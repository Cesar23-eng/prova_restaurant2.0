# views/dialogs.py
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QDialogButtonBox,
    QListWidget, QPushButton, QMessageBox, QComboBox, QRadioButton,
    QButtonGroup, QGroupBox, QFormLayout
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
            self.list_widget.addItem(
                f"{i + 1}. {item['dish']} ({item['variant']}) - Bs{item['price']}"
            )
        btn_eliminar = QPushButton("Eliminar Seleccion")
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


# ---------------------------------------------------------------------------
#  DeliveryDialog  (req. 2) - Costo de moto y metodo de pago a la moto
# ---------------------------------------------------------------------------
class DeliveryDialog(QDialog):
    """
    Dialogo que aparece cuando el tipo de pedido es 'Para llevar'.
    Captura el costo de la moto y el metodo de pago (Efectivo / QR).
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self._moto_cost = 0.0
        self._moto_method = "Efectivo"
        self.setWindowTitle("Detalles de Delivery")
        self.setFixedSize(380, 220)
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout()
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)

        title = QLabel("Informacion del Pedido Para Llevar")
        title.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        form = QFormLayout()
        form.setSpacing(10)

        # Costo moto
        self.moto_cost_input = QLineEdit()
        self.moto_cost_input.setPlaceholderText("Ej: 10, 15, 20...")
        validator = QDoubleValidator(0.00, 9999.99, 2)
        validator.setNotation(QDoubleValidator.Notation.StandardNotation)
        self.moto_cost_input.setValidator(validator)
        form.addRow("Costo de la moto (Bs):", self.moto_cost_input)

        # Metodo pago moto
        self.moto_method_combo = QComboBox()
        self.moto_method_combo.addItems(["Efectivo", "QR"])
        form.addRow("Pago a la moto:", self.moto_method_combo)

        layout.addLayout(form)

        btn_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        btn_box.accepted.connect(self._on_accept)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)
        self.setLayout(layout)

    def _on_accept(self):
        text = self.moto_cost_input.text().strip()
        if not text:
            QMessageBox.warning(self, "Campo requerido", "Ingresa el costo de la moto.")
            return
        try:
            self._moto_cost = float(text)
        except ValueError:
            QMessageBox.warning(self, "Valor invalido", "Ingresa un numero valido.")
            return
        self._moto_method = self.moto_method_combo.currentText()
        self.accept()

    def get_moto_cost(self) -> float:
        return self._moto_cost

    def get_moto_method(self) -> str:
        return self._moto_method


# ---------------------------------------------------------------------------
#  PaymentDialog  (req. 1, 4) - Pagos mixtos + metodo de cambio
# ---------------------------------------------------------------------------
class PaymentDialog(QDialog):
    """
    Dialogo de pago con:
    - Efectivo
    - QR / Transferencia
    - Pago Mixto (efectivo + QR)
    - Registro del metodo de cambio (req. 4)
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._payment_method = ""
        self._amount_paid = 0.0
        self._change = 0.0
        self._cash_amount = 0.0
        self._qr_amount = 0.0
        self._change_method = ""
        self.total_amount = 0.0

        if hasattr(parent, "order_manager") and parent.order_manager.current_table:
            _, self.total_amount = parent.order_manager.get_order_summary(
                parent.order_manager.current_table
            )

        self.setWindowTitle("Registrar Pago")
        self.setMinimumWidth(480)
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout()
        layout.setSpacing(16)
        layout.setContentsMargins(20, 20, 20, 20)

        # Total
        total_label = QLabel(f"<h2>Total a pagar: Bs. {self.total_amount:.2f}</h2>")
        total_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        total_label.setStyleSheet("color: #2196F3; font-weight: bold;")
        layout.addWidget(total_label)

        # --- Metodo de pago ---
        method_group = QGroupBox("Metodo de Pago")
        method_group.setStyleSheet("QGroupBox { font-weight: bold; }")
        method_layout = QVBoxLayout()

        self.btn_group = QButtonGroup(self)
        self.radio_cash = QRadioButton("Efectivo")
        self.radio_qr = QRadioButton("QR / Transferencia")
        self.radio_mixed = QRadioButton("Pago Mixto (Efectivo + QR)")

        for r in [self.radio_cash, self.radio_qr, self.radio_mixed]:
            r.setStyleSheet("font-size: 13px;")
            self.btn_group.addButton(r)
            method_layout.addWidget(r)

        method_group.setLayout(method_layout)
        layout.addWidget(method_group)

        # --- Seccion efectivo puro ---
        self.cash_section = QGroupBox("Pago en Efectivo")
        self.cash_section.setStyleSheet("QGroupBox { font-weight: bold; color: #4CAF50; }")
        cash_layout = QVBoxLayout()
        cash_layout.setSpacing(10)
        cash_layout.addWidget(QLabel("Monto recibido del cliente:"))
        self.cash_input = QLineEdit()
        self.cash_input.setPlaceholderText("Ej: 50, 100, 200...")
        self._apply_input_style(self.cash_input, "#4CAF50")
        self._set_validator(self.cash_input)
        cash_layout.addWidget(self.cash_input)
        self.change_label = QLabel("")
        self.change_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._style_change_label(self.change_label, neutral=True)
        cash_layout.addWidget(self.change_label)
        self.cash_section.setLayout(cash_layout)
        self.cash_section.setVisible(False)
        layout.addWidget(self.cash_section)

        # --- Seccion QR puro (sin campos extra, solo confirmacion) ---
        self.qr_section = QGroupBox("QR / Transferencia")
        self.qr_section.setStyleSheet("QGroupBox { font-weight: bold; color: #2196F3; }")
        qr_layout = QVBoxLayout()
        qr_info = QLabel(f"Se registrara pago de Bs. {self.total_amount:.2f} por QR.")
        qr_info.setStyleSheet("font-size: 13px; color: #2196F3;")
        qr_layout.addWidget(qr_info)
        self.qr_section.setLayout(qr_layout)
        self.qr_section.setVisible(False)
        layout.addWidget(self.qr_section)

        # --- Seccion pago mixto ---
        self.mixed_section = QGroupBox("Pago Mixto")
        self.mixed_section.setStyleSheet("QGroupBox { font-weight: bold; color: #FF9800; }")
        mixed_layout = QFormLayout()
        mixed_layout.setSpacing(10)

        self.mixed_cash_input = QLineEdit()
        self.mixed_cash_input.setPlaceholderText("Monto en Efectivo")
        self._apply_input_style(self.mixed_cash_input, "#4CAF50")
        self._set_validator(self.mixed_cash_input)
        mixed_layout.addRow("Efectivo (Bs):", self.mixed_cash_input)

        self.mixed_qr_input = QLineEdit()
        self.mixed_qr_input.setPlaceholderText("Monto en QR")
        self._apply_input_style(self.mixed_qr_input, "#2196F3")
        self._set_validator(self.mixed_qr_input)
        mixed_layout.addRow("QR (Bs):", self.mixed_qr_input)

        self.mixed_status_label = QLabel("")
        self.mixed_status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._style_change_label(self.mixed_status_label, neutral=True)
        mixed_layout.addRow(self.mixed_status_label)
        self.mixed_section.setLayout(mixed_layout)
        self.mixed_section.setVisible(False)
        layout.addWidget(self.mixed_section)

        # --- Cambio dado en (req. 4) ---
        self.change_method_group = QGroupBox("Cambio dado en")
        self.change_method_group.setStyleSheet("QGroupBox { font-weight: bold; }")
        cm_layout = QHBoxLayout()
        self.btn_group_change = QButtonGroup(self)
        self.radio_change_cash = QRadioButton("Efectivo")
        self.radio_change_qr = QRadioButton("QR")
        self.radio_change_cash.setChecked(True)
        for r in [self.radio_change_cash, self.radio_change_qr]:
            self.btn_group_change.addButton(r)
            cm_layout.addWidget(r)
        self.change_method_group.setLayout(cm_layout)
        self.change_method_group.setVisible(False)
        layout.addWidget(self.change_method_group)

        # --- Botones ---
        buttons_layout = QHBoxLayout()

        btn_calculate = QPushButton("Calcular")
        btn_calculate.setStyleSheet(self._btn_style("#FF9800", "#F57C00"))
        btn_calculate.clicked.connect(self.calculate)

        btn_confirm = QPushButton("Confirmar Pago")
        btn_confirm.setStyleSheet(self._btn_style("#4CAF50", "#45a049"))
        btn_confirm.clicked.connect(self.confirm_payment)

        btn_cancel = QPushButton("Cancelar")
        btn_cancel.setStyleSheet(self._btn_style("#f44336", "#da190b"))
        btn_cancel.clicked.connect(self.reject)

        buttons_layout.addWidget(btn_calculate)
        buttons_layout.addWidget(btn_confirm)
        buttons_layout.addWidget(btn_cancel)
        layout.addLayout(buttons_layout)
        self.setLayout(layout)

        # Senales
        self.radio_cash.toggled.connect(self._update_sections)
        self.radio_qr.toggled.connect(self._update_sections)
        self.radio_mixed.toggled.connect(self._update_sections)
        self.cash_input.textChanged.connect(self._auto_calculate)
        self.mixed_cash_input.textChanged.connect(self._auto_calculate)
        self.mixed_qr_input.textChanged.connect(self._auto_calculate)

    # ------------------------------------------------------------------
    #  Helpers de estilo
    # ------------------------------------------------------------------
    def _apply_input_style(self, widget, border_color):
        widget.setStyleSheet(f"""
            QLineEdit {{
                padding: 8px;
                font-size: 14px;
                border: 2px solid {border_color};
                border-radius: 4px;
            }}
        """)

    def _set_validator(self, widget):
        v = QDoubleValidator(0.00, 999999.99, 2)
        v.setNotation(QDoubleValidator.Notation.StandardNotation)
        widget.setValidator(v)

    def _style_change_label(self, lbl, neutral=False, ok=False, err=False):
        if neutral:
            lbl.setStyleSheet("font-size: 15px; font-weight: bold; padding: 10px;")
        elif ok:
            lbl.setStyleSheet("""
                font-size: 15px; font-weight: bold; color: white;
                padding: 10px; border-radius: 5px; background-color: #4CAF50;
            """)
        elif err:
            lbl.setStyleSheet("""
                font-size: 15px; font-weight: bold; color: white;
                padding: 10px; border-radius: 5px; background-color: #f44336;
            """)

    @staticmethod
    def _btn_style(bg, hover):
        return f"""
            QPushButton {{
                background-color: {bg}; color: white;
                font-weight: bold; padding: 10px; border-radius: 5px;
            }}
            QPushButton:hover {{ background-color: {hover}; }}
        """

    @staticmethod
    def _safe_float(text: str) -> float:
        try:
            return float((text or "").strip())
        except ValueError:
            return 0.0

    # ------------------------------------------------------------------
    #  Logica de visibilidad
    # ------------------------------------------------------------------
    def _update_sections(self):
        is_cash = self.radio_cash.isChecked()
        is_qr = self.radio_qr.isChecked()
        is_mixed = self.radio_mixed.isChecked()
        self.cash_section.setVisible(is_cash)
        self.qr_section.setVisible(is_qr)
        self.mixed_section.setVisible(is_mixed)
        # Reset labels
        if not is_cash:
            self.cash_input.clear()
            self.change_label.setText("")
        if not is_mixed:
            self.mixed_cash_input.clear()
            self.mixed_qr_input.clear()
            self.mixed_status_label.setText("")
        self.change_method_group.setVisible(False)

    def _auto_calculate(self):
        if self.radio_cash.isChecked() or self.radio_mixed.isChecked():
            self.calculate()

    # ------------------------------------------------------------------
    #  Calculo
    # ------------------------------------------------------------------
    def calculate(self):
        if self.radio_cash.isChecked():
            self._calc_cash()
        elif self.radio_mixed.isChecked():
            self._calc_mixed()

    def _calc_cash(self):
        cash = self._safe_float(self.cash_input.text())
        diff = cash - self.total_amount
        if cash == 0:
            return
        if diff < -0.001:
            self.change_label.setText(f"FALTA: Bs. {abs(diff):.2f}")
            self._style_change_label(self.change_label, err=True)
            self.change_method_group.setVisible(False)
        elif abs(diff) < 0.001:
            self.change_label.setText("MONTO EXACTO")
            self._style_change_label(self.change_label, ok=True)
            self.change_method_group.setVisible(False)
        else:
            self.change_label.setText(f"CAMBIO: Bs. {diff:.2f}")
            self._style_change_label(self.change_label, ok=True)
            self.change_method_group.setVisible(True)   # req. 4

    def _calc_mixed(self):
        cash = self._safe_float(self.mixed_cash_input.text())
        qr = self._safe_float(self.mixed_qr_input.text())
        total_given = cash + qr
        diff = total_given - self.total_amount
        if total_given == 0:
            return
        if diff < -0.001:
            self.mixed_status_label.setText(
                f"FALTA Bs. {abs(diff):.2f} (efectivo+QR = {total_given:.2f})"
            )
            self._style_change_label(self.mixed_status_label, err=True)
            self.change_method_group.setVisible(False)
        elif abs(diff) < 0.001:
            self.mixed_status_label.setText("MONTO EXACTO")
            self._style_change_label(self.mixed_status_label, ok=True)
            self.change_method_group.setVisible(False)
        else:
            self.mixed_status_label.setText(f"CAMBIO: Bs. {diff:.2f}")
            self._style_change_label(self.mixed_status_label, ok=True)
            self.change_method_group.setVisible(True)   # req. 4

    # ------------------------------------------------------------------
    #  Confirmacion
    # ------------------------------------------------------------------
    def confirm_payment(self):
        if not any([self.radio_cash.isChecked(),
                    self.radio_qr.isChecked(),
                    self.radio_mixed.isChecked()]):
            QMessageBox.warning(self, "Error", "Seleccione un metodo de pago")
            return

        if self.radio_qr.isChecked():
            self._payment_method = "QR"
            self._amount_paid = self.total_amount
            self._qr_amount = self.total_amount
            self._change = 0.0
            self._change_method = ""
            self.accept()

        elif self.radio_cash.isChecked():
            cash = self._safe_float(self.cash_input.text())
            if cash <= 0:
                QMessageBox.warning(self, "Error", "Ingrese el monto recibido")
                return
            if cash < self.total_amount - 0.001:
                QMessageBox.warning(
                    self, "Monto insuficiente",
                    f"Falta Bs. {self.total_amount - cash:.2f}"
                )
                return
            self._payment_method = "Efectivo"
            self._cash_amount = cash
            self._amount_paid = cash
            self._change = round(cash - self.total_amount, 2)
            self._change_method = (
                "Efectivo" if self.radio_change_cash.isChecked() else "QR"
            ) if self._change > 0 else ""
            self.accept()

        elif self.radio_mixed.isChecked():
            cash = self._safe_float(self.mixed_cash_input.text())
            qr = self._safe_float(self.mixed_qr_input.text())
            total_given = cash + qr
            if total_given <= 0:
                QMessageBox.warning(self, "Error", "Ingrese los montos de pago mixto")
                return
            if total_given < self.total_amount - 0.001:
                QMessageBox.warning(
                    self, "Monto insuficiente",
                    f"Efectivo+QR ({total_given:.2f}) no cubre el total ({self.total_amount:.2f})"
                )
                return
            self._payment_method = "Mixto"
            self._cash_amount = cash
            self._qr_amount = qr
            self._amount_paid = total_given
            self._change = round(total_given - self.total_amount, 2)
            self._change_method = (
                "Efectivo" if self.radio_change_cash.isChecked() else "QR"
            ) if self._change > 0 else ""
            self.accept()

    # ------------------------------------------------------------------
    #  Getters
    # ------------------------------------------------------------------
    def get_payment_method(self) -> str:
        return self._payment_method

    def get_amount_paid(self) -> float:
        return self._amount_paid

    def get_change(self) -> float:
        return self._change

    def get_cash_amount(self) -> float:
        return self._cash_amount

    def get_qr_amount(self) -> float:
        return self._qr_amount

    def get_change_method(self) -> str:
        return self._change_method
