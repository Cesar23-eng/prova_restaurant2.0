import datetime
import html
import os

from PyQt6.QtCore import QEvent, Qt, QTimer, QUrl, pyqtSignal
from PyQt6.QtGui import QColor, QDesktopServices, QKeySequence, QPalette, QPixmap, QShortcut
from PyQt6.QtWidgets import (
    QApplication, QButtonGroup, QDialog, QFrame, QHBoxLayout, QInputDialog, QLabel, QLineEdit,
    QMainWindow, QMenu, QMessageBox, QScrollArea, QSizePolicy, QSpinBox, QVBoxLayout, QWidget,
)

from models.menu import MenuData
from models.order import (
    MAX_PLATES, ORDER_TYPE_LOCAL, ORDER_TYPE_TAKEAWAY, OrderChangedError, OrderManager,
    group_lines_by_plate, plate_label,
)
from utils.config import app_dir, load_config, save_config_value
from utils.icons import category_icon, normalize_text, product_icon
from utils.styles import THEME_NAMES, ThemeManager
from views.dialogs import (
    AddOrderDialog, DaySummaryDialog, DeliveryDialog, EditTableDialog, PaymentDialog, PlateDialog,
)
from views.widgets import (
    PRODUCT_CARD_MIN_WIDTH, FlowLayout, OrderCard, ProductCard, TicketLine, Toast, clear_layout,
    format_minutes, make_button, make_label, money, set_prop,
)

MENU_SPACING = 10


def _scroll_area(widget: QWidget) -> QScrollArea:
    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QFrame.Shape.NoFrame)
    scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    scroll.setWidget(widget)
    return scroll


def _minutes_since(stamp: str) -> int:
    try:
        started = datetime.datetime.fromisoformat(stamp)
    except (TypeError, ValueError):
        return 0
    return max(0, int((datetime.datetime.now() - started).total_seconds() // 60))


class ProvaRestaurant(QMainWindow):
    """
    Caja de PRÖVA México en tres columnas, como un POS de restaurante:
    pedidos abiertos | menu tactil (un toque agrega) | ticket del pedido.
    """

    # Emitida desde cualquier hilo (p. ej. el servidor de meseros); Qt la entrega en el hilo de la UI
    orders_changed = pyqtSignal(str, str, dict)

    def __init__(self, order_manager: OrderManager = None, menu_data: MenuData = None,
                 config: dict = None):
        super().__init__()
        self.config = config or load_config()
        self.menu_data = menu_data or MenuData()
        self.order_manager = order_manager or OrderManager(
            cutoff_hour=int(self.config.get("hora_corte_jornada", 4)))
        self.theme_manager = ThemeManager(self.config.get("tema_visual", "noche"))
        self.local_name = self.config.get("nombre_local", "PRÖVA México")
        self.waiter_pin = str(self.config.get("pin_meseros", ""))
        self.waiter_url = ""
        self.waiter_server = None

        self.active_plate = 1
        self._plate_table = None
        self.current_category = None
        self._menu_snapshot = None
        self.category_buttons = {}
        self.variant_buttons = {}
        self.order_cards = {}
        self.plate_buttons = {}
        self.ticket_lines = []

        self.setWindowTitle("PRÖVA México · Caja")
        self.resize(1360, 820)
        self.setMinimumSize(1180, 680)
        self._build_ui()
        self.apply_stylesheet()
        self.reload_menu()

        self.orders_changed.connect(self._on_orders_changed)
        self.order_manager.add_listener(
            lambda event, table, info: self.orders_changed.emit(event, table or "", dict(info)))
        self.refresh_orders()
        self.refresh_ticket()
        self._setup_shortcuts()

        # Si el dueño edita menu_precios.xlsx con la app abierta, se recarga solo
        self.menu_timer = QTimer(self)
        self.menu_timer.timeout.connect(self.reload_menu)
        self.menu_timer.start(10_000)
        # Reloj y minutos de espera de cada mesa
        self.clock_timer = QTimer(self)
        self.clock_timer.timeout.connect(self._tick)
        self.clock_timer.start(30_000)
        self._update_clock()

        if self.order_manager.restored_count:
            QTimer.singleShot(500, lambda: self.toast.show_message(
                f"Se recuperaron {self.order_manager.restored_count} pedido(s) abiertos "
                f"de la sesión anterior.", "warning", 6000))

    @property
    def current_table(self):
        return self.order_manager.current_table

    # ================================================================
    #  Construccion de la interfaz
    # ================================================================
    def _build_ui(self):
        central = QWidget()
        central.setObjectName("central")
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self._build_header())

        body = QHBoxLayout()
        body.setContentsMargins(14, 14, 14, 14)
        body.setSpacing(14)
        body.addWidget(self._build_orders_panel())
        body.addWidget(self._build_menu_panel(), 1)
        body.addWidget(self._build_ticket_panel())
        root.addLayout(body, 1)

        self.toast = Toast(central)

    def _load_logo(self):
        for name in ("prova.png", "PROVA.png"):
            path = os.path.join(app_dir(), name)
            if os.path.exists(path):
                pixmap = QPixmap(path)
                if not pixmap.isNull():
                    return pixmap
        return None

    def _build_header(self) -> QFrame:
        header = QFrame()
        header.setObjectName("header")
        layout = QHBoxLayout(header)
        layout.setContentsMargins(18, 8, 18, 8)
        layout.setSpacing(12)

        logo = QLabel()
        logo.setObjectName("logoBadge")
        logo.setFixedSize(54, 54)
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pixmap = self._load_logo()
        if pixmap is not None:
            logo.setPixmap(pixmap.scaled(50, 50, Qt.AspectRatioMode.KeepAspectRatio,
                                         Qt.TransformationMode.SmoothTransformation))
        else:
            logo.setText("\U0001F336")
        layout.addWidget(logo)

        brand = QVBoxLayout()
        brand.setSpacing(0)
        brand.addWidget(make_label("PRÖVA", "brandTitle"))
        brand.addWidget(make_label("México", "brandScript"))
        layout.addLayout(brand)
        layout.addSpacing(18)

        self.jornada_label = make_label("", "headerInfo")
        layout.addWidget(self.jornada_label)
        layout.addStretch()

        self.waiters_btn = make_button("\U0001F4F1  Meseros: iniciando...", "headerChip",
                                       self.show_waiter_access,
                                       "Dirección y PIN para los celulares de los meseros")
        self.summary_btn = make_button("\U0001F4CA  Resumen del día", "headerChip", self.show_day_summary,
                                       "Cierre de caja: efectivo, QR y productos vendidos")
        self.theme_btn = make_button("", "headerChip", self.toggle_theme)
        self.more_btn = make_button("⋯", "iconButton", tooltip="Más opciones")
        more_menu = QMenu(self)
        more_menu.addAction("\U0001F4BE  Exportar respaldo del día", lambda _=False: self.save_to_excel())
        more_menu.addAction("\U0001F4C2  Abrir carpeta de ventas", lambda _=False: self.open_data_folder())
        more_menu.addSeparator()
        more_menu.addAction("\U0001F511  Cambiar PIN de meseros", lambda _=False: self.change_waiter_pin())
        self.more_btn.setMenu(more_menu)
        for widget in (self.waiters_btn, self.summary_btn, self.theme_btn, self.more_btn):
            layout.addWidget(widget)
        return header

    def _build_orders_panel(self) -> QFrame:
        panel = QFrame()
        panel.setObjectName("panel")
        panel.setFixedWidth(310)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        top = QHBoxLayout()
        top.addWidget(make_label("PEDIDOS", "panelTitle"))
        top.addStretch()
        self.pending_label = make_label("", "muted")
        top.addWidget(self.pending_label)
        layout.addLayout(top)

        self.new_order_btn = make_button("＋  Nuevo pedido", "bigPrimary", self.add_pedido, "Ctrl+N")
        layout.addWidget(self.new_order_btn)

        cards = QWidget()
        self.cards_layout = QVBoxLayout(cards)
        self.cards_layout.setContentsMargins(0, 2, 6, 2)
        self.cards_layout.setSpacing(8)
        self.cards_layout.addStretch()
        layout.addWidget(_scroll_area(cards), 1)

        self.orders_empty = make_label(
            "Todavía no hay pedidos.\nToca «Nuevo pedido» o espera a los meseros.", "emptyState", wrap=True)
        self.orders_empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.orders_empty)

        self.clear_paid_btn = make_button("Quitar cobrados de la lista", "ghostButton", self.clear_paid_orders,
                                          "Siguen guardados en el Excel del día")
        layout.addWidget(self.clear_paid_btn)
        return panel

    def _build_menu_panel(self) -> QFrame:
        panel = QFrame()
        panel.setObjectName("panel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(12)

        top = QHBoxLayout()
        top.setSpacing(10)
        top.addWidget(make_label("MENÚ", "panelTitle"))
        self.search_input = QLineEdit()
        self.search_input.setObjectName("searchInput")
        self.search_input.setPlaceholderText("\U0001F50D  Buscar platillo o bebida…     Ctrl+K")
        self.search_input.setClearButtonEnabled(True)
        self.search_input.textChanged.connect(lambda _text: self.render_products())
        self.search_input.returnPressed.connect(self._add_single_search_result)
        top.addWidget(self.search_input, 1)
        top.addWidget(make_label("Cantidad", "muted"))
        self.qty_spin = QSpinBox()
        self.qty_spin.setRange(1, 50)
        self.qty_spin.setFixedWidth(84)
        self.qty_spin.setToolTip("Unidades que agrega cada toque. Vuelve a 1 después de agregar.")
        top.addWidget(self.qty_spin)
        layout.addLayout(top)

        self.menu_warning = make_label("", "menuWarning", wrap=True)
        self.menu_warning.hide()
        layout.addWidget(self.menu_warning)

        chips = QWidget()
        self.category_layout = FlowLayout(chips, spacing=8)
        self.category_group = QButtonGroup(self)
        layout.addWidget(chips)

        products = QWidget()
        self.products_layout = FlowLayout(products, spacing=MENU_SPACING)
        self.products_scroll = _scroll_area(products)
        self.products_scroll.viewport().installEventFilter(self)
        self.product_cards = []
        layout.addWidget(self.products_scroll, 1)

        self.no_results = make_label("", "emptyState", wrap=True)
        self.no_results.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.no_results.hide()
        layout.addWidget(self.no_results)
        return panel

    def _build_ticket_panel(self) -> QFrame:
        panel = QFrame()
        panel.setObjectName("panel")
        panel.setFixedWidth(410)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(16, 14, 16, 16)
        layout.setSpacing(10)

        # --- Sin pedido seleccionado ---
        self.ticket_empty = QWidget()
        empty = QVBoxLayout(self.ticket_empty)
        empty.addStretch()
        icon = make_label("\U0001F32E", "emptyIcon")
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty.addWidget(icon)
        text = make_label("Selecciona un pedido de la izquierda\no crea uno nuevo", "emptyState", wrap=True)
        text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty.addWidget(text)
        empty.addSpacing(8)
        empty.addWidget(make_button("＋  Nuevo pedido", "primaryButton", self.add_pedido))
        empty.addStretch()
        layout.addWidget(self.ticket_empty, 1)

        # --- Pedido ---
        self.ticket_body = QWidget()
        body = QVBoxLayout(self.ticket_body)
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(10)

        head = QHBoxLayout()
        head.setSpacing(8)
        self.ticket_number = make_label("", "ticketNumber")
        head.addWidget(self.ticket_number)
        self.ticket_name = make_label("", "ticketTitle")
        self.ticket_name.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        head.addWidget(self.ticket_name, 1)
        self.rename_btn = make_button("✎", "iconButton", self.edit_table_name, "Renombrar pedido")
        self.delete_btn = make_button("\U0001F5D1", "iconButton", self.delete_table, "Eliminar pedido")
        head.addWidget(self.rename_btn)
        head.addWidget(self.delete_btn)
        body.addLayout(head)
        self.ticket_meta = make_label("", "muted")
        body.addWidget(self.ticket_meta)

        type_row = QHBoxLayout()
        type_row.setSpacing(8)
        self.type_group = QButtonGroup(self)
        self.type_buttons = {}
        for value, text in ((ORDER_TYPE_LOCAL, "\U0001F37D  En el local"),
                            (ORDER_TYPE_TAKEAWAY, "\U0001F6F5  Para llevar")):
            button = make_button(text, "segment")
            button.setCheckable(True)
            button.clicked.connect(lambda _c=False, v=value: self.set_order_type(v))
            self.type_group.addButton(button)
            type_row.addWidget(button, 1)
            self.type_buttons[value] = button
        body.addLayout(type_row)

        plate_row = QHBoxLayout()
        plate_row.setSpacing(8)
        plate_row.addWidget(make_label("PLATO", "muted"))
        plate_bar = QWidget()
        self.plate_layout = FlowLayout(plate_bar, spacing=6)
        plate_row.addWidget(plate_bar, 1)
        body.addLayout(plate_row)
        self.plate_hint = make_label("", "hint", wrap=True)
        body.addWidget(self.plate_hint)

        lines = QWidget()
        self.lines_layout = QVBoxLayout(lines)
        self.lines_layout.setContentsMargins(0, 0, 6, 0)
        self.lines_layout.setSpacing(4)
        self.lines_layout.addStretch()
        body.addWidget(_scroll_area(lines), 1)
        self.lines_empty = make_label("Pedido vacío.\nToca un platillo del menú para agregarlo.",
                                      "emptyState", wrap=True)
        self.lines_empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        body.addWidget(self.lines_empty)

        self.paid_banner = make_label("", "paidBanner", wrap=True)
        body.addWidget(self.paid_banner)

        total_row = QHBoxLayout()
        total_row.addWidget(make_label("TOTAL", "panelTitle"))
        total_row.addStretch()
        self.total_label = make_label(money(0), "totalAmount")
        total_row.addWidget(self.total_label)
        body.addLayout(total_row)

        actions = QHBoxLayout()
        actions.setSpacing(8)
        self.kitchen_btn = make_button("\U0001F514  Comanda", "secondaryButton",
                                       self.print_kitchen_ticket, "F8 · Imprime para cocina solo lo nuevo")
        self.bill_btn = make_button("\U0001F9FE  Cuenta", "secondaryButton", self.print_customer_bill,
                                    "Ctrl+P · Cuenta para el cliente")
        self.ticket_more_btn = make_button("⋯", "secondaryButton", tooltip="Más acciones del pedido")
        ticket_menu = QMenu(self)
        ticket_menu.addAction("\U0001F501  Reimprimir comanda completa",
                              lambda _=False: self.print_kitchen_ticket(reprint_all=True))
        self.plates_action = ticket_menu.addAction("\U0001F37D  Repartir en platos…",
                                                   lambda _=False: self.organize_plates())
        ticket_menu.addSeparator()
        ticket_menu.addAction("✎  Renombrar pedido", lambda _=False: self.edit_table_name())
        ticket_menu.addAction("\U0001F5D1  Eliminar pedido", lambda _=False: self.delete_table())
        self.ticket_more_btn.setMenu(ticket_menu)
        actions.addWidget(self.kitchen_btn, 1)
        actions.addWidget(self.bill_btn, 1)
        actions.addWidget(self.ticket_more_btn)
        body.addLayout(actions)

        self.pay_btn = make_button("Cobrar", "payButton", self.mark_as_paid, "F9")
        body.addWidget(self.pay_btn)
        self.remove_paid_btn = make_button("Quitar de la lista", "ghostButton", self.delete_table)
        body.addWidget(self.remove_paid_btn)

        layout.addWidget(self.ticket_body, 1)
        return panel

    def _setup_shortcuts(self):
        QShortcut(QKeySequence("Ctrl+N"), self, activated=self.add_pedido)
        QShortcut(QKeySequence("F9"), self, activated=self.mark_as_paid)
        QShortcut(QKeySequence("F8"), self, activated=self.print_kitchen_ticket)
        QShortcut(QKeySequence("Ctrl+P"), self, activated=self.print_customer_bill)
        QShortcut(QKeySequence("Ctrl+K"), self, activated=self._focus_search)
        escape = QShortcut(QKeySequence("Escape"), self.search_input, activated=self.search_input.clear)
        escape.setContext(Qt.ShortcutContext.WidgetShortcut)

    def _focus_search(self):
        self.search_input.setFocus()
        self.search_input.selectAll()

    # ================================================================
    #  Tema y reloj
    # ================================================================
    def apply_stylesheet(self):
        app = QApplication.instance()
        app.setStyleSheet(self.theme_manager.get_stylesheet())
        theme = self.theme_manager.get_current_theme()
        palette = app.palette()
        palette.setColor(QPalette.ColorRole.Window, QColor(theme["bg"]))
        palette.setColor(QPalette.ColorRole.Base, QColor(theme["surface3"]))
        palette.setColor(QPalette.ColorRole.Text, QColor(theme["text"]))
        palette.setColor(QPalette.ColorRole.WindowText, QColor(theme["text"]))
        palette.setColor(QPalette.ColorRole.Highlight, QColor(theme["primary"]))
        app.setPalette(palette)
        other = "dia" if self.theme_manager.is_dark else "noche"
        icon = "☀" if other == "dia" else "\U0001F319"
        self.theme_btn.setText(f"{icon}  {THEME_NAMES[other]}")
        self.theme_btn.setToolTip(f"Cambiar al tema {THEME_NAMES[other]}")

    def toggle_theme(self):
        self.theme_manager.toggle_theme()
        self.apply_stylesheet()
        try:
            save_config_value("tema_visual", self.theme_manager.current_theme, self.order_manager.root)
        except OSError:
            pass

    def _update_clock(self):
        now = datetime.datetime.now()
        self.jornada_label.setText(f"Jornada {self.order_manager.today():%d/%m}  ·  {now:%H:%M}")

    def _tick(self):
        self._update_clock()
        self.refresh_orders()
        self._update_ticket_meta()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.toast.isVisible():
            self.toast.reposition()

    # ================================================================
    #  Servidor de meseros
    # ================================================================
    def start_waiter_server(self):
        try:
            from server import WaiterServer, create_app, get_local_ip

            app = create_app(self.order_manager, self.menu_data, lambda: self.waiter_pin,
                             int(self.config.get("numero_mesas", 13)))
            self.waiter_server = WaiterServer(app)
            port = self.waiter_server.start(int(self.config.get("puerto_meseros", 5000)))
            self.waiter_url = f"http://{get_local_ip()}:{port}"
            self.waiters_btn.setText(f"\U0001F4F1  Meseros: {self.waiter_url.replace('http://', '')}")
            set_prop(self.waiters_btn, "status", "ok")
        except Exception as e:
            self.waiters_btn.setText("\U0001F4F1  Meseros sin conexión")
            set_prop(self.waiters_btn, "status", "error")
            self.toast.show_message(f"No se pudo iniciar el servidor de meseros: {e}", "error", 8000)

    def show_waiter_access(self):
        if not self.waiter_url:
            QMessageBox.warning(self, "Meseros", "El servidor de meseros no está activo.")
            return
        accent = self.theme_manager.get_current_theme()["accent"]
        box = QMessageBox(self)
        box.setWindowTitle("Acceso de meseros")
        box.setText(
            f"<p>En el celular, conectado al WiFi del local, abre:</p>"
            f"<h2 style='color:{accent}'>{html.escape(self.waiter_url)}</h2>"
            f"<p>PIN de meseros: <b style='font-size:22px'>{html.escape(self.waiter_pin)}</b></p>"
            f"<p>Si no abre, permite la app en el Firewall de Windows (redes privadas).</p>"
        )
        change = box.addButton("Cambiar PIN", QMessageBox.ButtonRole.ActionRole)
        box.addButton("Cerrar", QMessageBox.ButtonRole.RejectRole)
        box.exec()
        if box.clickedButton() is change:
            self.change_waiter_pin()

    def change_waiter_pin(self):
        pin, ok = QInputDialog.getText(self, "Cambiar PIN", "Nuevo PIN (4 a 8 dígitos):",
                                       text=self.waiter_pin)
        pin = (pin or "").strip()
        if not ok:
            return
        if not pin.isdigit() or not 4 <= len(pin) <= 8:
            QMessageBox.warning(self, "PIN inválido", "El PIN debe tener entre 4 y 8 dígitos.")
            return
        self.waiter_pin = pin
        save_config_value("pin_meseros", pin, self.order_manager.root)
        self.toast.show_message("PIN actualizado. Los meseros deben ingresarlo de nuevo.", "success")

    # ================================================================
    #  Cierre de la app
    # ================================================================
    def closeEvent(self, event):
        open_tables = self.order_manager.pending_tables()
        if open_tables:
            names = ", ".join(open_tables)
            reply = QMessageBox.question(
                self,
                "Cerrar PRÖVA",
                f"Hay {len(open_tables)} pedido(s) SIN cobrar:\n{names}\n\n"
                f"Quedan guardados y aparecerán al volver a abrir la app.\n\n"
                f"¿Deseas cerrar?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.No:
                event.ignore()
                return
        if self.waiter_server is not None:
            self.waiter_server.stop()
        event.accept()

    # ================================================================
    #  Menu
    # ================================================================
    def reload_menu(self):
        menu = self.menu_data.get_menu_prices()
        if self.menu_data.last_error:
            self.menu_warning.setText(f"{self.menu_data.last_error}. "
                                      f"Coloca menu_precios.xlsx junto al programa.")
            self.menu_warning.show()
        else:
            self.menu_warning.hide()
        if menu is self._menu_snapshot:
            return
        self._menu_snapshot = menu

        clear_layout(self.category_layout)
        for button in self.category_group.buttons():
            self.category_group.removeButton(button)
        self.category_buttons = {}
        if self.current_category not in menu:
            self.current_category = next(iter(menu), None)
        for category in menu:
            button = make_button(f"{category_icon(category)}  {category}", "chip")
            button.setCheckable(True)
            button.clicked.connect(lambda _c=False, c=category: self.set_category(c))
            self.category_group.addButton(button)
            self.category_layout.addWidget(button)
            self.category_buttons[category] = button
        self.render_products()

    def set_category(self, category: str):
        self.current_category = category
        if self.search_input.text():
            self.search_input.clear()  # vuelve a dibujar el menu
        else:
            self.render_products()
        self.products_scroll.verticalScrollBar().setValue(0)

    def eventFilter(self, obj, event):
        if obj is self.products_scroll.viewport() and event.type() == QEvent.Type.Resize:
            self._fit_product_cards()
        return super().eventFilter(obj, event)

    def _fit_product_cards(self):
        """Tarjetas del menu que llenan el ancho: tantas columnas como entren."""
        width = self.products_scroll.viewport().width() - 2
        columns = max(1, (width + MENU_SPACING) // (PRODUCT_CARD_MIN_WIDTH + MENU_SPACING))
        card_width = max(PRODUCT_CARD_MIN_WIDTH, (width - MENU_SPACING * (columns - 1)) // columns)
        for card in self.product_cards:
            card.setFixedWidth(card_width)

    def render_products(self):
        menu = self.menu_data.get_menu_prices()
        tokens = normalize_text(self.search_input.text()).split()
        clear_layout(self.products_layout)
        self.variant_buttons = {}
        self.product_cards = []
        shown = 0
        for category, products in menu.items():
            if not tokens and category != self.current_category:
                continue
            for product, variants in products.items():
                if tokens:
                    variants = {
                        variant: price for variant, price in variants.items()
                        if all(t in normalize_text(f"{product} {variant} {category}") for t in tokens)
                    }
                    if not variants:
                        continue
                card = ProductCard(category, product, variants, product_icon(product, category),
                                   self.add_product)
                self.products_layout.addWidget(card)
                self.product_cards.append(card)
                for variant, button in card.buttons.items():
                    self.variant_buttons[(category, product, variant)] = button
                shown += 1
        self._fit_product_cards()
        for category, button in self.category_buttons.items():
            button.setChecked(not tokens and category == self.current_category)
        if shown:
            self.no_results.hide()
        else:
            self.no_results.setText("Sin resultados para esa búsqueda." if tokens else "Menú no disponible.")
            self.no_results.show()

    def _add_single_search_result(self):
        if not self.search_input.text().strip():
            return
        if len(self.variant_buttons) == 1:
            (category, product, variant), button = next(iter(self.variant_buttons.items()))
            if self.add_product(category, product, variant, button):
                self.search_input.clear()
        elif self.variant_buttons:
            self.toast.show_message(f"Hay {len(self.variant_buttons)} opciones: toca la que quieras.", "info")

    def _flash(self, button):
        def restore():
            try:
                set_prop(button, "flash", False)
            except RuntimeError:
                pass  # el boton ya no existe (el menu se volvio a dibujar)
        set_prop(button, "flash", True)
        QTimer.singleShot(350, restore)

    def add_product(self, category: str, dish: str, variant: str, button=None) -> bool:
        """Un toque en el menu: agrega al pedido actual (o pide crear uno)."""
        table = self.current_table
        if not table:
            if not self.add_pedido():
                return False
            table = self.current_table
        if self.order_manager.is_paid(table):
            self.toast.show_message(f"«{table}» ya fue cobrado. Crea un pedido nuevo.", "error")
            return False
        price = self.menu_data.get_price(category, dish, variant)
        if price is None:
            self.toast.show_message(f"{dish} ({variant}) ya no está en el menú.", "error")
            return False
        qty = self.qty_spin.value()
        plate = self.active_plate if self.order_manager.plate_applies(dish) else 0
        try:
            self.order_manager.add_item(table, category, dish, variant, price, qty=qty, plate=plate)
        except (KeyError, ValueError, PermissionError) as e:
            self.toast.show_message(str(e), "error")
            return False
        self.qty_spin.setValue(1)
        if button is not None:
            self._flash(button)
        destination = f"  →  {plate_label(plate)}" if plate else ""
        self.toast.show_message(f"+ {qty}× {dish} ({variant}){destination}", "success", 1500)
        return True

    # ================================================================
    #  Pedidos
    # ================================================================
    def _on_orders_changed(self, event: str, table: str, info: dict):
        if event == "renamed" and info.get("old_name") == self._plate_table:
            self._plate_table = table
        self.refresh_orders()
        self.refresh_ticket()
        if info.get("source") == "mesero":
            if event == "created":
                self.toast.show_message(f"\U0001F4F1 Un mesero abrió «{table}»", "info", 4000)
            elif event == "items_added":
                self.toast.show_message(
                    f"\U0001F4F1 Mesero: +{info.get('count', 0)} platillo(s) en «{table}»",
                    "warning", 5000)
                QApplication.beep()

    def refresh_orders(self):
        clear_layout(self.cards_layout)
        self.order_cards = {}
        names = self.order_manager.get_all_tables()
        orders = [(name, self.order_manager.get_order(name)) for name in names]
        orders = [(name, order) for name, order in orders if order]
        orders.sort(key=lambda item: item[1]["paid"])  # primero lo que falta cobrar
        pending = paid = 0
        for name, order in orders:
            card = OrderCard(name, order, _minutes_since(order.get("created_at")),
                             name == self.current_table)
            card.selected_name.connect(self.select_order)
            self.cards_layout.addWidget(card)
            self.order_cards[name] = card
            if order["paid"]:
                paid += 1
            elif order["items"]:
                pending += 1
        self.cards_layout.addStretch()
        self.orders_empty.setVisible(not orders)
        self.pending_label.setText(f"{pending} por cobrar" if pending else "")
        self.clear_paid_btn.setVisible(paid > 0)
        self.clear_paid_btn.setText(f"Quitar cobrados de la lista ({paid})")
        if self.current_table and self.current_table not in names:
            self.order_manager.set_current_table(None)

    def select_order(self, name: str):
        self.order_manager.set_current_table(name)
        self.refresh_orders()
        self.refresh_ticket()

    def _update_ticket_meta(self):
        table = self.current_table
        order = self.order_manager.get_order(table) if table else None
        if order is None:
            return
        parts = []
        if order["paid"]:
            parts.append(f"Cobrado a las {(order.get('paid_at') or '')[11:16]}")
        else:
            opened = (order.get("created_at") or "")[11:16]
            parts.append(f"Abierto {opened}  ·  hace {format_minutes(_minutes_since(order.get('created_at')))}")
        if order.get("created_by") == "mesero":
            parts.append("\U0001F4F1 mesero")
        delivery = order.get("delivery")
        if delivery and order["order_type"] == ORDER_TYPE_TAKEAWAY:
            parts.append(f"\U0001F6F5 moto {money(delivery['moto_cost'])}")
        self.ticket_meta.setText("  ·  ".join(parts))

    def refresh_ticket(self):
        table = self.current_table
        order = self.order_manager.get_order(table) if table else None
        self.ticket_empty.setVisible(order is None)
        self.ticket_body.setVisible(order is not None)
        if order is None:
            self.ticket_lines = []
            self._plate_table = None
            return

        paid = order["paid"]
        self.ticket_number.setText(order["number"])
        self.ticket_name.setText(table)
        self._update_ticket_meta()
        for value, button in self.type_buttons.items():
            button.setChecked(order["order_type"] == value)
            button.setEnabled(not paid)
        self.rename_btn.setEnabled(not paid)
        self.plates_action.setEnabled(not paid)
        self._refresh_plate_bar(table, order)

        clear_layout(self.lines_layout)
        self.ticket_lines = []
        lines = self.order_manager.get_order_lines(table)
        indexed = [dict(line, index=i) for i, line in enumerate(lines)]
        with_plates = any(line["plate"] for line in lines)
        for plate, plate_lines in group_lines_by_plate(indexed):
            if with_plates:
                subtotal = sum(line["subtotal"] for line in plate_lines)
                title = f"\U0001F37D  {plate_label(plate).upper()}" if plate else "OTROS  ·  SIN PLATO"
                self.lines_layout.addWidget(make_label(f"{title}   ·   {money(subtotal)}", "plateHeader"))
            for line in plate_lines:
                widget = TicketLine(line, line["index"], not paid, self.change_line_qty, self.show_line_menu,
                                    plate_enabled=self.order_manager.plate_applies(line["dish"]),
                                    on_plate=self.show_plate_menu)
                self.lines_layout.addWidget(widget)
                self.ticket_lines.append(widget)
        self.lines_layout.addStretch()
        self.lines_empty.setVisible(not lines)

        total = sum(line["subtotal"] for line in lines)
        pending_kitchen = sum(line["pending_kitchen"] for line in lines)
        self.total_label.setText(money(total))
        self.kitchen_btn.setText(f"\U0001F514  Comanda ({pending_kitchen})" if pending_kitchen
                                 else "\U0001F514  Comanda")
        set_prop(self.kitchen_btn, "attention", bool(pending_kitchen) and not paid)
        self.kitchen_btn.setEnabled(bool(lines))
        self.bill_btn.setEnabled(bool(lines))
        self.pay_btn.setVisible(not paid)
        self.pay_btn.setEnabled(bool(lines))
        self.pay_btn.setText(f"\U0001F4B5  Cobrar   {money(total)}")
        self.remove_paid_btn.setVisible(paid)

        if paid:
            payment = order["payment"]
            text = f"✔  COBRADO  ·  {payment['method']}  ·  {money(payment['total'])}"
            if payment.get("change"):
                text += f"\nCambio {money(payment['change'])} en {payment['change_method']}"
            self.paid_banner.setText(text)
        self.paid_banner.setVisible(paid)

    # ----------------------------------------------------------------
    #  Platos
    # ----------------------------------------------------------------
    def _refresh_plate_bar(self, table: str, order: dict):
        used = self.order_manager.used_plates(table)
        if table != self._plate_table:
            self._plate_table = table
            self.active_plate = used[-1] if used else 1
        clear_layout(self.plate_layout)
        self.plate_buttons = {}
        plates = sorted(set(used) | ({self.active_plate} - {0}))
        next_plate = min((plates[-1] if plates else 0) + 1, MAX_PLATES)
        options = [(plate, str(plate), f"Agregar al {plate_label(plate)}") for plate in plates]
        if next_plate not in plates:
            options.append((next_plate, "＋", f"Empezar el {plate_label(next_plate)}"))
        options.append((0, "Sin plato", "Los tacos que toques van sin plato asignado"))
        for plate, text, tooltip in options:
            button = make_button(text, "plateChip", tooltip=tooltip)
            button.setCheckable(True)
            button.setChecked(plate == self.active_plate)
            button.setEnabled(not order["paid"])
            if text == "＋":
                button.setProperty("newPlate", True)
            button.clicked.connect(lambda _c=False, p=plate: self.set_active_plate(p))
            self.plate_layout.addWidget(button)
            self.plate_buttons[plate] = button
        if self.active_plate:
            self.plate_hint.setText(f"Los tacos que toques van al {plate_label(self.active_plate)}. "
                                    f"Lo demás va sin plato.")
        else:
            self.plate_hint.setText("Los tacos que toques van sin plato.")

    def set_active_plate(self, plate: int):
        self.active_plate = plate
        table = self.current_table
        order = self.order_manager.get_order(table) if table else None
        if order is not None:
            self._refresh_plate_bar(table, order)

    def organize_plates(self):
        table = self._require_open_table("No se pueden cambiar los platos.")
        if not table:
            return
        if not self.order_manager.get_items(table):
            self.toast.show_message("Primero agrega platillos al pedido.", "warning")
            return
        PlateDialog(self.order_manager, table, self).exec()

    # ----------------------------------------------------------------
    #  Lineas del ticket
    # ----------------------------------------------------------------
    def _line(self, index: int):
        lines = self.order_manager.get_order_lines(self.current_table) if self.current_table else []
        return lines[index] if 0 <= index < len(lines) else None

    def change_line_qty(self, index: int, delta: int):
        table = self.current_table
        if not table:
            return
        try:
            if delta > 0:
                self.order_manager.add_to_line(table, index, delta)
            else:
                self.order_manager.remove_line(table, index, -delta)
        except (KeyError, ValueError, PermissionError) as e:
            self.toast.show_message(str(e), "error")

    def show_line_menu(self, index: int, anchor):
        line = self._line(index)
        if line is None:
            return
        menu = QMenu(self)
        menu.addAction("\U0001F4DD  Nota para cocina…", lambda _=False: self.edit_line_note(index))
        if self.order_manager.plate_applies(line["dish"]):
            self.fill_plate_menu(menu, index, line)
        menu.addSeparator()
        menu.addAction(f"\U0001F5D1  Quitar todo ({line['qty']})", lambda _=False: self.remove_whole_line(index))
        menu.exec(anchor.mapToGlobal(anchor.rect().bottomLeft()))

    def show_plate_menu(self, index: int, anchor):
        line = self._line(index)
        if line is None or not self.order_manager.plate_applies(line["dish"]):
            return
        menu = QMenu(self)
        self.fill_plate_menu(menu, index, line)
        menu.exec(anchor.mapToGlobal(anchor.rect().bottomLeft()))

    def fill_plate_menu(self, menu: QMenu, index: int, line: dict):
        """
        Opciones de plato de una linea de tacos. Con varias unidades se puede
        separar una sola (p. ej. de 3 tacos con queso, 1 a otro plato) o mover todas.
        """
        used = self.order_manager.used_plates(self.current_table)
        top = min(max(used + [line["plate"], 0]) + 1, MAX_PLATES)
        targets = [plate for plate in [*range(1, top + 1), 0] if plate != line["plate"]]

        def label(plate):
            suffix = "  (nuevo)" if plate and plate not in used else ""
            return f"{plate_label(plate)}{suffix}"

        if line["qty"] > 1:
            menu.addSection(f"Separar 1 de los {line['qty']} a…")
            for plate in targets:
                menu.addAction(f"✂  {label(plate)}", lambda _=False, p=plate: self.move_line(index, p, 1))
            menu.addSection(f"Mover los {line['qty']} a…")
        else:
            menu.addSection("Mover a…")
        for plate in targets:
            menu.addAction(f"\U0001F37D  {label(plate)}", lambda _=False, p=plate: self.move_line(index, p))

    def edit_line_note(self, index: int):
        line = self._line(index)
        if line is None:
            return
        note, ok = QInputDialog.getText(
            self, "Nota para cocina", f"{line['qty']}× {line['dish']} ({line['variant']})",
            text=line["note"])
        if not ok:
            return
        try:
            changed, already_sent = self.order_manager.set_line_note(self.current_table, index, note)
        except (KeyError, PermissionError) as e:
            self.toast.show_message(str(e), "error")
            return
        if changed and already_sent:
            self.toast.show_message(f"Nota guardada. {already_sent} ya salieron en comanda: avisa a cocina.",
                                    "warning", 5000)

    def move_line(self, index: int, plate: int, count: int = None):
        try:
            moved, already_sent = self.order_manager.move_line_to_plate(self.current_table, index, plate, count)
        except (KeyError, ValueError, PermissionError) as e:
            self.toast.show_message(str(e), "error")
            return
        what = f"{moved} separado al" if count else "Movido al"
        if already_sent:
            self.toast.show_message(f"{what} {plate_label(plate)}. {already_sent} ya salieron en "
                                    f"comanda: avisa a cocina.", "warning", 5000)
        elif moved:
            self.toast.show_message(f"{what} {plate_label(plate)}", "success", 1500)

    def remove_whole_line(self, index: int):
        line = self._line(index)
        if line is None:
            return
        reply = QMessageBox.question(
            self, "Quitar", f"¿Quitar {line['qty']}× {line['dish']} ({line['variant']}) del pedido?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            self.change_line_qty(index, -line["qty"])

    # ----------------------------------------------------------------
    #  Crear, renombrar, eliminar
    # ----------------------------------------------------------------
    def _require_table(self, message="Selecciona un pedido primero") -> str:
        table = self.current_table
        if not table:
            self.toast.show_message(message, "warning")
        return table

    def _require_open_table(self, action: str) -> str:
        table = self._require_table()
        if table and self.order_manager.is_paid(table):
            self.toast.show_message(f"Este pedido ya fue cobrado. {action}", "warning")
            return ""
        return table

    def add_pedido(self) -> bool:
        dialog = AddOrderDialog(self, occupied=self.order_manager.get_all_tables(),
                                table_count=int(self.config.get("numero_mesas", 13)))
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return False
        ok, result = self.order_manager.create_table(dialog.get_order_name(), dialog.get_order_type())
        if not ok:
            QMessageBox.warning(self, "Nombre en uso",
                                f"Ya existe un pedido con ese nombre.\nPrueba con: '{result}'.")
            return False
        self.select_order(result)
        self._focus_search()
        self.toast.show_message(
            f"Pedido {self.order_manager.get_order_number(result)} abierto para «{result}»", "success")
        return True

    def edit_table_name(self):
        table = self._require_open_table("No se puede renombrar.")
        if not table:
            return
        dialog = EditTableDialog(table, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        new_name = dialog.get_new_name()
        if not new_name:
            self.toast.show_message("Ingresa un nombre válido.", "warning")
            return
        if not self.order_manager.rename_table(table, new_name):
            suggestion = self.order_manager.suggest_name(new_name)
            QMessageBox.warning(self, "Nombre en uso",
                                f"Ya existe '{new_name}'.\nPrueba con: '{suggestion}'.")

    def delete_table(self):
        table = self._require_table()
        if not table:
            return
        if self.order_manager.is_paid(table):
            self.order_manager.delete_table(table)
            self.toast.show_message(f"«{table}» quitado de la lista (sigue en el Excel).", "info")
            return
        if self.order_manager.get_items(table):
            text = (f"«{table}» tiene platillos SIN cobrar.\n"
                    f"¿Eliminarlo de todas formas? Quedará registrado en la auditoría.")
        else:
            text = f"¿Eliminar el pedido «{table}»?"
        reply = QMessageBox.question(self, "Eliminar pedido", text,
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                     QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            self.order_manager.delete_table(table)

    def clear_paid_orders(self):
        removed = self.order_manager.remove_paid_orders()
        if removed:
            self.toast.show_message(f"{removed} pedido(s) cobrados quitados de la lista. "
                                    f"Siguen en el Excel del día.", "info")

    def set_order_type(self, order_type: str):
        table = self.current_table
        if not table:
            return
        try:
            self.order_manager.set_order_type(table, order_type)
        except PermissionError as e:
            self.toast.show_message(str(e), "error")
            self.refresh_ticket()

    # ================================================================
    #  Cobro
    # ================================================================
    def mark_as_paid(self):
        table = self._require_table()
        if not table:
            return
        if self.order_manager.is_paid(table):
            self.toast.show_message("Este pedido ya fue cobrado.", "info")
            return
        if not self.order_manager.get_items(table):
            self.toast.show_message("El pedido está vacío.", "warning")
            return
        total = self.order_manager.get_total(table)
        number = self.order_manager.get_order_number(table)

        if self.order_manager.get_order_type(table) == ORDER_TYPE_TAKEAWAY:
            delivery_dlg = DeliveryDialog(self, self.order_manager.get_delivery_details(table))
            if delivery_dlg.exec() != QDialog.DialogCode.Accepted:
                return
            self.order_manager.set_delivery_details(
                table, delivery_dlg.get_moto_cost(), delivery_dlg.get_moto_method())

        dialog = PaymentDialog(self, total=total, title=f"{number}  ·  {table}")
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            result = self.order_manager.register_payment(
                table,
                method=dialog.get_payment_method(),
                cash_amount=dialog.get_cash_amount(),
                qr_amount=dialog.get_qr_amount(),
                change_method=dialog.get_change_method(),
                expected_total=total,
            )
        except OrderChangedError as e:
            QMessageBox.warning(
                self, "El pedido cambió",
                f"Mientras cobrabas se agregaron platillos a «{table}».\n"
                f"Nuevo total: {money(e.new_total)}.\n\nRevisa el pedido y vuelve a cobrar.")
            return
        except (KeyError, ValueError, PermissionError) as e:
            QMessageBox.warning(self, "No se pudo cobrar", str(e))
            return
        except OSError as e:
            QMessageBox.critical(
                self, "Error al registrar la venta",
                f"No se pudo guardar la venta en disco: {e}\n\nEl pedido sigue abierto; intenta de nuevo.")
            return

        details = self.order_manager.get_payment_details(table)
        message = f"✔ Cobrado {number}  ·  {money(details['total'])}  ·  {details['method']}"
        if details["change"] > 0:
            message += f"  ·  Cambio {money(details['change'])} en {details['change_method']}"
        self.toast.show_message(message, "success", 6000)
        if not result.excel_ok:
            QMessageBox.warning(self, "Revisar Excel", f"La venta quedó registrada, pero:\n{result.message}")

    # ================================================================
    #  Impresion
    # ================================================================
    def print_html(self, body: str) -> bool:
        try:
            from PyQt6.QtGui import QFont, QTextDocument
            from PyQt6.QtPrintSupport import QPrintDialog, QPrinter

            printer = QPrinter(QPrinter.PrinterMode.HighResolution)
            dlg = QPrintDialog(printer, self)
            if dlg.exec() != QDialog.DialogCode.Accepted:
                return False
            doc = QTextDocument()
            doc.setDefaultFont(QFont("Arial", 10))
            doc.setHtml(body)
            doc.print(printer)
            self.toast.show_message("\U0001F5A8 Enviado a la impresora", "success")
            return True
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error al imprimir: {e}")
            return False

    def _ticket_header(self, table: str, order: dict, title: str) -> str:
        esc = html.escape
        now = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
        return (f"<p align='center' style='margin:0'><b style='font-size:15px'>{esc(self.local_name)}</b><br/>"
                f"{esc(title)}</p><hr/>"
                f"<p style='margin:0'><b style='font-size:15px'>{esc(order['number'])} - {esc(table)}</b><br/>"
                f"{esc(order['order_type'])}<br/>{now}</p><hr/>")

    def print_kitchen_ticket(self, reprint_all: bool = False):
        table = self._require_table("No hay nada para imprimir")
        if not table:
            return
        order = self.order_manager.get_order(table)
        lines = self.order_manager.get_order_lines(table, kitchen_pending_only=not reprint_all)
        if not lines:
            if not order["items"]:
                self.toast.show_message("El pedido está vacío.", "warning")
                return
            reply = QMessageBox.question(
                self, "Comanda",
                "Todos los platillos ya se enviaron a cocina.\n¿Reimprimir la comanda completa?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if reply != QMessageBox.StandardButton.Yes:
                return
            lines = self.order_manager.get_order_lines(table)
            reprint_all = True

        if self.print_html(self.kitchen_ticket_html(table, order, lines, reprint_all)):
            self.order_manager.mark_sent_to_kitchen(table)

    def kitchen_ticket_html(self, table: str, order: dict, lines: list, reprint_all: bool) -> str:
        """Comanda agrupada por plato para que cocina sepa como servir cada uno."""
        esc = html.escape
        title = "COMANDA COCINA" + (" (REIMPRESION)" if reprint_all else "")
        # Platos que cocina ya recibio: lo nuevo se agrega a ese plato
        sent_plates = {i.get("plate", 0) for i in order["items"] if i.get("kitchen_sent")}
        with_plates = any(line["plate"] for line in lines)
        body = [self._ticket_header(table, order, title)]
        for plate, plate_lines in group_lines_by_plate(lines):
            if with_plates:
                heading = plate_label(plate).upper() if plate else "SIN PLATO"
                if plate and plate in sent_plates and not reprint_all:
                    heading += " (agregar)"
                body.append(f"<p style='margin:8px 0 2px 0'><b style='font-size:17px'>"
                            f"== {esc(heading)} ==</b></p>")
            body.append("<table width='100%' cellpadding='2'>")
            for line in plate_lines:
                body.append(f"<tr><td valign='top' width='36'><b style='font-size:15px'>{line['qty']}x</b></td>"
                            f"<td><b style='font-size:15px'>{esc(line['dish'])}</b> ({esc(line['variant'])})")
                if line["note"]:
                    body.append(f"<br/><i>&gt;&gt; {esc(line['note'])}</i>")
                body.append("</td></tr>")
            body.append("</table>")
        body.append("<hr/>")
        return "".join(body)

    def print_customer_bill(self):
        table = self._require_table("No hay nada para imprimir")
        if not table:
            return
        order = self.order_manager.get_order(table)
        lines = self.order_manager.get_order_lines(table)
        if not lines:
            self.toast.show_message("El pedido está vacío.", "warning")
            return
        esc = html.escape
        total = sum(l["subtotal"] for l in lines)
        # Al cliente no le importa el plato ni la nota: se suman las lineas iguales
        bill_lines = {}
        for line in lines:
            key = (line["dish"], line["variant"], line["unit_price"])
            entry = bill_lines.setdefault(key, [0, 0.0])
            entry[0] += line["qty"]
            entry[1] += line["subtotal"]
        body = [self._ticket_header(table, order, "CUENTA"), "<table width='100%' cellpadding='2'>"]
        for (dish, variant, _price), (qty, subtotal) in bill_lines.items():
            body.append(f"<tr><td>{qty}x {esc(dish)} ({esc(variant)})</td>"
                        f"<td align='right'>{subtotal:.2f}</td></tr>")
        body.append(f"</table><hr/><p align='right' style='font-size:15px'><b>TOTAL: {money(total)}</b></p>")
        delivery = order.get("delivery")
        if delivery and order["order_type"] == ORDER_TYPE_TAKEAWAY and delivery.get("moto_cost"):
            body.append(f"<p>Moto: {money(delivery['moto_cost'])} ({esc(delivery['moto_payment_method'])})</p>")
        payment = order.get("payment")
        if payment:
            body.append(f"<p>Pagado: {esc(payment['method'])}")
            if payment.get("change"):
                body.append(f"<br/>Recibido: {money(payment['amount_paid'])} - Cambio: {money(payment['change'])}")
            body.append("</p>")
        body.append("<p align='center'>¡Gracias por tu visita!<br/>No la mires mucho, se te va a antojar</p>")
        self.print_html("".join(body))

    # ================================================================
    #  Reportes y respaldos
    # ================================================================
    def show_day_summary(self):
        DaySummaryDialog(self.order_manager, self.local_name, self,
                         colors=self.theme_manager.get_current_theme()).exec()

    def save_to_excel(self):
        today = self.order_manager.today()
        folder = os.path.dirname(self.order_manager.daily_excel_path(today))
        filename = os.path.join(folder, f"respaldo_{today:%Y-%m-%d}_{datetime.datetime.now():%H%M}.xlsx")
        ok, message = self.order_manager.export_snapshot(filename)
        daily_ok, daily_message = self.order_manager.refresh_daily_excel(today)
        if not ok:
            QMessageBox.critical(self, "Error", f"Error al exportar: {message}")
            return
        if daily_ok:
            self.toast.show_message(f"\U0001F4BE Respaldo guardado: {os.path.basename(filename)}", "success", 4000)
        else:
            self.toast.show_message(f"Respaldo guardado, pero: {daily_message}", "warning", 7000)

    def open_data_folder(self):
        folder = os.path.dirname(self.order_manager.daily_excel_path())
        QDesktopServices.openUrl(QUrl.fromLocalFile(folder))
