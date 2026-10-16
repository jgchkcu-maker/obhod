from __future__ import annotations

import logging

from qfluentwidgets import MessageBox, PushButton

from obhod.core.diagnostics import detect_tunnel

ANYWAY = 2


def ensure_direct(parent, controller, action: str, proceed):
    """If a VPN/TUN proxy carries the traffic, offer to close it before `proceed()`."""
    try:
        found = detect_tunnel()
    except Exception:
        logging.getLogger("obhod").exception("Не удалось проверить туннели")
        found = []
    if not found:
        proceed()
        return
    box = MessageBox("Трафик идёт через VPN / прокси",
                     "\n".join(found) + f"\n\nПока туннель включён, {action} работает не через провайдера, "
                     "а через туннель. «Обход» может закрыть эти программы и вернуть прямое подключение: "
                     "их службы остановятся до перезагрузки, автозапуск не меняется.", parent)
    box.yesButton.setText("Отключить туннели и продолжить")
    box.cancelButton.setText("Отмена")
    anyway = PushButton("Всё равно продолжить", box.buttonGroup)
    anyway.clicked.connect(lambda: box.done(ANYWAY))
    box.buttonLayout.insertWidget(1, anyway, 1)
    result = box.exec()
    if result == ANYWAY:
        proceed()
    elif result:
        controller.close_tunnels(then=lambda _: proceed())
