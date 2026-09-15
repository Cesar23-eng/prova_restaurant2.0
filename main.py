import datetime
import os
import sys
import traceback

from PyQt6.QtCore import QLockFile, QTimer
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QApplication, QMessageBox

from utils.config import data_root, load_config


def install_error_handler():
    """
    PyQt6 cierra la aplicacion ante cualquier excepcion no capturada en un
    slot. En plena atencion eso es inaceptable: se registra el error en
    data/errores.log, se avisa al cajero y la app sigue abierta.
    """
    def handle(exc_type, exc, tb):
        detail = "".join(traceback.format_exception(exc_type, exc, tb))
        try:
            with open(os.path.join(data_root(), "errores.log"), "a", encoding="utf-8") as f:
                f.write(f"\n[{datetime.datetime.now():%Y-%m-%d %H:%M:%S}]\n{detail}")
        except OSError:
            pass
        if QApplication.instance() is not None:
            QMessageBox.critical(
                None, "Error inesperado",
                f"Ocurrio un error, pero los pedidos siguen guardados.\n\n{exc}\n\n"
                f"Detalle en data/errores.log",
            )

    sys.excepthook = handle


def main() -> int:
    install_error_handler()
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setApplicationName("PRÖVA México")
    app.setFont(QFont("Segoe UI", 10))

    # Dos copias abiertas pisarian los pedidos guardadas una de la otra
    lock = QLockFile(os.path.join(data_root(), "prova.lock"))
    if not lock.tryLock(200):
        QMessageBox.warning(None, "PRÖVA", "PRÖVA ya esta abierto en esta computadora.")
        return 1

    from models.menu import MenuData
    from models.order import OrderManager
    from views.main_window import ProvaRestaurant

    config = load_config()
    order_manager = OrderManager(cutoff_hour=int(config.get("hora_corte_jornada", 4)))
    window = ProvaRestaurant(order_manager, MenuData(), config)
    # En la caja se trabaja con la ventana completa
    window.showMaximized()

    # El servidor de meseros arranca cuando la ventana ya esta visible
    QTimer.singleShot(300, window.start_waiter_server)

    code = app.exec()
    lock.unlock()
    return code


if __name__ == "__main__":
    sys.exit(main())
