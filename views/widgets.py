# views/widgets.py
"""Componentes visuales de la caja: tarjetas de pedido, menu, ticket y avisos."""
from PyQt6.QtCore import QPoint, QRect, QSize, Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QLayout, QPushButton, QSizePolicy, QVBoxLayout, QWidget,
)


def money(value: float) -> str:
    return f"Bs {value:,.2f}"


def repolish(widget: QWidget):
    """Reaplica la hoja de estilos tras cambiar una propiedad usada en un selector."""
    widget.style().unpolish(widget)
    widget.style().polish(widget)
    widget.update()


def set_prop(widget: QWidget, name: str, value):
    if widget.property(name) != value:
        widget.setProperty(name, value)
        repolish(widget)


def make_label(text: str = "", name: str = "", wrap: bool = False) -> QLabel:
    label = QLabel(text)
    if name:
        label.setObjectName(name)
    label.setWordWrap(wrap)
    return label


def make_button(text: str, name: str = "", callback=None, tooltip: str = "") -> QPushButton:
    button = QPushButton(text)
    if name:
        button.setObjectName(name)
    if callback is not None:
        button.clicked.connect(lambda _checked=False: callback())
    if tooltip:
        button.setToolTip(tooltip)
    button.setCursor(Qt.CursorShape.PointingHandCursor)
    return button


def badge(text: str, kind: str = "") -> QLabel:
    label = QLabel(text)
    label.setObjectName("badge")
    if kind:
        label.setProperty("kind", kind)
    return label


def clear_layout(layout: QLayout):
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget()
        if widget is not None:
            widget.hide()
            widget.deleteLater()
        elif item.layout() is not None:
            clear_layout(item.layout())


class FlowLayout(QLayout):
    """Acomoda los elementos en filas que se ajustan al ancho disponible."""

    def __init__(self, parent=None, spacing: int = 8):
        super().__init__(parent)
        self._items = []
        self._spacing = spacing
        self.setContentsMargins(0, 0, 0, 0)

    def addItem(self, item):
        self._items.append(item)

    def count(self):
        return len(self._items)

    def itemAt(self, index):
        return self._items[index] if 0 <= index < len(self._items) else None

    def takeAt(self, index):
        return self._items.pop(index) if 0 <= index < len(self._items) else None

    def expandingDirections(self):
        return Qt.Orientation(0)

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        return self._do_layout(QRect(0, 0, width, 0), test_only=True)

    def setGeometry(self, rect):
        super().setGeometry(rect)
        self._do_layout(rect, test_only=False)

    def sizeHint(self):
        return self.minimumSize()

    def minimumSize(self):
        size = QSize()
        for item in self._items:
            size = size.expandedTo(item.minimumSize())
        margins = self.contentsMargins()
        return size + QSize(margins.left() + margins.right(), margins.top() + margins.bottom())

    def _do_layout(self, rect, test_only):
        margins = self.contentsMargins()
        area = rect.adjusted(margins.left(), margins.top(), -margins.right(), -margins.bottom())
        x, y, row_height = area.x(), area.y(), 0
        for item in self._items:
            if item.widget() is not None and not item.widget().isVisibleTo(item.widget().parentWidget()):
                continue
            hint = item.sizeHint()
            if item.hasHeightForWidth():
                hint.setHeight(item.heightForWidth(hint.width()))
            next_x = x + hint.width() + self._spacing
            if next_x - self._spacing > area.right() + 1 and row_height > 0:
                x = area.x()
                y += row_height + self._spacing
                next_x = x + hint.width() + self._spacing
                row_height = 0
            if not test_only:
                item.setGeometry(QRect(QPoint(x, y), hint))
            x = next_x
            row_height = max(row_height, hint.height())
        return y + row_height - rect.y() + margins.bottom()


class ClickableFrame(QFrame):
    clicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.rect().contains(event.pos()):
            self.clicked.emit()
        super().mouseReleaseEvent(event)


class OrderCard(ClickableFrame):
    """Tarjeta de un pedido en la columna izquierda."""

    selected_name = pyqtSignal(str)

    def __init__(self, name: str, order: dict, minutes: int, selected: bool, parent=None):
        super().__init__(parent)
        self.name = name
        self.setObjectName("orderCard")
        self.setProperty("selected", selected)
        self.setProperty("paid", bool(order["paid"]))
        self.clicked.connect(lambda: self.selected_name.emit(self.name))

        total = sum(i["price"] for i in order["items"])
        units = len(order["items"])
        pending_kitchen = sum(1 for i in order["items"] if not i.get("kitchen_sent"))

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(4)

        top = QHBoxLayout()
        top.setSpacing(8)
        top.addWidget(make_label(order["number"], "cardNumber"))
        title = make_label(name, "cardTitle")
        title.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        top.addWidget(title, 1)
        layout.addLayout(top)

        middle = QHBoxLayout()
        items_text = "Sin platillos" if not units else f"{units} {'ítem' if units == 1 else 'ítems'}"
        if order["order_type"] == "Para llevar":
            items_text = f"\U0001F6F5 Para llevar · {items_text}"
        meta = make_label(items_text, "cardMeta")
        meta.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        middle.addWidget(meta, 1)
        middle.addWidget(make_label(money(total), "cardTotal"))
        layout.addLayout(middle)

        # Las etiquetas bajan de linea si no entran, asi la tarjeta nunca se corta
        bottom = FlowLayout(spacing=6)
        if order["paid"]:
            paid_at = (order.get("paid_at") or "")[11:16]
            bottom.addWidget(badge(f"✔ Cobrado {paid_at}".strip(), "paid"))
        else:
            kind = "late" if minutes >= 40 else "warn" if minutes >= 20 else ""
            bottom.addWidget(badge(f"⏱ {format_minutes(minutes)}", kind))
            if pending_kitchen:
                bottom.addWidget(badge(f"\U0001F514 {pending_kitchen} sin comanda", "kitchen"))
            if order.get("created_by") == "mesero":
                bottom.addWidget(badge("\U0001F4F1 Mesero", "waiter"))
        layout.addLayout(bottom)
        self.setToolTip(f"{order['number']} - {name}\n{order['order_type']}")


def format_minutes(minutes: int) -> str:
    if minutes < 1:
        return "recién"
    if minutes < 60:
        return f"{minutes} min"
    return f"{minutes // 60} h {minutes % 60:02d} min"


PRODUCT_CARD_MIN_WIDTH = 214


class ProductCard(QFrame):
    """Un producto del menu con un boton por variante: un toque agrega al pedido."""

    def __init__(self, category: str, product: str, variants: dict, icon: str,
                 on_add, parent=None):
        super().__init__(parent)
        self.setObjectName("productCard")
        self.setFixedWidth(PRODUCT_CARD_MIN_WIDTH)
        self.buttons = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 12)
        layout.setSpacing(8)

        header = QHBoxLayout()
        header.setSpacing(8)
        header.addWidget(make_label(icon, "productIcon"))
        name = make_label(product, "productName", wrap=True)
        header.addWidget(name, 1)
        layout.addLayout(header)

        flow = FlowLayout(spacing=6)
        for variant, price in variants.items():
            text = f"{variant}  ·  {price:g}"
            button = make_button(text, "variantChip",
                                 tooltip=f"Agregar {product} ({variant}) - {money(price)}")
            button.clicked.connect(
                lambda _checked=False, v=variant, b=button: on_add(category, product, v, b))
            flow.addWidget(button)
            self.buttons[variant] = button
        layout.addLayout(flow)


class TicketLine(QFrame):
    """Linea del ticket: cantidad con -/+, nombre, nota, precio y menu de opciones."""

    def __init__(self, line: dict, index: int, editable: bool, on_qty, on_menu, parent=None):
        super().__init__(parent)
        self.line = line
        self.index = index
        self.setObjectName("ticketLine")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(2, 8, 2, 8)
        layout.setSpacing(8)

        qty = QHBoxLayout()
        qty.setSpacing(4)
        self.minus_btn = make_button("−", "qtyButton", lambda: on_qty(index, -1),
                                     "Quitar uno")
        self.qty_label = make_label(str(line["qty"]), "qtyLabel")
        self.qty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.plus_btn = make_button("+", "qtyButton", lambda: on_qty(index, 1), "Agregar uno igual")
        for widget in (self.minus_btn, self.qty_label, self.plus_btn):
            qty.addWidget(widget)
        self.minus_btn.setVisible(editable)
        self.plus_btn.setVisible(editable)
        layout.addLayout(qty)

        text = QVBoxLayout()
        text.setSpacing(1)
        name_row = QHBoxLayout()
        name_row.setSpacing(6)
        name = make_label(line["dish"], "lineName", wrap=True)
        name_row.addWidget(name, 1)
        if editable and line.get("pending_kitchen"):
            dot = make_label("●", "kitchenDot")
            dot.setToolTip(f"{line['pending_kitchen']} sin enviar a cocina")
            name_row.addWidget(dot)
        text.addLayout(name_row)
        text.addWidget(make_label(line["variant"], "lineSub", wrap=True))
        if line["note"]:
            text.addWidget(make_label(f"\U0001F4DD {line['note']}", "lineNote", wrap=True))
        layout.addLayout(text, 1)

        price = make_label(money(line["subtotal"]), "linePrice")
        price.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(price)

        self.menu_btn = make_button("⋯", "lineMenuButton", tooltip="Nota, mover de plato, quitar")
        self.menu_btn.clicked.connect(lambda _checked=False: on_menu(index, self.menu_btn))
        self.menu_btn.setVisible(editable)
        layout.addWidget(self.menu_btn)


class Toast(QLabel):
    """Aviso flotante que no interrumpe al cajero (a diferencia de un cuadro de dialogo)."""

    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.setObjectName("toast")
        self.setWordWrap(True)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.last_message = ""
        self.last_kind = ""
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.hide)
        self.hide()

    def show_message(self, text: str, kind: str = "info", duration_ms: int = 2600):
        self.last_message = text
        self.last_kind = kind
        set_prop(self, "kind", kind)
        self.setText(text)
        self.reposition()
        self.raise_()
        self.show()
        self._timer.start(duration_ms)

    def reposition(self):
        parent = self.parentWidget()
        if parent is None:
            return
        width = min(560, max(260, parent.width() - 80))
        self.setFixedWidth(width)
        self.adjustSize()
        self.move((parent.width() - self.width()) // 2, parent.height() - self.height() - 36)
