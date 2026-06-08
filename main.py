import sys
import os
from PyQt6.QtWidgets import QApplication
from views.main_window import ProvaRestaurant


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    window = ProvaRestaurant()

    # Arrancar servidor Flask en hilo daemon
    try:
        from server import init_server, start_server, get_local_ip
        from models.menu import MenuData

        menu_data = MenuData()

        # Callback para refrescar el display de PyQt6 cuando llega un pedido del celular
        def on_new_item(mesa_nombre: str):
            try:
                if (
                    window.order_manager.current_table == mesa_nombre
                    and hasattr(window, "update_order_display")
                ):
                    # Llamar en el hilo principal de Qt
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
        window.setWindowTitle(
            f"PROVA - Sistema de Pedidos  |  Meseros: http://{ip}:{port}"
        )
    except Exception as e:
        # Si Flask no esta instalado, la app funciona igual sin el servidor
        print(f"[PROVA] Servidor de meseros no disponible: {e}")

    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
