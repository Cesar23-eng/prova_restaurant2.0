import sys
from PyQt6.QtWidgets import QApplication
from views.main_window import ProvaRestaurant
import os

def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    window = ProvaRestaurant()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
