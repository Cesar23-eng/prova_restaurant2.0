import sys
import os
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QTimer
from views.main_window import ProvaRestaurant


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    window = ProvaRestaurant()
    window.show()

    # Arrancar Flask DESPUES de que la ventana ya esta lista y el cajero ingreso sus datos
    # QTimer.singleShot ejecuta en el proximo ciclo del event loop (ventana ya visible)
    def _start_flask():
        try:
            from server import init_server, start_server, get_local_ip
            from models.menu import MenuData

            menu_data = MenuData()

            def on_new_item(mesa_nombre: str):
                try:
                    if (
                        window.order_manager.current_table == mesa_nombre
                        and hasattr(window, "update_order_display")
                    ):
                        from PyQt6.QtCore import QMetaObject, Qt
                        QMetaObject.invokeMethod(
                            window,
                            "update_order_display",
                            Qt.ConnectionType.QueuedConnection,
                        )
                except Exception:
                    pass

            init_server(window.order_manager, menu_data, on_new_item)
            port = start_server(port=5000)
            ip = get_local_ip()

            # Agregar la URL al titulo SIN borrar lo que puso apertura de caja
            titulo_actual = window.windowTitle()
            window.setWindowTitle(f"{titulo_actual}  |  Meseros: http://{ip}:{port}")

        except Exception as e:
            print(f"[PROVA] Servidor de meseros no disponible: {e}")

    QTimer.singleShot(500, _start_flask)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
