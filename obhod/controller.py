from __future__ import annotations

import asyncio
import json
import logging
import threading
import time

from PySide6.QtCore import QObject, Signal, Slot

from obhod.core.catalog import Catalog
from obhod.core.conflicts import detect_conflicts, stop_conflict
from obhod.core.lists import Lists
from obhod.core.paths import Paths, State
from obhod.core.service import ServiceManager
from obhod.core.strategy import compose
from obhod.core.tunnels import make_direct
from obhod.core.winws import WinwsRunner
from obhod.tester.probes import ProbeSuite
from obhod.tester.targets import load_targets
from obhod.tester.tuner import MEASURED, Tuner, score

log = logging.getLogger("obhod")
SERVICES = ("youtube", "discord", "fortnite")


class Controller(QObject):
    """Owns the backend; long operations run in threads and report back on the GUI thread."""
    statusChanged = Signal()
    busyChanged = Signal(bool)
    message = Signal(str, str)              # level: success|warning|error|info, text
    probed = Signal(dict)                   # service -> {"status": ok|fail|unknown, "latency": ms}
    tunerRound = Signal(dict, int, int)
    tunerFinished = Signal(object)
    _done = Signal(object, object, object)  # callback, result, error

    def __init__(self, paths: Paths | None = None):
        super().__init__()
        self.paths = paths or Paths()
        self.paths.ensure()
        self.state = State(self.paths)
        self.lists = Lists(self.paths)
        self.lists.prepare_game()
        self.catalog = Catalog(self.paths.strategies)
        self.runner = WinwsRunner(self.paths.bin / "winws.exe")
        self.service = ServiceManager(self.paths.bin / "winws.exe")
        self.busy = False
        self.health: dict[str, dict] = {s: {"status": "unknown", "latency": 0} for s in SERVICES}
        self._cancel = threading.Event()
        self._done.connect(self._dispatch)

    # --- helpers -------------------------------------------------------------------------
    @Slot(object, object, object)
    def _dispatch(self, callback, result, error):
        self._set_busy(False)
        if callback:
            callback(result, error)
        self.statusChanged.emit()

    def _set_busy(self, value):
        if self.busy != value:
            self.busy = value
            self.busyChanged.emit(value)

    def _spawn(self, fn, callback=None):
        if self.busy:
            self.message.emit("warning", "Подождите, предыдущая операция ещё выполняется")
            return False
        self._set_busy(True)

        def work():
            try:
                result, error = fn(), None
            except Exception as exc:  # reported to the user, full trace goes to the log
                log.exception("Операция завершилась ошибкой")
                result, error = None, exc
            self._done.emit(callback, result, error)
        threading.Thread(target=work, daemon=True).start()
        return True

    # --- profile ---------------------------------------------------------------------------
    def blocks(self):
        try:
            return self.catalog.select(self.state.get("profile"))
        except ValueError:
            log.warning("Сохранённый профиль устарел, используется профиль по умолчанию")
            self.state.update(profile=None, profile_name="Сбалансированный")
            return self.catalog.default()

    def argv(self, blocks=None):
        tcp, udp = self.state.get("tcp_ports"), self.state.get("udp_ports")
        return compose(blocks or self.blocks(), self.state.get("game_mode"), self.state.get("ipset_mode"),
                       variables=self.paths.variables(tcp, udp), services=self.state.get("services"),
                       tcp_ports=tcp, udp_ports=udp)

    @property
    def service_installed(self):
        return self.service.status()["status"] not in {"not_installed", "unknown"}

    @property
    def running(self):
        return self.runner.running or self.service.status()["status"] == "running"

    def conflicts(self):
        return detect_conflicts(self.runner.process.pid if self.runner.running else None)

    # --- start / stop ------------------------------------------------------------------------
    def _start(self):
        self.lists.prepare_game()
        argv = self.argv()
        if self.state.get("autostart"):
            self.service.install(argv)
        else:
            self.runner.replace(argv) if self.runner.running else self.runner.start(argv)
        log.info("Обход включён: %s", self.state.get("profile_name"))

    def _stop(self):
        self.runner.stop()
        if self.service_installed:
            self.service.stop()
        log.info("Обход выключен")

    def start(self, stop_conflicts=False, then_probe=True):
        def work():
            if stop_conflicts:
                for item in self.conflicts():
                    stop_conflict(item)
            self._start()

        def done(_, error):
            if error:
                self.message.emit("error", f"Не удалось включить обход: {error}")
            else:
                self.message.emit("success", "Обход включён")
                if then_probe:
                    self.probe()
        return self._spawn(work, done)

    def stop(self):
        def done(_, error):
            self.health = {s: {"status": "unknown", "latency": 0} for s in SERVICES}
            self.probed.emit(self.health)
            if error:
                self.message.emit("error", f"Не удалось выключить обход: {error}")
        return self._spawn(self._stop, done)

    def restart_if_running(self):
        if self.running:
            self.start()

    def stop_now(self):
        """Synchronous stop for application exit (the service, if installed, keeps running)."""
        self._cancel.set()
        self.runner.stop()

    # --- tunnels ------------------------------------------------------------------------
    def close_tunnels(self, then=None):
        """Close VPN/TUN clients so traffic goes directly; calls then(report) on success."""
        def done(report, error):
            if error:
                self.message.emit("error", f"Не удалось отключить туннели: {error}")
                return
            closed = ", ".join(report["closed"]) or "клиентов не найдено"
            if report["errors"] or report["remaining"]:
                problems = report["errors"] + report["remaining"]
                self.message.emit("warning", "Отключено не полностью: " + "; ".join(problems))
            else:
                self.message.emit("success", f"Туннели отключены ({closed}); " + ", ".join(report["notes"]))
            if then and not report["remaining"]:
                then(report)
        return self._spawn(make_direct, done)

    # --- quick health check ------------------------------------------------------------------------
    def probe(self):
        services = [s for s in self.state.get("services") if s in SERVICES]

        def work():
            targets = load_targets(self.paths.root / "data/targets.json", services, quick=True)
            results = asyncio.run(ProbeSuite().run(targets, budget=7.0))
            health = {s: {"status": "unknown", "latency": 0} for s in SERVICES}
            for service in services:
                tls = [r for r in results if r.service == service and r.kind in {"tls12", "tls13"}]
                good = [r for r in tls if r.status == "ok"]
                health[service] = {"status": "ok" if good else ("fail" if tls else "unknown"),
                                   "latency": round(min(r.latency_ms for r in good)) if good else 0}
            return health

        def done(health, error):
            if error:
                self.message.emit("error", f"Проверка не удалась: {error}")
                return
            self.health = health
            self.probed.emit(health)
        return self._spawn(work, done)

    # --- auto tuning ------------------------------------------------------------------------
    def tune(self):
        self._cancel = threading.Event()
        services = [s for s in self.state.get("services") if s in SERVICES]

        def work():
            was_running, via_service = self.running, self.service.status()["status"] == "running"
            self.runner.stop()
            if via_service:
                self.service.stop()
            try:
                targets = load_targets(self.paths.root / "data/targets.json", services)
                self.lists.prepare_game()
                tuner = Tuner(self.catalog, self.runner, self.argv, targets, self._cancel,
                              lambda row, i, total: self.tunerRound.emit(row, i, total))
                result = tuner.run()
                report = self.paths.reports / time.strftime("tune-%Y%m%d-%H%M%S.json")
                report.write_text(json.dumps(result.to_dict(), ensure_ascii=False, indent=1), encoding="utf-8")
                if result.verified:
                    self.state.update(profile=result.blocks, tuned_profile=result.blocks, profile_name="Мой профиль")
                return result
            finally:
                if was_running:
                    try:
                        self._start()
                    except Exception:
                        log.exception("Не удалось восстановить обход после автоподбора")

        def done(result, error):
            self.tunerFinished.emit(error or result)
        return self._spawn(work, done)

    def cancel_tuning(self):
        self._cancel.set()

    @staticmethod
    def service_score(results, service):
        cats = {"youtube": {"google-tcp"}, "discord": {"general-tcp"}, "fortnite": {"epic-tcp"}}[service] & MEASURED
        return round(sum(score([r for r in results if r.service == service], c) for c in cats), 2)

    # --- autostart ------------------------------------------------------------------------
    def set_autostart(self, enabled: bool):
        def work():
            if enabled:
                self.lists.prepare_game()
                self.runner.stop()
                self.service.install(self.argv(), start=True)
            else:
                self.service.remove()
                if self.state.get("autostart"):
                    self.state.update(autostart=False)
            self.state.update(autostart=enabled)

        def done(_, error):
            if error:
                self.message.emit("error", f"Служба: {error}")
            else:
                self.message.emit("success", "Автозапуск включён" if enabled else "Автозапуск выключен")
        return self._spawn(work, done)
