# Обход

Windows-приложение (PySide6) для запуска и автоподбора стратегий обхода DPI-блокировок
для YouTube, Discord и Fortnite. Это оболочка над [zapret](https://github.com/bol-van/zapret)
и стратегиями [Flowseal](https://github.com/Flowseal/zapret-discord-youtube); сами они
написаны не мной — см. [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

## Запуск из исходников

Нужны Windows и Python 3.11–3.14.

```powershell
python -m venv .venv
.venv\Scripts\pip install -e .
.venv\Scripts\python -m obhod
```

Для работы `winws` нужен запуск от администратора. Бинарники и списки (`bin/`, `lists/`)
уже лежат в репозитории; при желании их можно заново получить из закреплённого релиза
Flowseal 1.10.3 командой `python scripts/fetch_vendor.py` (SHA-256 проверяется).

Перед автоподбором закройте VPN/TUN-клиенты (FlClash, Happ и т.п.): иначе трафик идёт
через туннель и обход нечего подбирать.

## Лицензии и авторы

- Код приложения — GPL-3.0-or-later ([LICENSE](LICENSE)).
- zapret / winws — © bol-van, MIT; стратегии и списки — © Flowseal, MIT.
- WinDivert — © basil00, LGPLv3/GPLv2; Cygwin — LGPLv3 с исключением.

Подробности и ссылки: [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
