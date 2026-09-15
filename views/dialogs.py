# views/dialogs.py
import datetime
import html
import math
import os

from PyQt6.QtCore import QDate, Qt, QUrl
from PyQt6.QtGui import QDesktopServices, QDoubleValidator
from PyQt6.QtWidgets import (
    QButtonGroup, QComboBox, QDateEdit, QDialog, QFrame, QGridLayout, QHBoxLayout, QLabel,
    QLineEdit, QListWidget, QListWidgetItem, QMessageBox, QPushButton, QSpinBox, QTextBrowser,
    QVBoxLayout,
)

from models.order import MAX_PLATES, ORDER_TYPE_LOCAL, ORDER_TYPE_TAKEAWAY, group_lines_by_plate, plate_label
from utils import tickets
from utils.config import save_config_value
from utils.printer import (
    PrinterError, TicketPrinter, available_printers, default_printer, looks_thermal,
)
from views.widgets import make_button, make_label, money, repolish, set_prop


def _dialog_layout(dialog: QDialog, title: str, subtitle: str = "") -> QVBoxLayout:
    layout = QVBoxLayout(dialog)
    layout.setContentsMargins(24, 20, 24, 20)
    layout.setSpacing(12)
    layout.addWidget(make_label(title, "panelTitle"))
    if subtitle:
        layout.addWidget(make_label(subtitle, "muted", wrap=True))
    return layout


def _segmented(options, checked, object_name="segment"):
    """Botones alternables tipo interruptor. Devuelve (layout, grupo, {valor: boton})."""
    row = QHBoxLayout()
    row.setSpacing(8)
    group = QButtonGroup()
    group.setExclusive(True)
    buttons = {}
    for value, text in options:
        button = make_button(text, object_name)
        button.setCheckable(True)
        button.setChecked(value == checked)
        group.addButton(button)
        row.addWidget(button, 1)
        buttons[value] = button
    return row, group, buttons


# ---------------------------------------------------------------------------
#  Nuevo pedido
# ---------------------------------------------------------------------------
class AddOrderDialog(QDialog):
    """Crear pedido: un toque en el numero de mesa o el nombre del cliente para llevar."""

    def __init__(self, parent=None, suggested_name: str = "", occupied=None, table_count: int = 13):
        super().__init__(parent)
        self.suggested_name = suggested_name
        self.occupied = {name.lower() for name in (occupied or [])}
        self.table_count = max(0, int(table_count))
        self.setWindowTitle("Nuevo pedido")
        self.setMinimumWidth(460)
        self.setup_ui()

    def setup_ui(self):
        layout = _dialog_layout(self, "NUEVO PEDIDO", "Elige una mesa o escribe el nombre del cliente.")

        row, self.type_group, self.type_buttons = _segmented(
            [(ORDER_TYPE_LOCAL, "\U0001F37D  En el local"), (ORDER_TYPE_TAKEAWAY, "\U0001F6F5  Para llevar")],
            ORDER_TYPE_LOCAL)
        self.type_group.setParent(self)
        layout.addLayout(row)

        if self.table_count:
            grid = QGridLayout()
            grid.setSpacing(8)
            columns = 5 if self.table_count > 8 else 4
            self.table_buttons = {}
            for i in range(self.table_count):
                name = f"Mesa {i + 1}"
                button = make_button(name, "chip")
                busy = name.lower() in self.occupied
                button.setEnabled(not busy)
                button.setToolTip("Mesa ocupada" if busy else f"Crear pedido para {name}")
                button.clicked.connect(lambda _c=False, n=name: self._pick_table(n))
                grid.addWidget(button, i // columns, i % columns)
                self.table_buttons[name] = button
            layout.addLayout(grid)

        layout.addWidget(make_label("Nombre de mesa o cliente", "muted"))
        self.name_input = QLineEdit(self.suggested_name)
        self.name_input.setPlaceholderText("Ej: Mesa 5, Juan, Terraza 2")
        self.name_input.selectAll()
        self.name_input.returnPressed.connect(self._accept_if_valid)
        layout.addWidget(self.name_input)

        buttons = QHBoxLayout()
        buttons.addWidget(make_button("Cancelar", "ghostButton", self.reject))
        self.ok_button = make_button("Crear pedido", "primaryButton", self._accept_if_valid)
        self.ok_button.setDefault(True)
        buttons.addWidget(self.ok_button, 1)
        layout.addLayout(buttons)
        self.name_input.textChanged.connect(self._validate)
        self._validate()

    def _pick_table(self, name: str):
        self.name_input.setText(name)
        self.type_buttons[ORDER_TYPE_LOCAL].setChecked(True)
        self.accept()

    def _validate(self):
        self.ok_button.setEnabled(bool(self.name_input.text().strip()))

    def _accept_if_valid(self):
        if self.name_input.text().strip():
            self.accept()

    def get_order_name(self) -> str:
        return self.name_input.text().strip()

    def get_order_type(self) -> str:
        for value, button in self.type_buttons.items():
            if button.isChecked():
                return value
        return ORDER_TYPE_LOCAL


class EditTableDialog(QDialog):
    def __init__(self, current_name, parent=None):
        super().__init__(parent)
        self.current_name = current_name
        self.setWindowTitle("Renombrar pedido")
        self.setMinimumWidth(380)
        layout = _dialog_layout(self, "RENOMBRAR PEDIDO")
        self.name_input = QLineEdit(self.current_name)
        self.name_input.selectAll()
        self.name_input.returnPressed.connect(self.accept)
        layout.addWidget(self.name_input)
        buttons = QHBoxLayout()
        buttons.addWidget(make_button("Cancelar", "ghostButton", self.reject))
        ok = make_button("Guardar", "primaryButton", self.accept)
        ok.setDefault(True)
        buttons.addWidget(ok, 1)
        layout.addLayout(buttons)

    def get_new_name(self) -> str:
        return self.name_input.text().strip()


# ---------------------------------------------------------------------------
#  PlateDialog
# ---------------------------------------------------------------------------
class PlateDialog(QDialog):
    """
    Reparte los platillos de un pedido en platos. Los tacos se piden por unidad:
    si dos personas de la misma mesa piden tacos, cocina necesita saber cuales
    van juntos en cada plato.
    """

    def __init__(self, order_manager, table: str, parent=None):
        super().__init__(parent)
        self.order_manager = order_manager
        self.table = table
        self.lines = []
        self.setWindowTitle(f"Platos - {table}")
        self.setMinimumSize(540, 500)
        self.setup_ui()
        self.refresh()

    def setup_ui(self):
        layout = _dialog_layout(
            self, "REPARTIR EN PLATOS",
            "Selecciona un platillo, elige cuántas unidades y a qué plato van. "
            "Ejemplo: de 3 tacos con queso, 2 al Plato 1 y 1 al Plato 2.")

        self.list_widget = QListWidget()
        self.list_widget.currentItemChanged.connect(lambda *_: self._on_selection())
        layout.addWidget(self.list_widget, 1)

        move_row = QHBoxLayout()
        move_row.addWidget(make_label("Cantidad", "muted"))
        self.count_spin = QSpinBox()
        self.count_spin.setRange(1, 1)
        move_row.addWidget(self.count_spin)
        move_row.addWidget(make_label("Mover a", "muted"))
        self.target_combo = QComboBox()
        self.target_combo.setMinimumWidth(150)
        move_row.addWidget(self.target_combo, 1)
        self.move_btn = make_button("Mover", "primaryButton", self.move_selected)
        move_row.addWidget(self.move_btn)
        layout.addLayout(move_row)

        self.status_label = make_label("", "hint", wrap=True)
        layout.addWidget(self.status_label)
        layout.addWidget(make_button("Listo", "successButton", self.accept))

    def refresh(self, select_key=None):
        self.lines = self.order_manager.get_order_lines(self.table)
        used = self.order_manager.used_plates(self.table)
        self.list_widget.blockSignals(True)
        self.list_widget.clear()
        to_select = None
        indexed = [dict(line, index=i) for i, line in enumerate(self.lines)]
        for plate, plate_lines in group_lines_by_plate(indexed):
            title = f"\U0001F37D  {plate_label(plate)}" if plate else "Sin plato"
            header = QListWidgetItem(title.upper())
            font = header.font()
            font.setBold(True)
            header.setFont(font)
            header.setFlags(Qt.ItemFlag.NoItemFlags)
            self.list_widget.addItem(header)
            for line in plate_lines:
                text = f"      {line['qty']}x  {line['dish']} ({line['variant']})"
                if line["note"]:
                    text += f"   \U0001F4DD {line['note']}"
                item = QListWidgetItem(text)
                item.setData(Qt.ItemDataRole.UserRole, line["index"])
                self.list_widget.addItem(item)
                key = (line["dish"], line["variant"], line["note"], line["plate"])
                if to_select is None or key == select_key:
                    to_select = item
        self.list_widget.blockSignals(False)

        current_target = self.target_combo.currentData()
        top = min(max(used + [0]) + 1, MAX_PLATES)
        self.target_combo.clear()
        self.target_combo.addItem("Sin plato", 0)
        for plate in range(1, top + 1):
            self.target_combo.addItem(plate_label(plate) + ("" if plate in used else "  (nuevo)"), plate)
        if current_target is not None and self.target_combo.findData(current_target) >= 0:
            self.target_combo.setCurrentIndex(self.target_combo.findData(current_target))
        else:
            self.target_combo.setCurrentIndex(self.target_combo.count() - 1)

        if to_select is not None:
            self.list_widget.setCurrentItem(to_select)
        self._on_selection()

    def selected_index(self):
        item = self.list_widget.currentItem()
        return None if item is None else item.data(Qt.ItemDataRole.UserRole)

    def selected_line(self):
        index = self.selected_index()
        return None if index is None else self.lines[index]

    def _on_selection(self):
        line = self.selected_line()
        enabled = line is not None and self.order_manager.plate_applies(line["dish"])
        self.count_spin.setEnabled(enabled)
        self.target_combo.setEnabled(enabled)
        self.move_btn.setEnabled(enabled)
        if line is None:
            return
        self.count_spin.setRange(1, line["qty"])
        self.count_spin.setValue(line["qty"])
        if not enabled:
            self.status_label.setText(f"{line['dish']} va sin plato: solo los tacos se reparten.")

    def move_selected(self):
        index = self.selected_index()
        if index is None:
            return
        line = self.lines[index]
        target = self.target_combo.currentData()
        try:
            moved, already_sent = self.order_manager.move_line_to_plate(
                self.table, index, target, self.count_spin.value())
        except (KeyError, ValueError, PermissionError) as e:
            QMessageBox.warning(self, "No se pudo mover", str(e))
            return
        if not moved:
            self.status_label.setText("Ese platillo ya está en ese plato.")
            return
        text = f"{moved}x {line['dish']} ({line['variant']}) movido(s) al {plate_label(target)}."
        if already_sent:
            text += (f" {already_sent} ya habían salido en una comanda: avisa a cocina "
                     f"o reimprime la comanda completa.")
        self.status_label.setText(text)
        self.refresh(select_key=(line["dish"], line["variant"], line["note"], target))


# ---------------------------------------------------------------------------
#  Delivery
# ---------------------------------------------------------------------------
class DeliveryDialog(QDialog):
    QUICK_COSTS = (0, 5, 10, 15, 20)

    def __init__(self, parent=None, current=None):
        super().__init__(parent)
        current = current or {}
        self._moto_cost = float(current.get("moto_cost") or 0)
        self._moto_method = current.get("moto_payment_method") or "Efectivo"
        self._has_current = bool(current)
        self.setWindowTitle("Pedido para llevar")
        self.setMinimumWidth(440)
        self.setup_ui()

    def setup_ui(self):
        layout = _dialog_layout(self, "\U0001F6F5  PARA LLEVAR",
                                "Costo de la moto. Deja 0 si el cliente recoge en el local.")
        quick = QHBoxLayout()
        quick.setSpacing(8)
        for cost in self.QUICK_COSTS:
            text = "Recoge" if cost == 0 else f"Bs {cost}"
            button = make_button(text, "quickAmount")
            button.setAutoDefault(False)
            button.clicked.connect(lambda _c=False, c=cost: self.moto_cost_input.setText(str(c)))
            quick.addWidget(button, 1)
        layout.addLayout(quick)

        self.moto_cost_input = QLineEdit()
        self.moto_cost_input.setObjectName("bigInput")
        self.moto_cost_input.setPlaceholderText("0")
        validator = QDoubleValidator(0.00, 9999.99, 2)
        validator.setNotation(QDoubleValidator.Notation.StandardNotation)
        self.moto_cost_input.setValidator(validator)
        if self._has_current:
            self.moto_cost_input.setText(f"{self._moto_cost:g}")
        layout.addWidget(self.moto_cost_input)

        layout.addWidget(make_label("La moto se paga en", "muted"))
        row, self.method_group, self.method_buttons = _segmented(
            [("Efectivo", "\U0001F4B5  Efectivo"), ("QR", "\U0001F4F1  QR")], self._moto_method)
        self.method_group.setParent(self)
        layout.addLayout(row)

        buttons = QHBoxLayout()
        buttons.addWidget(make_button("Cancelar", "ghostButton", self.reject))
        ok = make_button("Continuar al cobro", "primaryButton", self._on_accept)
        ok.setDefault(True)
        buttons.addWidget(ok, 1)
        layout.addLayout(buttons)

    def _on_accept(self):
        text = self.moto_cost_input.text().strip().replace(",", ".")
        try:
            self._moto_cost = float(text) if text else 0.0
        except ValueError:
            QMessageBox.warning(self, "Valor inválido", "Ingresa un número válido.")
            return
        self._moto_method = "QR" if self.method_buttons["QR"].isChecked() else "Efectivo"
        self.accept()

    def get_moto_cost(self) -> float:
        return self._moto_cost

    def get_moto_method(self) -> str:
        return self._moto_method


# ---------------------------------------------------------------------------
#  Cobro
# ---------------------------------------------------------------------------
class PaymentDialog(QDialog):
    """
    Cobro pensado para la hora pico: el metodo con un toque (o F1/F2/F3), montos
    rapidos y el cambio en grande para no equivocarse al darlo.
    """

    def __init__(self, parent=None, total: float = None, title: str = ""):
        super().__init__(parent)
        self._payment_method = ""
        self._amount_paid = 0.0
        self._change = 0.0
        self._cash_amount = 0.0
        self._qr_amount = 0.0
        self._change_method = ""
        self.total_amount = 0.0
        self.order_title = title

        if total is not None:
            self.total_amount = float(total)
        elif hasattr(parent, "order_manager") and parent.order_manager.current_table:
            self.total_amount = parent.order_manager.get_total(parent.order_manager.current_table)

        self.setWindowTitle("Cobrar")
        self.setMinimumWidth(520)
        self.setup_ui()

    @staticmethod
    def quick_amounts(total: float):
        """Monto exacto, la siguiente decena y billetes que cubren el total."""
        amounts = [round(total, 2)]
        for candidate in (math.ceil(total / 10) * 10, 50, 100, 200):
            if candidate > total and candidate not in amounts:
                amounts.append(candidate)
        return amounts[:4]

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(12)

        header = QHBoxLayout()
        header.addWidget(make_label("COBRAR", "panelTitle"))
        if self.order_title:
            header.addWidget(make_label(self.order_title, "muted"))
        header.addStretch()
        layout.addLayout(header)
        total = make_label(money(self.total_amount), "totalAmount")
        total.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(total)

        methods = QHBoxLayout()
        methods.setSpacing(10)
        self.btn_group = QButtonGroup(self)
        self.radio_cash = self._method_button("\U0001F4B5  Efectivo\nF1", "cash")
        self.radio_qr = self._method_button("\U0001F4F1  QR\nF2", "qr")
        self.radio_mixed = self._method_button("\U0001F500  Mixto\nF3", "mixed")
        for button in (self.radio_cash, self.radio_qr, self.radio_mixed):
            self.btn_group.addButton(button)
            methods.addWidget(button, 1)
        layout.addLayout(methods)

        # --- Efectivo ---
        self.cash_section = QFrame()
        cash_layout = QVBoxLayout(self.cash_section)
        cash_layout.setContentsMargins(0, 0, 0, 0)
        cash_layout.setSpacing(8)
        cash_layout.addWidget(make_label("Recibido del cliente", "muted"))
        self.cash_input = self._amount_input("0")
        cash_layout.addWidget(self.cash_input)
        quick = QHBoxLayout()
        quick.setSpacing(8)
        for amount in self.quick_amounts(self.total_amount):
            text = "Exacto" if amount == round(self.total_amount, 2) else f"Bs {amount:g}"
            button = make_button(text, "quickAmount")
            button.setAutoDefault(False)
            button.clicked.connect(lambda _c=False, a=amount: self.cash_input.setText(f"{a:g}"))
            quick.addWidget(button, 1)
        cash_layout.addLayout(quick)
        self.change_label = make_label("", "resultBox")
        self.change_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        cash_layout.addWidget(self.change_label)
        self.cash_section.setVisible(False)
        layout.addWidget(self.cash_section)

        # --- QR ---
        self.qr_section = QFrame()
        qr_layout = QVBoxLayout(self.qr_section)
        qr_layout.setContentsMargins(0, 0, 0, 0)
        info = make_label(f"Se registra {money(self.total_amount)} por QR.\n"
                          f"Verifica en el celular que la transferencia llegó.", "resultBox")
        info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        info.setProperty("state", "ok")
        qr_layout.addWidget(info)
        self.qr_section.setVisible(False)
        layout.addWidget(self.qr_section)

        # --- Mixto ---
        self.mixed_section = QFrame()
        mixed_layout = QGridLayout(self.mixed_section)
        mixed_layout.setContentsMargins(0, 0, 0, 0)
        mixed_layout.setHorizontalSpacing(10)
        mixed_layout.addWidget(make_label("Efectivo", "muted"), 0, 0)
        mixed_layout.addWidget(make_label("QR", "muted"), 0, 1)
        self.mixed_cash_input = self._amount_input("0")
        self.mixed_qr_input = self._amount_input("0")
        mixed_layout.addWidget(self.mixed_cash_input, 1, 0)
        mixed_layout.addWidget(self.mixed_qr_input, 1, 1)
        fill_qr = make_button("Completar el resto con QR", "secondaryButton", self._fill_rest_with_qr)
        fill_qr.setAutoDefault(False)
        mixed_layout.addWidget(fill_qr, 2, 0, 1, 2)
        self.mixed_status_label = make_label("", "resultBox")
        self.mixed_status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        mixed_layout.addWidget(self.mixed_status_label, 3, 0, 1, 2)
        self.mixed_section.setVisible(False)
        layout.addWidget(self.mixed_section)

        # --- Cambio ---
        self.change_method_group = QFrame()
        change_layout = QHBoxLayout(self.change_method_group)
        change_layout.setContentsMargins(0, 0, 0, 0)
        change_layout.addWidget(make_label("Cambio en", "muted"))
        self.btn_group_change = QButtonGroup(self)
        self.radio_change_cash = make_button("\U0001F4B5  Efectivo", "segment")
        self.radio_change_qr = make_button("\U0001F4F1  QR", "segment")
        self.radio_change_cash.setProperty("method", "cash")
        self.radio_change_qr.setProperty("method", "qr")
        for button in (self.radio_change_cash, self.radio_change_qr):
            button.setCheckable(True)
            button.setAutoDefault(False)
            self.btn_group_change.addButton(button)
            change_layout.addWidget(button, 1)
        self.radio_change_cash.setChecked(True)
        self.change_method_group.setVisible(False)
        layout.addWidget(self.change_method_group)

        buttons = QHBoxLayout()
        cancel = make_button("Cancelar", "ghostButton", self.reject)
        cancel.setAutoDefault(False)
        buttons.addWidget(cancel)
        self.confirm_button = make_button("Confirmar cobro  ⏎", "payButton", self.confirm_payment)
        self.confirm_button.setDefault(True)
        buttons.addWidget(self.confirm_button, 1)
        layout.addLayout(buttons)

        self.radio_cash.toggled.connect(self._update_sections)
        self.radio_qr.toggled.connect(self._update_sections)
        self.radio_mixed.toggled.connect(self._update_sections)
        self.cash_input.textChanged.connect(self._auto_calculate)
        self.mixed_cash_input.textChanged.connect(self._auto_calculate)
        self.mixed_qr_input.textChanged.connect(self._auto_calculate)

    def _method_button(self, text: str, method: str) -> QPushButton:
        button = make_button(text, "methodButton")
        button.setProperty("method", method)
        button.setCheckable(True)
        button.setAutoDefault(False)
        return button

    def _amount_input(self, placeholder: str) -> QLineEdit:
        field = QLineEdit()
        field.setObjectName("bigInput")
        field.setPlaceholderText(placeholder)
        validator = QDoubleValidator(0.00, 999999.99, 2)
        validator.setNotation(QDoubleValidator.Notation.StandardNotation)
        field.setValidator(validator)
        return field

    def keyPressEvent(self, event):
        shortcuts = {
            Qt.Key.Key_F1: self.radio_cash,
            Qt.Key.Key_F2: self.radio_qr,
            Qt.Key.Key_F3: self.radio_mixed,
        }
        button = shortcuts.get(event.key())
        if button is not None:
            button.setChecked(True)
            return
        super().keyPressEvent(event)

    @staticmethod
    def _safe_float(text: str) -> float:
        try:
            return float((text or "").strip().replace(",", "."))
        except ValueError:
            return 0.0

    def _fill_rest_with_qr(self):
        cash = self._safe_float(self.mixed_cash_input.text())
        rest = max(0.0, round(self.total_amount - cash, 2))
        self.mixed_qr_input.setText(f"{rest:g}")

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
            self._calc_cash()
        elif is_mixed:
            self.mixed_cash_input.setFocus()
            self._calc_mixed()
        self.adjustSize()

    def _auto_calculate(self):
        if self.radio_cash.isChecked() or self.radio_mixed.isChecked():
            self.calculate()

    def calculate(self):
        if self.radio_cash.isChecked():
            self._calc_cash()
        elif self.radio_mixed.isChecked():
            self._calc_mixed()

    def _show_difference(self, label, given: float, suffix: str = ""):
        diff = given - self.total_amount
        if given == 0:
            label.setText("Ingresa el monto")
            state = ""
            show_change = False
        elif diff < -0.001:
            label.setText(f"FALTA  {money(abs(diff))}{suffix}")
            state, show_change = "missing", False
        elif abs(diff) < 0.001:
            label.setText("MONTO EXACTO")
            state, show_change = "ok", False
        else:
            label.setText(f"CAMBIO  {money(diff)}")
            state, show_change = "change", True
        set_prop(label, "state", state)
        self.change_method_group.setVisible(show_change)

    def _calc_cash(self):
        self._show_difference(self.change_label, self._safe_float(self.cash_input.text()))

    def _calc_mixed(self):
        cash = self._safe_float(self.mixed_cash_input.text())
        qr = self._safe_float(self.mixed_qr_input.text())
        self._show_difference(self.mixed_status_label, cash + qr,
                              f"  (efectivo + QR = {money(cash + qr)})")

    def confirm_payment(self):
        if not any([self.radio_cash.isChecked(),
                    self.radio_qr.isChecked(),
                    self.radio_mixed.isChecked()]):
            QMessageBox.warning(self, "Método de pago", "Elige Efectivo, QR o Mixto.")
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
                QMessageBox.warning(self, "Monto", "Ingresa el monto recibido.")
                return
            if cash < self.total_amount - 0.001:
                QMessageBox.warning(self, "Monto insuficiente",
                                    f"Falta {money(self.total_amount - cash)}")
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
                QMessageBox.warning(self, "Monto", "Ingresa los montos del pago mixto.")
                return
            if total_given < self.total_amount - 0.001:
                QMessageBox.warning(
                    self, "Monto insuficiente",
                    f"Efectivo + QR ({money(total_given)}) no cubre el total ({money(self.total_amount)})")
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
def day_summary_html(summary: dict, date_label: str, local_name: str, colors: dict = None) -> str:
    """HTML del cierre. Sin `colors` sale en blanco y negro para la impresora."""
    heading = colors["accent"] if colors else "#000000"
    muted = colors["muted"] if colors else "#555555"

    def row(label, value, bold=False):
        open_b, close_b = ("<b>", "</b>") if bold else ("", "")
        return (f"<tr><td style='padding:3px 0'>{open_b}{html.escape(label)}{close_b}</td>"
                f"<td align='right' style='padding:3px 0'>{open_b}{html.escape(str(value))}{close_b}</td></tr>")

    def section(title):
        return (f"<tr><td colspan='2' style='padding:14px 0 4px 0'>"
                f"<b style='font-size:13px; color:{heading}'>{html.escape(title.upper())}</b></td></tr>")

    parts = [
        f"<h2 style='margin-bottom:0'>{html.escape(local_name)}</h2>",
        f"<p style='margin-top:2px; color:{muted}'>Cierre de caja - {html.escape(date_label)}</p>",
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
        parts.append(row(f"Motos ({summary['moto_orders']} envíos) en efectivo", money(summary["moto_cash"])))
        parts.append(row("Motos por QR", money(summary["moto_qr"])))
    parts.append(section("Por método de pago"))
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
    def __init__(self, order_manager, local_name: str, parent=None, colors: dict = None):
        super().__init__(parent)
        self.order_manager = order_manager
        self.local_name = local_name
        self.colors = colors
        self.setWindowTitle("Resumen del día")
        self.resize(620, 720)
        self.setup_ui()
        self.refresh()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(12)

        top = QHBoxLayout()
        top.addWidget(make_label("CIERRE DE CAJA", "panelTitle"))
        top.addStretch()
        top.addWidget(make_label("Jornada", "muted"))
        today = self.order_manager.today()
        self.date_edit = QDateEdit(QDate(today.year, today.month, today.day))
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDisplayFormat("dd/MM/yyyy")
        self.date_edit.setMaximumDate(QDate(today.year, today.month, today.day))
        self.date_edit.dateChanged.connect(self.refresh)
        top.addWidget(self.date_edit)
        layout.addLayout(top)

        # Tarjetas con lo que el cajero necesita para cuadrar la caja
        kpis = QGridLayout()
        kpis.setSpacing(10)
        self.kpi_labels = {}
        for i, (key, title) in enumerate((("total", "Total vendido"), ("orders", "Pedidos"),
                                          ("cash_net", "\U0001F4B5 Efectivo en caja"),
                                          ("qr_net", "\U0001F4F1 QR neto"))):
            card = QFrame()
            card.setObjectName("productCard")
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(14, 10, 14, 10)
            card_layout.addWidget(make_label(title, "muted"))
            value = make_label("-", "totalAmount")
            card_layout.addWidget(value)
            self.kpi_labels[key] = value
            kpis.addWidget(card, i // 2, i % 2)
        layout.addLayout(kpis)

        self.browser = QTextBrowser()
        layout.addWidget(self.browser, 1)

        buttons = QHBoxLayout()
        self.print_btn = make_button("\U0001F5A8  Imprimir", "secondaryButton", self.print_summary)
        self.excel_btn = make_button("\U0001F4CA  Abrir Excel", "secondaryButton", self.open_excel)
        buttons.addWidget(self.print_btn)
        buttons.addWidget(self.excel_btn)
        buttons.addStretch()
        buttons.addWidget(make_button("Cerrar", "primaryButton", self.accept))
        layout.addLayout(buttons)

    def selected_date(self) -> datetime.date:
        return self.date_edit.date().toPyDate()

    def refresh(self):
        date = self.selected_date()
        self.summary = self.order_manager.day_summary(date)
        label = date.strftime("%d/%m/%Y")
        self.kpi_labels["total"].setText(money(self.summary["total"]))
        self.kpi_labels["orders"].setText(str(self.summary["orders"]))
        self.kpi_labels["cash_net"].setText(money(self.summary["cash_net"]))
        self.kpi_labels["qr_net"].setText(money(self.summary["qr_net"]))
        self.browser.setHtml(day_summary_html(self.summary, label, self.local_name, self.colors))

    def print_summary(self):
        parent = self.parent()
        if parent is not None and hasattr(parent, "print_day_summary"):
            parent.print_day_summary(self.summary, self.selected_date().strftime("%d/%m/%Y"))

    def open_excel(self):
        date = self.selected_date()
        if self.summary["orders"]:
            self.order_manager.refresh_daily_excel(date)
        path = self.order_manager.daily_excel_path(date)
        if not os.path.exists(path):
            QMessageBox.information(self, "Sin Excel", "No hay Excel de ventas para esa jornada.")
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(path))


# ---------------------------------------------------------------------------
#  Impresora de tickets
# ---------------------------------------------------------------------------
class PrinterDialog(QDialog):
    """Elegir la impresora de tickets (Epson TM-T20III), el modo y el ancho del papel."""

    MODES = (
        ("auto", "Automático (ESC/POS si es impresora de tickets)"),
        ("escpos", "Térmica ESC/POS (Epson TM-T20III y similares)"),
        ("windows", "Impresora común de Windows"),
    )
    PAPERS = ((80, "80 mm · 48 columnas"), (58, "58 mm · 32 columnas"))
    FONT_SIZES = (("normal", "Normal (recomendada): platillos de 3 mm, platos en alto doble"),
                  ("grande", "Grande: platillos en alto doble, para leer de lejos"))

    def __init__(self, config: dict, root: str, local_name: str, parent=None, printers=None, default=None):
        super().__init__(parent)
        self.config = config
        self.root = root
        self.local_name = local_name
        self.printers = available_printers() if printers is None else list(printers)
        self.default = default_printer() if default is None else default
        self.setWindowTitle("Impresora de tickets")
        self.setMinimumWidth(520)
        self.setup_ui()

    def setup_ui(self):
        layout = _dialog_layout(
            self, "IMPRESORA DE TICKETS",
            "La comanda y la cuenta se imprimen directo, sin preguntar. Para la Epson TM-T20III "
            "usa ESC/POS con papel de 80 mm: letra nativa de la impresora y corte automático.")

        layout.addWidget(make_label("Impresora", "muted"))
        self.printer_combo = QComboBox()
        self.printer_combo.addItem("Automática (detectar la Epson)", "")
        for name in self.printers:
            tags = []
            if looks_thermal(name):
                tags.append("tickets")
            if name == self.default:
                tags.append("predeterminada")
            self.printer_combo.addItem(f"{name}   ({', '.join(tags)})" if tags else name, name)
        index = self.printer_combo.findData(self.config.get("impresora_tickets", ""))
        self.printer_combo.setCurrentIndex(max(0, index))
        layout.addWidget(self.printer_combo)

        layout.addWidget(make_label("Modo", "muted"))
        self.mode_combo = QComboBox()
        for value, text in self.MODES:
            self.mode_combo.addItem(text, value)
        self.mode_combo.setCurrentIndex(max(0, self.mode_combo.findData(self.config.get("modo_impresion", "auto"))))
        layout.addWidget(self.mode_combo)

        layout.addWidget(make_label("Papel", "muted"))
        self.paper_combo = QComboBox()
        for value, text in self.PAPERS:
            self.paper_combo.addItem(text, value)
        self.paper_combo.setCurrentIndex(max(0, self.paper_combo.findData(int(self.config.get("ancho_papel_mm", 80)))))
        layout.addWidget(self.paper_combo)

        layout.addWidget(make_label("Letra de la comanda", "muted"))
        self.font_combo = QComboBox()
        for value, text in self.FONT_SIZES:
            self.font_combo.addItem(text, value)
        self.font_combo.setCurrentIndex(max(0, self.font_combo.findData(self.config.get("letra_comanda", "normal"))))
        layout.addWidget(self.font_combo)

        self.result_label = make_label("", "hint", wrap=True)
        layout.addWidget(self.result_label)

        buttons = QHBoxLayout()
        self.test_btn = make_button("\U0001F5A8  Imprimir prueba", "secondaryButton", self.print_test)
        buttons.addWidget(self.test_btn)
        buttons.addStretch()
        buttons.addWidget(make_button("Cancelar", "ghostButton", self.reject))
        buttons.addWidget(make_button("Guardar", "primaryButton", self.save))
        layout.addLayout(buttons)

        for combo in (self.printer_combo, self.mode_combo, self.paper_combo, self.font_combo):
            combo.currentIndexChanged.connect(lambda _i: self._update_summary())
        self._update_summary()

    def selection(self) -> dict:
        return {
            "impresora_tickets": self.printer_combo.currentData() or "",
            "modo_impresion": self.mode_combo.currentData(),
            "ancho_papel_mm": int(self.paper_combo.currentData()),
            "letra_comanda": self.font_combo.currentData(),
        }

    def _printer_for_selection(self) -> TicketPrinter:
        return TicketPrinter({**self.config, **self.selection()}, self.printers, self.default)

    def _update_summary(self):
        printer = self._printer_for_selection()
        name = printer.printer_name()
        if not name:
            self.result_label.setText("No hay impresoras instaladas. Instala el driver de la Epson TM-T20III.")
            self.test_btn.setEnabled(False)
            return
        self.test_btn.setEnabled(True)
        mode = "ESC/POS (térmica)" if printer.mode_for(name) == "escpos" else "Windows"
        text = f"Se usará: {name}  ·  {mode}  ·  {printer.columns} columnas"
        if printer.mode_for(name) == "escpos" and not looks_thermal(name):
            text += "\n⚠ Ese nombre no parece de una impresora de tickets: ESC/POS podría imprimir símbolos raros."
        self.result_label.setText(text)

    def print_test(self):
        printer = self._printer_for_selection()
        name = printer.printer_name()
        try:
            printer.print_ticket(tickets.test_ticket(self.local_name, name or "", printer.columns), "PROVA prueba")
        except PrinterError as e:
            self.result_label.setText(f"No se pudo imprimir: {e}")
            return
        self.result_label.setText(f"Prueba enviada a {name}. Revisa que las tildes y el corte salgan bien.")

    def save(self):
        for key, value in self.selection().items():
            self.config[key] = value
            save_config_value(key, value, self.root)
        self.accept()
