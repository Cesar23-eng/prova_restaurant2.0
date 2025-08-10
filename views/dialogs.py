from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QLineEdit, QDialogButtonBox,
    QListWidget, QPushButton, QMessageBox, QComboBox
)
from PyQt6.QtGui import QFont
from PyQt6.QtCore import Qt


class AddOrderDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()

    def setup_ui(self):
        self.setWindowTitle("Nuevo Pedido")
        self.setFixedSize(350, 200)

        layout = QVBoxLayout()
        layout.setContentsMargins(20, 20, 20, 20)

        lbl_name = QLabel("Nombre de mesa/cliente:")
        lbl_name.setFont(QFont("Arial", 12))
        self.name_input = QLineEdit()
        self.name_input.setFont(QFont("Arial", 12))

        btn_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        btn_box.accepted.connect(self.accept)
        btn_box.rejected.connect(self.reject)

        layout.addWidget(lbl_name)
        layout.addWidget(self.name_input)
        layout.addWidget(btn_box)

        self.setLayout(layout)

    def get_order_name(self) -> str:
        return self.name_input.text().strip()


class EditTableDialog(QDialog):
    def __init__(self, current_name, parent=None):
        super().__init__(parent)
        self.current_name = current_name
        self.setup_ui()

    def setup_ui(self):
        self.setWindowTitle("Editar Nombre")
        self.setFixedSize(350, 200)

        layout = QVBoxLayout()
        layout.setContentsMargins(20, 20, 20, 20)

        lbl_name = QLabel("Nuevo nombre:")
        lbl_name.setFont(QFont("Arial", 12))
        self.name_input = QLineEdit(self.current_name)
        self.name_input.setFont(QFont("Arial", 12))

        btn_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        btn_box.accepted.connect(self.accept)
        btn_box.rejected.connect(self.reject)

        layout.addWidget(lbl_name)
        layout.addWidget(self.name_input)
        layout.addWidget(btn_box)

        self.setLayout(layout)

    def get_new_name(self) -> str:
        return self.name_input.text().strip()


class DeleteItemDialog(QDialog):
    def __init__(self, items, parent=None):
        super().__init__(parent)
        self.items = items
        self.selected_index = None
        self.setup_ui()

    def setup_ui(self):
        self.setWindowTitle("Eliminar Platillo")
        self.setFixedSize(400, 300)

        layout = QVBoxLayout()

        lbl = QLabel("Selecciona el platillo a eliminar:")
        lbl.setFont(QFont("Arial", 12))

        self.list_widget = QListWidget()
        for i, item in enumerate(self.items):
            self.list_widget.addItem(f"{i + 1}. {item['dish']} ({item['variant']}) - Bs{item['price']}")

        btn_eliminar = QPushButton("Eliminar Selección")
        btn_eliminar.setObjectName("dangerButton")
        btn_eliminar.clicked.connect(self.on_delete_clicked)

        layout.addWidget(lbl)
        layout.addWidget(self.list_widget)
        layout.addWidget(btn_eliminar)

        self.setLayout(layout)

    def on_delete_clicked(self):
        self.selected_index = self.list_widget.currentRow()
        if self.selected_index >= 0:
            self.accept()
        else:
            QMessageBox.warning(self, "Error", "Selecciona un platillo primero")

    def get_selected_index(self) -> int:
        return self.selected_index


class PaymentDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()

    def setup_ui(self):
        self.setWindowTitle("Marcar como Pagado")
        self.setFixedSize(300, 200)

        layout = QVBoxLayout()
        layout.setContentsMargins(20, 20, 20, 20)

        lbl = QLabel("Método de pago:")
        lbl.setFont(QFont("Arial", 12))

        self.method_combo = QComboBox()
        self.method_combo.addItems(["Efectivo", "QR"])
        self.method_combo.setFont(QFont("Arial", 12))

        btn_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        btn_box.accepted.connect(self.accept)
        btn_box.rejected.connect(self.reject)

        layout.addWidget(lbl)
        layout.addWidget(self.method_combo)
        layout.addWidget(btn_box)

        self.setLayout(layout)

    def get_payment_method(self) -> str:
        return self.method_combo.currentText()