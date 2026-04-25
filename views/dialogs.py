# views/dialogs.py - COMPLETO
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QDialogButtonBox,
    QListWidget, QPushButton, QMessageBox, QComboBox, QRadioButton,
    QButtonGroup, QGroupBox
)
from PyQt6.QtGui import QFont, QDoubleValidator
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
    """Diálogo de pago con cálculo automático de cambio"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.payment_method = None
        self.amount_paid = 0
        self.change = 0
        self.total_amount = 0

        # Obtener el total de la orden actual
        if hasattr(parent, 'order_manager') and parent.order_manager.current_table:
            _, self.total_amount = parent.order_manager.get_order_summary(
                parent.order_manager.current_table
            )

        self.setWindowTitle("Registrar Pago")
        self.setMinimumWidth(450)
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout()
        layout.setSpacing(20)

        # Total a pagar
        total_label = QLabel(f"<h2>Total a pagar: Bs. {self.total_amount:.2f}</h2>")
        total_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        total_label.setStyleSheet("color: #2196F3; font-weight: bold;")
        layout.addWidget(total_label)

        # Métodos de pago
        payment_group = QGroupBox("Método de Pago")
        payment_group.setStyleSheet("QGroupBox { font-weight: bold; }")
        payment_layout = QVBoxLayout()

        self.btn_group = QButtonGroup()
        self.radio_transfer = QRadioButton("💳 Transferencia / QR")
        self.radio_cash = QRadioButton("💵 Efectivo")

        self.radio_transfer.setStyleSheet("font-size: 14px;")
        self.radio_cash.setStyleSheet("font-size: 14px;")

        self.btn_group.addButton(self.radio_transfer)
        self.btn_group.addButton(self.radio_cash)

        payment_layout.addWidget(self.radio_transfer)
        payment_layout.addWidget(self.radio_cash)
        payment_group.setLayout(payment_layout)
        layout.addWidget(payment_group)

        # Sección de efectivo
        self.cash_section = QGroupBox("💵 Pago en Efectivo")
        self.cash_section.setStyleSheet("QGroupBox { font-weight: bold; color: #4CAF50; }")
        cash_layout = QVBoxLayout()
        cash_layout.setSpacing(15)

        cash_input_label = QLabel("Monto recibido del cliente:")
        cash_input_label.setStyleSheet("font-size: 13px;")
        cash_layout.addWidget(cash_input_label)

        self.cash_input = QLineEdit()
        self.cash_input.setPlaceholderText("Ej: 50, 100, 200...")
        self.cash_input.setStyleSheet("""
            QLineEdit {
                padding: 10px;
                font-size: 16px;
                border: 2px solid #4CAF50;
                border-radius: 5px;
            }
        """)

        validator = QDoubleValidator(0.00, 999999.99, 2)
        validator.setNotation(QDoubleValidator.Notation.StandardNotation)
        self.cash_input.setValidator(validator)
        cash_layout.addWidget(self.cash_input)

        # Etiqueta de cambio
        self.change_label = QLabel("")
        self.change_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.change_label.setStyleSheet("""
            font-size: 18px; 
            font-weight: bold; 
            padding: 15px;
            border-radius: 5px;
            background-color: #E8F5E9;
        """)
        cash_layout.addWidget(self.change_label)

        self.cash_section.setLayout(cash_layout)
        self.cash_section.setVisible(False)
        layout.addWidget(self.cash_section)

        # Botones
        buttons_layout = QHBoxLayout()

        btn_calculate = QPushButton("🧮 Calcular")
        btn_calculate.setStyleSheet("""
            QPushButton {
                background-color: #FF9800;
                color: white;
                font-weight: bold;
                padding: 10px;
                border-radius: 5px;
            }
            QPushButton:hover { background-color: #F57C00; }
        """)
        btn_calculate.clicked.connect(self.calculate_change)

        btn_confirm = QPushButton("✅ Confirmar")
        btn_confirm.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                font-weight: bold;
                padding: 10px;
                border-radius: 5px;
            }
            QPushButton:hover { background-color: #45a049; }
        """)
        btn_confirm.clicked.connect(self.confirm_payment)

        btn_cancel = QPushButton("❌ Cancelar")
        btn_cancel.setStyleSheet("""
            QPushButton {
                background-color: #f44336;
                color: white;
                font-weight: bold;
                padding: 10px;
                border-radius: 5px;
            }
            QPushButton:hover { background-color: #da190b; }
        """)
        btn_cancel.clicked.connect(self.reject)

        buttons_layout.addWidget(btn_calculate)
        buttons_layout.addWidget(btn_confirm)
        buttons_layout.addWidget(btn_cancel)

        layout.addLayout(buttons_layout)
        self.setLayout(layout)

        # Conectar señales
        self.radio_transfer.toggled.connect(self.toggle_cash_section)
        self.radio_cash.toggled.connect(self.toggle_cash_section)
        self.cash_input.textChanged.connect(self.on_cash_input_changed)

    def toggle_cash_section(self):
        self.cash_section.setVisible(self.radio_cash.isChecked())
        if not self.radio_cash.isChecked():
            self.change_label.setText("")
            self.cash_input.clear()

    def on_cash_input_changed(self):
        if self.radio_cash.isChecked() and self.cash_input.text():
            self.calculate_change()

    def calculate_change(self):
        if not self.radio_cash.isChecked():
            return

        try:
            cash_text = self.cash_input.text().strip()
            if not cash_text:
                return

            cash = float(cash_text)

            if cash < self.total_amount:
                falta = self.total_amount - cash
                self.change_label.setText(f"⚠️ FALTA: Bs. {falta:.2f}")
                self.change_label.setStyleSheet("""
                    font-size: 18px; font-weight: bold; color: white;
                    padding: 15px; border-radius: 5px; background-color: #f44336;
                """)
            elif cash == self.total_amount:
                self.change_label.setText(f"✅ MONTO EXACTO")
                self.change_label.setStyleSheet("""
                    font-size: 18px; font-weight: bold; color: white;
                    padding: 15px; border-radius: 5px; background-color: #4CAF50;
                """)
                self.change = 0
                self.amount_paid = cash
            else:
                self.change = round(cash - self.total_amount, 2)
                self.change_label.setText(f"💰 CAMBIO: Bs. {self.change:.2f}")
                self.change_label.setStyleSheet("""
                    font-size: 18px; font-weight: bold; color: white;
                    padding: 15px; border-radius: 5px; background-color: #4CAF50;
                """)
                self.amount_paid = cash
        except ValueError:
            pass

    def confirm_payment(self):
        if not self.radio_transfer.isChecked() and not self.radio_cash.isChecked():
            QMessageBox.warning(self, "Error", "Seleccione un método de pago")
            return

        if self.radio_transfer.isChecked():
            self.payment_method = "Transferencia/QR"
            self.amount_paid = self.total_amount
            self.change = 0
            self.accept()

        elif self.radio_cash.isChecked():
            try:
                cash_text = self.cash_input.text().strip()
                if not cash_text:
                    QMessageBox.warning(self, "Error", "Ingrese el monto recibido")
                    return

                cash = float(cash_text)
                if cash < self.total_amount:
                    QMessageBox.warning(self, "Error",
                                        f"Monto insuficiente. Falta: Bs. {self.total_amount - cash:.2f}")
                    return

                self.payment_method = "Efectivo"
                self.amount_paid = cash
                self.change = round(cash - self.total_amount, 2)
                self.accept()
            except ValueError:
                QMessageBox.warning(self, "Error", "Ingrese un monto válido")

    def get_payment_method(self):
        return self.payment_method

    def get_amount_paid(self):
        return self.amount_paid

    def get_change(self):
        return self.change
