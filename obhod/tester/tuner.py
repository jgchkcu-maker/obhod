from __future__ import annotations

import asyncio
import logging
import math
import threading
import time
from dataclasses import asdict, dataclass, field

from obhod.core.strategy import Block
from .probes import ProbeResult, ProbeSuite

WEIGHTS = {"tls13": 2.0, "tls12": 1.0, "freeze": 2.0, "websocket": 1.0, "http": .25}
MEASURED = {"google-tcp", "general-tcp", "epic-tcp"}
log = logging.getLogger("obhod.tuner")


def score(results: list[ProbeResult], category: str | None = None) -> float:
    selected = [r for r in results if category is None or r.category == category]
    value = 0.0
    for result in selected:
        if result.kind not in WEIGHTS:
            continue
        if result.status == "ok":
            value += WEIGHTS[result.kind] - min(result.latency_ms, 4000) / 40000
            if result.kind == "freeze" and result.service == "youtube":
                value += min(1.0, math.log1p(max(0, result.kbps)) / 12)
        elif result.status == "suspected_freeze":
            value -= 2
    return round(value, 4)


@dataclass
class Round:
    id: str
    name: str
    blocks: list[str]
    results: list[ProbeResult] = field(default_factory=list)
    error: str = ""
    elapsed: float = 0

    def to_dict(self):
        return asdict(self)


@dataclass
class TuningResult:
    rounds: list[Round]
    blocks: list[str]
    verified: bool
    reason: str
    elapsed: float

    def to_dict(self):
        return {"rounds": [r.to_dict() for r in self.rounds], "blocks": self.blocks,
                "verified": self.verified, "reason": self.reason, "elapsed": self.elapsed}


class Tuner:
    def __init__(self, catalog, runner, compose, targets, cancel=None, on_round=None):
        self.catalog, self.runner, self.compose, self.targets = catalog, runner, compose, targets
        self.cancel = cancel or threading.Event()
        self.on_round = on_round or (lambda *args: None)
        self.suite = ProbeSuite()

    def candidates(self):
        defaults = self.catalog.default()
        for strategy in self.catalog.strategies:
            blocks = list(strategy.blocks)
            if not any(b.category == "epic-tcp" for b in blocks):
                blocks += [self.catalog.blocks["E2"]]
            yield strategy.id, strategy.name, blocks
        for epic in [b for b in self.catalog.custom if b.category == "epic-tcp"]:
            yield "custom-" + epic.id, f"Epic {epic.id} · {epic.label}", [b for b in defaults if b.category != "epic-tcp"] + [epic]

    def failures(self, row: Round, baseline: Round) -> list[str]:
        """Why a verification round is not acceptable, per measured category; empty list = passed."""
        problems = []
        if row.error:
            return [row.error]
        for category in sorted({t.category for t in self.targets} & MEASURED):
            got, base = score(row.results, category), score(baseline.results, category)
            if not any(r.status == "ok" and r.kind in {"tls12", "tls13"} and r.category == category for r in row.results):
                problems.append(f"{category}: ни один TLS-запрос не прошёл")
            # One lost TLS 1.3 probe costs 2 points, so a fixed 0.25 margin turned every network hiccup into
            # a failure. Allow ~15% of the baseline instead: a real breakage loses far more than that.
            elif got < base - max(.5, .15 * base):
                problems.append(f"{category}: {got} против {base} без обхода")
        return problems

    def run(self, max_seconds=420, round_budget=10.0, verify_budget=16.0):
        start = time.monotonic()
        rounds = []
        def probe_round(identifier, name, blocks, total, final=False):
            began = time.monotonic()
            row = Round(identifier, name, [b.id for b in blocks])
            try:
                if blocks:
                    self.runner.start(self.compose(blocks))
                remaining = max_seconds - (time.monotonic() - start)
                if remaining <= 0 and not final:
                    raise TimeoutError("Истёк общий лимит автоподбора")
                budget = verify_budget if final else min(round_budget, remaining)
                # The unscored bare TCP connect only eats concurrency slots, so tuning skips it.
                row.results = asyncio.run(self.suite.run(self.targets, budget=budget, cancel=self.cancel,
                                                         dns=False, kinds=("tls13", "tls12", "http")))
            except Exception as exc:
                row.error = str(exc)
            finally:
                self.runner.stop()
            row.elapsed = round(time.monotonic() - began, 2)
            rounds.append(row)
            self._log_round(row)
            self.on_round(row.to_dict(), len(rounds), total)
            return row
        candidates = list(self.candidates())
        total = len(candidates) + 1 + 4  # baseline + up to four verification rounds
        try:
            baseline = probe_round("baseline", "Без обхода", [], total)
            if baseline.error:
                raise RuntimeError(baseline.error)
            for identifier, name, blocks in candidates:
                if self.cancel.is_set():
                    raise InterruptedError("Автоподбор отменён; предыдущий режим восстановлен")
                if time.monotonic() - start > max_seconds - 3 * verify_budget:
                    log.warning("Автоподбор: лимит времени, пропущено стратегий: %d",
                                len(candidates) - len(rounds) + 1)
                    break
                probe_round(identifier, name, blocks, total)
            if self.cancel.is_set():
                raise InterruptedError("Автоподбор отменён; предыдущий режим восстановлен")
            chosen = self.catalog.default()
            for category in MEASURED:
                eligible = [r for r in rounds if r.blocks and not r.error and any(
                    p.category == category and p.kind in WEIGHTS and p.status == "ok" for p in r.results)]
                if not eligible:
                    continue
                def key(row):
                    group = [self.catalog.blocks[x] for x in row.blocks if self.catalog.blocks[x].category == category]
                    return (score(row.results, category), -sum(b.complexity for b in group))
                eligible = [r for r in eligible if any(self.catalog.blocks[x].category == category for x in r.blocks)]
                if not eligible:
                    continue
                best = max(eligible, key=key)
                replacement = [self.catalog.blocks[x] for x in best.blocks if self.catalog.blocks[x].category == category]
                chosen = [b for b in chosen if b.category != category] + replacement
            # Mixing blocks from different strategies can misbehave, and one 10-second sample is noisy.
            # So: check the mix, re-check it once, then fall back to the best strategies measured as a whole.
            measured = {t.category for t in self.targets} & MEASURED
            whole = sorted((r for r in rounds if r.blocks and not r.error and r.id != "baseline"),
                           key=lambda r: sum(score(r.results, c) for c in measured), reverse=True)
            attempts = [("composite", "Мой профиль · проверка", chosen),
                        ("composite-retry", "Мой профиль · повторная проверка", chosen)]
            attempts += [(f"fallback-{r.id}", f"{r.name} · проверка", [self.catalog.blocks[x] for x in r.blocks])
                         for r in whole[:2]]
            problems: list[str] = []
            for identifier, name, blocks in attempts:
                if self.cancel.is_set():
                    raise InterruptedError("Автоподбор отменён; предыдущий режим восстановлен")
                problems = self.failures(probe_round(identifier, name, blocks, total, True), baseline)
                if not problems:
                    log.info("Автоподбор: принят вариант «%s»", name)
                    reason = ("Комбинация проверена на HTTP/TLS. QUIC, голос Discord и UDP игры требуют живой проверки."
                              if identifier.startswith("composite") else
                              f"Смешанная комбинация не прошла проверку, выбрана стратегия целиком: "
                              f"{name.removesuffix(' · проверка')}. "
                              "QUIC, голос Discord и UDP игры требуют живой проверки.")
                    return TuningResult(rounds, [b.id for b in blocks], True, reason, round(time.monotonic() - start, 1))
                log.warning("Автоподбор: «%s» не прошёл проверку: %s", name, "; ".join(problems))
            reason = ("Ни один вариант не прошёл финальную проверку, предыдущий профиль сохранён. Причина: "
                      + "; ".join(problems) + ". Подробности — в журнале и .state/reports.")
            return TuningResult(rounds, [b.id for b in chosen], False, reason, round(time.monotonic() - start, 1))
        finally:
            self.runner.stop()

    @staticmethod
    def _log_round(row: Round):
        if row.error:
            log.warning("Автоподбор · %s: ошибка: %s", row.name, row.error)
            return
        scores = ", ".join(f"{c}={score(row.results, c)}" for c in sorted({r.category for r in row.results} & MEASURED))
        bad = sorted({f"{r.target}/{r.kind}={r.status}" for r in row.results
                      if r.kind in {"tls12", "tls13", "freeze", "websocket"} and r.status != "ok"})
        log.info("Автоподбор · %s (%.1f с): %s%s", row.name, row.elapsed, scores,
                 "; сбои: " + ", ".join(bad) if bad else "")
