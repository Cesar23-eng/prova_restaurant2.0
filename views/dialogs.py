# views/dialogs.py
import datetime
import html

from PyQt6.QtCore import QDate, Qt
from PyQt6.QtGui import QDoubleValidator, QFont
from PyQt6.QtWidgets import (
    QButtonGroup, QComboBox, QDateEdit, QDialog, QDialogButtonBox, QFormLayout,
    QGroupBox, QHBoxLayout, QLabel, QLineEdit, QListWidget, QMessageBox,
    QPushButton, QRadioButton, QSpinBox, QTextBrowser, QVBoxLayout,
)

from models.order import ORDER_TYPES


def money(value: float) -> str:
    return f"Bs {value:,.2f}"


class AddOrderDialog(QDialog):
    def __init__(self, parent=None, suggested_name: str = ""):
        super().__init__(parent)
        self.suggested_name = suggested_name
        self.setup_ui()

    def setup_ui(self):
        self.setWindowTitle("Nuevo Pedido")
        self.setMinimumWidth(360)
        layout = QVBoxLayout()
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(10)

        lbl_name = QLabel("Nombre de mesa/cliente:")
        lbl_name.setFont(QFont("Arial", 12))
        self.name_input = QLineEdit(self.suggested_name)
        self.name_input.setFont(QFont("Arial", 12))
        self.name_input.setPlaceholderText("Ej: Mesa 5, Juan, Terraza 2")
        self.name_input.selectAll()

        lbl_type = QLabel("Tipo de consumo:")
        lbl_type.setFont(QFont("Arial", 12))
        self.type_combo = QComboBox()
        self.type_combo.addItems(ORDER_TYPES)

        self.btn_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.btn_box.accepted.connect(self.accept)
        self.btn_box.rejected.connect(self.reject)
        self.name_input.textChanged.connect(self._validate)
        self._validate()

        layout.addWidget(lbl_name)
        layout.addWidget(self.name_input)
        layout.addWidget(lbl_type)
        layout.addWidget(self.type_combo)
        layout.addWidget(self.btn_box)
        self.setLayout(layout)

    def _validate(self):
        ok_button = self.btn_box.button(QDialogButtonBox.StandardButton.Ok)
        ok_button.setEnabled(bool(self.name_input.text().strip()))

    def get_order_name(self) -> str:
        return self.name_input.text().strip()

    def get_order_type(self) -> str:
        return self.type_combo.currentText()


class EditTableDialog(QDialog):
    def __init__(self, current_name, parent=None):
        super().__init__(parent)
        self.current_name = current_name
        self.setup_ui()

    def setup_ui(self):
        self.setWindowTitle("Editar Nombre")
        self.setMinimumWidth(350)
        layout = QVBoxLayout()
        layout.setContentsMargins(20, 20, 20, 20)
        lbl_name = QLabel("Nuevo nombre:")
        lbl_name.setFont(QFont("Arial", 12))
        self.name_input = QLineEdit(self.current_name)
        self.name_input.setFont(QFont("Arial", 12))
        self.name_input.selectAll()
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
    """Quita unidades de una linea del pedido (p. ej. 1 de los 3 tacos)."""

    def __init__(self, lines, parent=None):
        super().__init__(parent)
        self.lines = lines
        self.selected_index = None
        self.selected_count = 1
        self.setup_ui()

    def setup_ui(self):
        self.setWindowTitle("Quitar Platillo")
        self.setMinimumSize(440, 320)
        layout = QVBoxLayout()
        lbl = QLabel("Selecciona el platillo a quitar:")
        lbl.setFont(QFont("Arial", 12))
        self.list_widget = QListWidget()
        self.list_widget.setFont(QFont("Arial", 11))
        for line in self.lines:
            text = f"{line['qty']}x {line['dish']} ({line['variant']}) - {money(line['subtotal'])}"
            if line["note"]:
                text += f"   [{line['note']}]"
            self.list_widget.addItem(text)
        self.list_widget.currentRowChanged.connect(self._on_row_changed)
        self.list_widget.itemDoubleClicked.connect(lambda _: self.on_delete_clicked())

        qty_row = QHBoxLayout()
        qty_row.addWidget(QLabel("Cantidad a quitar:"))
        self.count_spin = QSpinBox()
        self.count_spin.setRange(1, 1)
        qty_row.addWidget(self.count_spin)
        qty_row.addStretch()

        btn_eliminar = QPushButton("Quitar seleccion")
        btn_eliminar.setObjectName("dangerButton")
        btn_eliminar.clicked.connect(self.on_delete_clicked)
        layout.addWidget(lbl)
        layout.addWidget(self.list_widget)
        layout.addLayout(qty_row)
        layout.addWidget(btn_eliminar)
        self.setLayout(layout)
        if self.lines:
            self.list_widget.setCurrentRow(len(self.lines) - 1)

    def _on_row_changed(self, row: int):
        if 0 <= row < len(self.lines):
            self.count_spin.setRange(1, self.lines[row]["qty"])
            self.count_spin.setValue(1)

    def on_delete_clicked(self):
        row = self.list_widget.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Error", "Selecciona un platillo primero")
            return
        self.selected_index = row
        self.selected_count = self.count_spin.value()
        self.accept()

    def get_selected_index(self):
        return self.selected_index

    def get_selected_count(self) -> int:
        return self.selected_count


# ---------------------------------------------------------------------------
#  DeliveryDialog
# ---------------------------------------------------------------------------
class DeliveryDialog(QDialog):
    def __init__(self, parent=None, current=None):
        super().__init__(parent)
        current = current or {}
        self._moto_cost = float(current.get("moto_cost") or 0)
        self._moto_method = current.get("moto_payment_method") or "Efectivo"
        self._has_current = bool(current)
        self.setWindowTitle("Detalles de Delivery")
        self.setMinimumWidth(400)
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

        self.moto_cost_input = QLineEdit()
        self.moto_cost_input.setPlaceholderText("Vacio o 0 si el cliente recoge en el local")
        validator = QDoubleValidator(0.00, 9999.99, 2)
        validator.setNotation(QDoubleValidator.Notation.StandardNotation)
        self.moto_cost_input.setValidator(validator)
        if self._has_current:
            self.moto_cost_input.setText(f"{self._moto_cost:g}")
        form.addRow("Costo de la moto (Bs):", self.moto_cost_input)

        self.moto_method_combo = QComboBox()
        self.moto_method_combo.addItems(["Efectivo", "QR"])
        self.moto_method_combo.setCurrentText(self._moto_method)
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
        text = self.moto_cost_input.text().strip().replace(",", ".")
        try:
            self._moto_cost = float(text) if text else 0.0
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
#  PaymentDialog
# ---------------------------------------------------------------------------
class PaymentDialog(QDialog):
    QUICK_BILLS = (50, 100, 200)

    def __init__(self, parent=None, total: float = None):
        super().__init__(parent)
        self._payment_method = ""
        self._amount_paid = 0.0
        self._change = 0.0
        self._cash_amount = 0.0
        self._qr_amount = 0.0
        self._change_method = ""
        self.total_amount = 0.0

        if total is not None:
            self.total_amount = float(total)
        elif hasattr(parent, "order_manager") and parent.order_manager.current_table:
            self.total_amount = parent.order_manager.get_total(parent.order_manager.current_table)

        self.setWindowTitle("Registrar Pago")
        self.setMinimumWidth(480)
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout()
        layout.setSpacing(16)
        layout.setContentsMargins(20, 20, 20, 20)

        total_label = QLabel(f"<h2>Total a pagar: Bs. {self.total_amount:.2f}</h2>")
        total_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        total_label.setStyleSheet("color: #2196F3; font-weight: bold;")
        layout.addWidget(total_label)

        method_group = QGroupBox("Metodo de Pago")
        method_group.setStyleSheet("QGroupBox { font-weight: bold; }")
        method_layout = QHBoxLayout()

        self.btn_group = QButtonGroup(self)
        self.radio_cash = QRadioButton("Efectivo (F1)")
        self.radio_qr = QRadioButton("QR / Transferencia (F2)")
        self.radio_mixed = QRadioButton("Mixto (F3)")

        for r in [self.radio_cash, self.radio_qr, self.radio_mixed]:
            r.setStyleSheet("font-size: 13px;")
            self.btn_group.addButton(r)
            method_layout.addWidget(r)

        method_group.setLayout(method_layout)
        layout.addWidget(method_group)

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

        quick_row = QHBoxLayout()
        exact_btn = QPushButton("Monto exacto")
        exact_btn.clicked.connect(lambda: self.cash_input.setText(f"{self.total_amount:.2f}"))
        quick_row.addWidget(exact_btn)
        for bill in self.QUICK_BILLS:
            if bill < self.total_amount:
                continue
            btn = QPushButton(f"Bs {bill}")
            btn.clicked.connect(lambda _, b=bill: self.cash_input.setText(str(b)))
            quick_row.addWidget(btn)
        for i in range(quick_row.count()):
            quick_row.itemAt(i).widget().setStyleSheet(self._btn_style("#607D8B", "#455A64"))
            quick_row.itemAt(i).widget().setAutoDefault(False)
        cash_layout.addLayout(quick_row)

        self.change_label = QLabel("")
        self.change_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._style_change_label(self.change_label, neutral=True)
        cash_layout.addWidget(self.change_label)
        self.cash_section.setLayout(cash_layout)
        self.cash_section.setVisible(False)
        layout.addWidget(self.cash_section)

        self.qr_section = QGroupBox("QR / Transferencia")
        self.qr_section.setStyleSheet("QGroupBox { font-weight: bold; color: #2196F3; }")
        qr_layout = QVBoxLayout()
        qr_info = QLabel(f"Se registrara pago de Bs. {self.total_amount:.2f} por QR.\n"
                         f"Verifica que la transferencia llego antes de confirmar.")
        qr_info.setStyleSheet("font-size: 13px; color: #2196F3;")
        qr_layout.addWidget(qr_info)
        self.qr_section.setLayout(qr_layout)
        self.qr_section.setVisible(False)
        layout.addWidget(self.qr_section)

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

        buttons_layout = QHBoxLayout()

        btn_confirm = QPushButton("Confirmar Pago")
        btn_confirm.setStyleSheet(self._btn_style("#4CAF50", "#45a049"))
        btn_confirm.clicked.connect(self.confirm_payment)
        btn_confirm.setDefault(True)

        btn_cancel = QPushButton("Cancelar")
        btn_cancel.setStyleSheet(self._btn_style("#f44336", "#da190b"))
        btn_cancel.clicked.connect(self.reject)
        btn_cancel.setAutoDefault(False)

        buttons_layout.addWidget(btn_confirm)
        buttons_layout.addWidget(btn_cancel)
        layout.addLayout(buttons_layout)
        self.setLayout(layout)

        self.radio_cash.toggled.connect(self._update_sections)
        self.radio_qr.toggled.connect(self._update_sections)
        self.radio_mixed.toggled.connect(self._update_sections)
        self.cash_input.textChanged.connect(self._auto_calculate)
        self.mixed_cash_input.textChanged.connect(self._auto_calculate)
        self.mixed_qr_input.textChanged.connect(self._auto_calculate)

    def keyPressEvent(self, event):
        shortcuts = {
            Qt.Key.Key_F1: self.radio_cash,
            Qt.Key.Key_F2: self.radio_qr,
            Qt.Key.Key_F3: self.radio_mixed,
        }
        radio = shortcuts.get(event.key())
        if radio is not None:
            radio.setChecked(True)
            return
        super().keyPressEvent(event)

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
            return float((text or "").strip().replace(",", "."))
        except ValueError:
            return 0.0

    def _update_sections(self):
        is_cash = self.radio_cash.isChecked()
        is_qr = self.radio_qr.isChecked()
        is_mixed = self.radio_mixed.isChecked()
        self.cash_section.setVisible(is_cash)
        self.qr_section.setVisible(is_qr)
        self.mixed_section.setVisible(is_mixed)
        if not is_cash:
            self.cash_input.clear()
            self.change_label.setText("")
        if not is_mixed:
            self.mixed_cash_input.clear()
            self.mixed_qr_input.clear()
            self.mixed_status_label.setText("")
        self.change_method_group.setVisible(False)
        if is_cash:
            self.cash_input.setFocus()
        elif is_mixed:
            self.mixed_cash_input.setFocus()
        self.adjustSize()

    def _auto_calculate(self):
        if self.radio_cash.isChecked() or self.radio_mixed.isChecked():
            self.calculate()

    def calculate(self):
        if self.radio_cash.isChecked():
            self._calc_cash()
        elif self.radio_mixed.isChecked():
            self._calc_mixed()

    def _show_difference(self, label, given: float, prefix: str = ""):
        diff = given - self.total_amount
        if given == 0:
            label.setText("")
            self._style_change_label(label, neutral=True)
            self.change_method_group.setVisible(False)
        elif diff < -0.001:
            label.setText(f"FALTA: Bs. {abs(diff):.2f}{prefix}")
            self._style_change_label(label, err=True)
            self.change_method_group.setVisible(False)
        elif abs(diff) < 0.001:
            label.setText("MONTO EXACTO")
            self._style_change_label(label, ok=True)
            self.change_method_group.setVisible(False)
        else:
            label.setText(f"CAMBIO: Bs. {diff:.2f}")
            self._style_change_label(label, ok=True)
            self.change_method_group.setVisible(True)

    def _calc_cash(self):
        self._show_difference(self.change_label, self._safe_float(self.cash_input.text()))

    def _calc_mixed(self):
        cash = self._safe_float(self.mixed_cash_input.text())
        qr = self._safe_float(self.mixed_qr_input.text())
        self._show_difference(self.mixed_status_label, cash + qr,
                              f" (efectivo+QR = {cash + qr:.2f})")

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
            self._cash_amount = 0.0
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
            self._qr_amount = 0.0
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


# ---------------------------------------------------------------------------
#  Resumen del dia / cierre de caja
# ---------------------------------------------------------------------------
def day_summary_html(summary: dict, date_label: str, local_name: str) -> str:
    def row(label, value, bold=False):
        open_b, close_b = ("<b>", "</b>") if bold else ("", "")
        return (f"<tr><td style='padding:2px 0'>{open_b}{html.escape(label)}{close_b}</td>"
                f"<td align='right' style='padding:2px 0'>{open_b}{html.escape(str(value))}{close_b}</td></tr>")

    def section(title):
        return (f"<tr><td colspan='2' style='padding:12px 0 2px 0'>"
                f"<b style='font-size:13px'>{html.escape(title)}</b></td></tr>")

    parts = [
        f"<h2 style='margin-bottom:0'>{html.escape(local_name)}</h2>",
        f"<h3 style='margin-top:4px'>Cierre de caja - {html.escape(date_label)}</h3>",
    ]
    if not summary["orders"]:
        parts.append("<p>No hay ventas cobradas en esta jornada.</p>")
        return "".join(parts)

    parts.append("<table width='100%' cellspacing='0' cellpadding='0'>")
    parts.append(row("Pedidos cobrados", summary["orders"]))
    parts.append(row("Total vendido", money(summary["total"]), bold=True))
    parts.append(row("Ticket promedio", money(summary["average_ticket"])))
    parts.append(row("Horario de ventas", f"{summary['first_time']} a {summary['last_time']}"))
    parts.append(section("Caja"))
    parts.append(row("Efectivo neto en caja", money(summary["cash_net"]), bold=True))
    parts.append(row("QR neto", money(summary["qr_net"]), bold=True))
    parts.append(row("Cambio dado en efectivo", money(summary["change_cash"])))
    parts.append(row("Cambio dado por QR", money(summary["change_qr"])))
    if summary["moto_orders"]:
        parts.append(row(f"Motos ({summary['moto_orders']} envios) en efectivo", money(summary["moto_cash"])))
        parts.append(row("Motos por QR", money(summary["moto_qr"])))
    parts.append(section("Por metodo de pago"))
    for method, data in summary["by_method"].items():
        parts.append(row(f"{method} ({data['orders']})", money(data["total"])))
    parts.append(section("Por tipo de consumo"))
    for order_type, data in summary["by_type"].items():
        parts.append(row(f"{order_type} ({data['orders']})", money(data["total"])))
    parts.append(section("Productos vendidos"))
    for product in summary["products"]:
        parts.append(row(f"{product['qty']}x {product['product']}", money(product["amount"])))
    parts.append("</table>")
    return "".join(parts)


class DaySummaryDialog(QDialog):
    def __init__(self, order_manager, local_name: str, parent=None):
        super().__init__(parent)
        self.order_manager = order_manager
        self.local_name = local_name
        self.setWindowTitle("Resumen del dia")
        self.resize(520, 680)
        self.setup_ui()
        self.refresh()

    def setup_ui(self):
        layout = QVBoxLayout()

        date_row = QHBoxLayout()
        date_row.addWidget(QLabel("Jornada:"))
        today = self.order_manager.today()
        self.date_edit = QDateEdit(QDate(today.year, today.month, today.day))
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDisplayFormat("dd/MM/yyyy")
        self.date_edit.setMaximumDate(QDate(today.year, today.month, today.day))
        self.date_edit.dateChanged.connect(self.refresh)
        date_row.addWidget(self.date_edit)
        date_row.addStretch()
        layout.addLayout(date_row)

        self.browser = QTextBrowser()
        self.browser.setFont(QFont("Arial", 11))
        layout.addWidget(self.browser)

        buttons = QHBoxLayout()
        self.print_btn = QPushButton("Imprimir")
        self.print_btn.setObjectName("secondaryButton")
        self.print_btn.clicked.connect(self.print_summary)
        self.excel_btn = QPushButton("Abrir Excel")
        self.excel_btn.setObjectName("accentButton")
        self.excel_btn.clicked.connect(self.open_excel)
        close_btn = QPushButton("Cerrar")
        close_btn.setObjectName("primaryButton")
        close_btn.clicked.connect(self.accept)
        for btn in (self.print_btn, self.excel_btn, close_btn):
            buttons.addWidget(btn)
        layout.addLayout(buttons)
        self.setLayout(layout)

    def selected_date(self) -> datetime.date:
        return self.date_edit.date().toPyDate()

    def refresh(self):
        date = self.selected_date()
        self.summary = self.order_manager.day_summary(date)
        self.html = day_summary_html(self.summary, date.strftime("%d/%m/%Y"), self.local_name)
        self.browser.setHtml(self.html)

    def print_summary(self):
        parent = self.parent()
        if parent is not None and hasattr(parent, "print_html"):
            parent.print_html(self.html)

    def open_excel(self):
        import os
        from PyQt6.QtCore import QUrl
        from PyQt6.QtGui import QDesktopServices

        date = self.selected_date()
        if self.summary["orders"]:
            self.order_manager.refresh_daily_excel(date)
        path = self.order_manager.daily_excel_path(date)
        if not os.path.exists(path):
            QMessageBox.information(self, "Sin Excel", "No hay Excel de ventas para esa jornada.")
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(path))
