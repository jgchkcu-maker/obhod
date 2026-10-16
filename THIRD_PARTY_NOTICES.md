# Сторонние компоненты и авторы

Обход — это графическая оболочка. Рабочие компоненты обхода созданы другими авторами и
распространяются здесь в неизменном виде под их собственными лицензиями.
Все права на них принадлежат их авторам.

| Компонент | Где в репозитории | Авторы | Лицензия |
|---|---|---|---|
| **zapret** (`winws.exe`, технология desync) | `bin/winws.exe` | bol-van — <https://github.com/bol-van/zapret> | MIT, © 2016–2026 bol-van |
| **zapret-discord-youtube** (готовые стратегии `general*.bat`, списки доменов и IP, файлы `*.bin`), версия 1.10.3 | `bin/*.bin`, `lists/`, `vendor/`, `strategies/flowseal/` (импорт из `.bat`) | Flowseal — <https://github.com/Flowseal/zapret-discord-youtube> | MIT, © 2024–2026 Flowseal |
| **WinDivert** (`WinDivert.dll`, `WinDivert64.sys`) | `bin/WinDivert.dll`, `bin/WinDivert64.sys` | Basil (basil00) — <https://github.com/basil00/WinDivert> | LGPLv3 или GPLv2 на выбор |
| **Cygwin** (`cygwin1.dll`) | `bin/cygwin1.dll` | Cygwin contributors / Red Hat — <https://cygwin.com> | LGPLv3 с исключением для Cygwin API, см. <https://cygwin.com/licensing.html>; исходный код: <https://cygwin.com/git/> |

## Тексты лицензий

- MIT (bol-van, Flowseal): [`licenses/MIT-Flowseal-and-bol-van.txt`](licenses/MIT-Flowseal-and-bol-van.txt) — копия `LICENSE.txt` из репозитория Flowseal.
- WinDivert (LGPLv3 / GPLv2): [`licenses/WinDivert-LICENSE.txt`](licenses/WinDivert-LICENSE.txt) — копия `LICENSE` из репозитория WinDivert.
- Cygwin: текст и исходный код по ссылкам выше.

Файлы `bin/` и `lists/` получены скриптом [`scripts/fetch_vendor.py`](scripts/fetch_vendor.py) из релиза
Flowseal v1.10.3 с проверкой SHA-256 и не изменялись. Исходный архив лежит в `vendor/flowseal-1.10.3.zip`.

## Собственный код

Код приложения «Обход» (`obhod/`, `scripts/`) распространяется под GPL-3.0-or-later, см. [`LICENSE`](LICENSE).
