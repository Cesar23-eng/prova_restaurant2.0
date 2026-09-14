import datetime
import html
import os

from PyQt6.QtCore import QSize, Qt, QTimer, QUrl, pyqtSignal
from PyQt6.QtGui import QColor, QDesktopServices, QFont, QKeySequence, QPalette, QPixmap, QShortcut
from PyQt6.QtWidgets import (
    QApplication, QCompleter, QComboBox, QDialog, QFrame, QGridLayout, QHBoxLayout, QInputDialog, QLabel,
    QLineEdit, QListWidget, QListWidgetItem, QMainWindow, QMenu, QMessageBox, QPushButton,
    QSpinBox, QTextBrowser, QVBoxLayout, QWidget,
)

from models.menu import MenuData
from models.order import ORDER_TYPE_TAKEAWAY, ORDER_TYPES, OrderChangedError, OrderManager
from utils.config import app_dir, load_config, save_config_value
from utils.styles import ThemeManager
from views.dialogs import (
    AddOrderDialog, DaySummaryDialog, DeleteItemDialog, DeliveryDialog, EditTableDialog,
    PaymentDialog, money,
)

NO_TABLE_TEXT = "Seleccione una mesa o cree un nuevo pedido"


class ProvaRestaurant(QMainWindow):
    # Emitida desde cualquier hilo (p. ej. el servidor de meseros); Qt la entrega en el hilo de la UI
    orders_changed = pyqtSignal(str, str, dict)

    def __init__(self, order_manager: OrderManager = None, menu_data: MenuData = None,
                 config: dict = None):
        super().__init__()
        self.config = config or load_config()
        self.menu_data = menu_data or MenuData()
        self.order_manager = order_manager or OrderManager(
            cutoff_hour=int(self.config.get("hora_corte_jornada", 4)))
        self.theme_manager = ThemeManager(self.config.get("tema", "light"))
        self.local_name = self.config.get("nombre_local", "PROVA")
        self.waiter_pin = str(self.config.get("pin_meseros", ""))
        self.waiter_url = ""
        self.waiter_server = None

        self.quick_index = {}
        self._menu_snapshot = None
        self._completer_just_used = False

        self.setup_window()
        self.init_ui()
        self.apply_stylesheet()
        self.reload_menu()

        self.orders_changed.connect(self._on_orders_changed)
        self.order_manager.add_listener(
            lambda event, table, info: self.orders_changed.emit(event, table or "", dict(info)))
        self.refresh_table_list()

        # Si el dueño edita menu_precios.xlsx con la app abierta, se recarga solo
        self.menu_timer = QTimer(self)
        self.menu_timer.timeout.connect(self.reload_menu)
        self.menu_timer.start(10_000)

        if self.order_manager.restored_count:
            self.statusBar().showMessage(
                f"Se recuperaron {self.order_manager.restored_count} pedido(s) abiertos "
                f"de la sesion anterior.", 15_000)

    def setup_window(self):
        self.setWindowTitle("PROVA - Sistema de Pedidos")
        self.setGeometry(100, 100, 1200, 820)
        self.setMinimumSize(1100, 760)

    def init_ui(self):
        self.main_widget = QWidget()
        self.setCentralWidget(self.main_widget)
        self.main_layout = QHBoxLayout()
        self.main_widget.setLayout(self.main_layout)
        self.setup_left_panel()
        self.setup_right_panel()
        self.setup_status_bar()
        self.setup_shortcuts()

    @property
    def current_table(self):
        return self.order_manager.current_table

    # ----------------------------------------------------------------
    #  Servidor de meseros
    # ----------------------------------------------------------------
    def start_waiter_server(self):
        try:
            from server import WaiterServer, create_app, get_local_ip

            app = create_app(self.order_manager, self.menu_data, lambda: self.waiter_pin)
            self.waiter_server = WaiterServer(app)
            port = self.waiter_server.start(int(self.config.get("puerto_meseros", 5000)))
            self.waiter_url = f"http://{get_local_ip()}:{port}"
            self.server_label.setText(f"Meseros: {self.waiter_url}")
            self.setWindowTitle(f"PROVA - Sistema de Pedidos  |  Meseros: {self.waiter_url}")
        except Exception as e:
            self.server_label.setText("Servidor de meseros no disponible")
            self.statusBar().showMessage(f"No se pudo iniciar el servidor de meseros: {e}", 20_000)

    def show_waiter_access(self):
        if not self.waiter_url:
            QMessageBox.warning(self, "Meseros", "El servidor de meseros no esta activo.")
            return
        box = QMessageBox(self)
        box.setWindowTitle("Acceso de meseros")
        box.setText(
            f"<p>En el celular, conectado al mismo WiFi, abre:</p>"
            f"<h2>{html.escape(self.waiter_url)}</h2>"
            f"<p>PIN de meseros: <b style='font-size:20px'>{html.escape(self.waiter_pin)}</b></p>"
            f"<p style='color:gray'>Si no abre, permite la app en el Firewall de Windows "
            f"(redes privadas).</p>"
        )
        change = box.addButton("Cambiar PIN", QMessageBox.ButtonRole.ActionRole)
        box.addButton(QMessageBox.StandardButton.Close)
        box.exec()
        if box.clickedButton() is change:
            self.change_waiter_pin()

    def change_waiter_pin(self):
        pin, ok = QInputDialog.getText(self, "Cambiar PIN", "Nuevo PIN (4 a 8 digitos):",
                                       text=self.waiter_pin)
        pin = (pin or "").strip()
        if not ok:
            return
        if not pin.isdigit() or not 4 <= len(pin) <= 8:
            QMessageBox.warning(self, "PIN invalido", "El PIN debe tener entre 4 y 8 digitos.")
            return
        self.waiter_pin = pin
        save_config_value("pin_meseros", pin, self.order_manager.root)
        self.statusBar().showMessage("PIN actualizado. Los meseros deberan ingresarlo de nuevo.", 8000)

    # ----------------------------------------------------------------
    #  Confirmacion al cerrar
    # ----------------------------------------------------------------
    def closeEvent(self, event):
        open_tables = self.order_manager.pending_tables()
        if open_tables:
            names = ", ".join(open_tables)
            reply = QMessageBox.question(
                self,
                "Cerrar aplicacion",
                f"Hay {len(open_tables)} pedido(s) SIN cobrar:\n{names}\n\n"
                f"Quedan guardados y apareceran al volver a abrir la app.\n\n"
                f"\u00bfDeseas cerrar?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.No:
                event.ignore()
                return
        if self.waiter_server is not None:
            self.waiter_server.stop()
        event.accept()

    # ----------------------------------------------------------------
    #  Panel izquierdo
    # ----------------------------------------------------------------
    def setup_left_panel(self):
        self.left_panel = QFrame()
        self.left_panel.setObjectName("leftPanel")
        self.left_panel.setMaximumWidth(360)

        layout = QVBoxLayout()
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)
        self.left_panel.setLayout(layout)

        self.setup_logo(layout)

        title = QLabel("PROVA")
        title.setFont(QFont("Arial", 28, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setObjectName("appTitle")
        layout.addWidget(title)

        subtitle = QLabel("Sistema de Pedidos")
        subtitle.setFont(QFont("Arial", 12))
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setObjectName("appSubtitle")
        layout.addWidget(subtitle)

        self.tables_label = QLabel("Mesas/Clientes:")
        layout.addWidget(self.tables_label)
        self.table_list = QListWidget()
        self.table_list.setObjectName("tableList")
        self.table_list.setFont(QFont("Arial", 11))
        self.table_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.table_list.setWordWrap(True)
        self.table_list.currentItemChanged.connect(self._on_current_item_changed)
        layout.addWidget(self.table_list)

        self.setup_left_panel_buttons(layout)
        self.main_layout.addWidget(self.left_panel)

    def setup_logo(self, layout):
        self.local_image_label = QLabel()
        self.local_image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.local_image_label.setFixedSize(300, 160)

        pixmap = QPixmap()
        for name in ("prova.png", "PROVA.png"):
            path = os.path.join(app_dir(), name)
            if os.path.exists(path):
                pixmap = QPixmap(path)
                break

        if not pixmap.isNull():
            scaled = pixmap.scaled(
                self.local_image_label.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            self.local_image_label.setPixmap(scaled)
        else:
            self.local_image_label.setText("Logo del Local\n(prova.png)")
            self.local_image_label.setStyleSheet("""
                background-color: #F0F0F0;
                border: 2px dashed #AAAAAA;
                color: #666666;
                font-weight: bold;
            """)
        layout.addWidget(self.local_image_label)

    def setup_left_panel_buttons(self, layout):
        btn_layout = QGridLayout()
        btn_layout.setSpacing(10)

        self.add_table_btn    = self.create_fancy_button("Nuevo Pedido",  "primary",   self.add_pedido)
        self.edit_table_btn   = self.create_fancy_button("Editar",        "secondary", self.edit_table_name)
        self.delete_table_btn = self.create_fancy_button("Eliminar",      "danger",    self.delete_table)
        self.summary_btn      = self.create_fancy_button("Resumen del dia", "success", self.show_day_summary)
        self.theme_toggle_btn = self.create_fancy_button("Cambiar Tema",  "accent",    self.toggle_theme)
        self.add_table_btn.setToolTip("Ctrl+N")

        btn_layout.addWidget(self.add_table_btn,    0, 0)
        btn_layout.addWidget(self.edit_table_btn,   0, 1)
        btn_layout.addWidget(self.delete_table_btn, 1, 0)
        btn_layout.addWidget(self.theme_toggle_btn, 1, 1)
        btn_layout.addWidget(self.summary_btn,      2, 0, 1, 2)
        layout.addLayout(btn_layout)

    # ----------------------------------------------------------------
    #  Panel derecho
    # ----------------------------------------------------------------
    def setup_right_panel(self):
        self.right_panel = QFrame()
        self.right_panel.setObjectName("rightPanel")

        layout = QVBoxLayout()
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(12)
        self.right_panel.setLayout(layout)

        self.current_order_header = QLabel("Pedido Actual")
        self.current_order_header.setFont(QFont("Arial", 18, QFont.Weight.Bold))
        self.current_order_header.setObjectName("orderHeader")
        layout.addWidget(self.current_order_header)

        self.table_info = QLabel(NO_TABLE_TEXT)
        self.table_info.setFont(QFont("Arial", 12))
        self.table_info.setObjectName("tableInfo")
        layout.addWidget(self.table_info)

        self.menu_warning = QLabel()
        self.menu_warning.setObjectName("menuWarning")
        self.menu_warning.setWordWrap(True)
        self.menu_warning.hide()
        layout.addWidget(self.menu_warning)

        self.setup_menu_selectors(layout)
        self.setup_quick_search(layout)
        self.setup_action_buttons(layout)

        self.order_display = QTextBrowser()
        self.order_display.setObjectName("orderDisplay")
        self.order_display.setFont(QFont("Arial", 12))
        self.order_display.setOpenLinks(False)
        layout.addWidget(self.order_display, 1)

        bottom = QHBoxLayout()
        self.export_btn = self.create_fancy_button("Exportar respaldo del dia", "accent", self.save_to_excel)
        self.open_folder_btn = self.create_fancy_button("Abrir carpeta de ventas", "secondary", self.open_data_folder)
        bottom.addWidget(self.export_btn)
        bottom.addWidget(self.open_folder_btn)
        layout.addLayout(bottom)

        self.main_layout.addWidget(self.right_panel)

    def setup_status_bar(self):
        self.server_label = QLabel("Iniciando servidor de meseros...")
        self.waiter_access_btn = QPushButton("Acceso meseros / PIN")
        self.waiter_access_btn.setObjectName("secondaryButton")
        self.waiter_access_btn.clicked.connect(self.show_waiter_access)
        self.statusBar().addPermanentWidget(self.server_label)
        self.statusBar().addPermanentWidget(self.waiter_access_btn)

    def setup_shortcuts(self):
        QShortcut(QKeySequence("Ctrl+N"), self, activated=self.add_pedido)
        QShortcut(QKeySequence("F9"), self, activated=self.mark_as_paid)
        QShortcut(QKeySequence("Ctrl+P"), self, activated=self.print_customer_bill)
        QShortcut(QKeySequence("Ctrl+K"), self, activated=lambda: self.search_input.setFocus())

    # ----------------------------------------------------------------
    #  Selectores de menu
    # ----------------------------------------------------------------
    def setup_menu_selectors(self, layout):
        form_layout = QGridLayout()
        form_layout.setHorizontalSpacing(12)
        form_layout.setVerticalSpacing(8)

        def label(text):
            lbl = QLabel(text)
            lbl.setFont(QFont("Arial", 12))
            return lbl

        self.category_combo = QComboBox()
        self.category_combo.setObjectName("categoryCombo")
        self.category_combo.currentIndexChanged.connect(self.update_dishes)
        form_layout.addWidget(label("Categoria:"), 0, 0)
        form_layout.addWidget(self.category_combo, 0, 1)

        self.dish_combo = QComboBox()
        self.dish_combo.setObjectName("dishCombo")
        self.dish_combo.currentIndexChanged.connect(self.update_variants)
        form_layout.addWidget(label("Platillo:"), 0, 2)
        form_layout.addWidget(self.dish_combo, 0, 3)

        self.variant_combo = QComboBox()
        self.variant_combo.setObjectName("variantCombo")
        form_layout.addWidget(label("Variante:"), 1, 0)
        form_layout.addWidget(self.variant_combo, 1, 1)

        self.qty_spin = QSpinBox()
        self.qty_spin.setRange(1, 50)
        form_layout.addWidget(label("Cantidad:"), 1, 2)
        form_layout.addWidget(self.qty_spin, 1, 3)

        self.note_input = QLineEdit()
        self.note_input.setMaxLength(120)
        self.note_input.setPlaceholderText("Nota para cocina (opcional): sin cebolla, bien cocido...")
        self.note_input.returnPressed.connect(self.add_order)
        form_layout.addWidget(label("Nota:"), 2, 0)
        form_layout.addWidget(self.note_input, 2, 1)

        self.order_type_combo = QComboBox()
        self.order_type_combo.addItems(ORDER_TYPES)
        self.order_type_combo.setObjectName("orderTypeCombo")
        self.order_type_combo.setEnabled(False)
        self.order_type_combo.activated.connect(self.set_order_type)
        form_layout.addWidget(label("Tipo de Consumo:"), 2, 2)
        form_layout.addWidget(self.order_type_combo, 2, 3)

        form_layout.setColumnStretch(1, 1)
        form_layout.setColumnStretch(3, 1)
        layout.addLayout(form_layout)

    def setup_action_buttons(self, layout):
        action_layout = QHBoxLayout()
        action_layout.setSpacing(12)

        self.add_item_btn    = self.create_fancy_button("Agregar",  "success",   self.add_order)
        self.remove_item_btn = self.create_fancy_button("Quitar",   "warning",   self.delete_platillo)
        self.pay_btn         = self.create_fancy_button("Cobrar (F9)", "primary", self.mark_as_paid)
        self.print_btn       = self.create_fancy_button("Imprimir", "secondary", lambda: None)

        print_menu = QMenu(self)
        print_menu.addAction("Comanda para cocina (solo lo nuevo)", self.print_kitchen_ticket)
        print_menu.addAction("Comanda para cocina (todo el pedido)",
                             lambda: self.print_kitchen_ticket(reprint_all=True))
        print_menu.addAction("Cuenta para el cliente   Ctrl+P", self.print_customer_bill)
        self.print_btn.setMenu(print_menu)

        action_layout.addWidget(self.add_item_btn)
        action_layout.addWidget(self.remove_item_btn)
        action_layout.addWidget(self.pay_btn)
        action_layout.addWidget(self.print_btn)
        layout.addLayout(action_layout)

    def create_fancy_button(self, text, color_type, callback):
        btn = QPushButton(text)
        btn.setFont(QFont("Arial", 11, QFont.Weight.Bold))
        btn.setObjectName(f"{color_type}Button")
        btn.clicked.connect(lambda _checked=False: callback())
        return btn

    # ----------------------------------------------------------------
    #  Tema
    # ----------------------------------------------------------------
    def apply_stylesheet(self):
        self.setStyleSheet(self.theme_manager.get_stylesheet())
        palette = self.palette()
        theme = self.theme_manager.get_current_theme()
        palette.setColor(QPalette.ColorRole.Window, QColor(theme["background"]))
        self.setPalette(palette)

    def toggle_theme(self):
        self.theme_manager.toggle_theme()
        self.apply_stylesheet()
        self.refresh_table_list()
        self.update_order_display()
        try:
            save_config_value("tema", self.theme_manager.current_theme, self.order_manager.root)
        except OSError:
            pass

    # ----------------------------------------------------------------
    #  Menu
    # ----------------------------------------------------------------
    def reload_menu(self):
        menu = self.menu_data.get_menu_prices()
        if self.menu_data.last_error:
            self.menu_warning.setText(f"{self.menu_data.last_error}\n"
                                      f"Coloca menu_precios.xlsx junto al programa.")
            self.menu_warning.show()
        else:
            self.menu_warning.hide()
        if menu is self._menu_snapshot:
            return
        self._menu_snapshot = menu

        previous = (self.category_combo.currentText(), self.dish_combo.currentText(),
                    self.variant_combo.currentText())
        self.category_combo.blockSignals(True)
        self.category_combo.clear()
        self.category_combo.addItems(menu.keys())
        if previous[0] in menu:
            self.category_combo.setCurrentText(previous[0])
        self.category_combo.blockSignals(False)
        self.update_dishes()
        if previous[1]:
            self.dish_combo.setCurrentText(previous[1])
        if previous[2]:
            self.variant_combo.setCurrentText(previous[2])

        self._build_quick_index()
        self.completer.model().setStringList(list(self.quick_index.keys()))
        has_menu = bool(menu)
        for widget in (self.add_item_btn, self.search_add_btn):
            widget.setEnabled(has_menu)

    def update_dishes(self):
        menu = self.menu_data.get_menu_prices()
        self.dish_combo.blockSignals(True)
        self.dish_combo.clear()
        self.dish_combo.addItems(menu.get(self.category_combo.currentText(), {}).keys())
        self.dish_combo.blockSignals(False)
        self.update_variants()

    def update_variants(self):
        menu = self.menu_data.get_menu_prices()
        variants = menu.get(self.category_combo.currentText(), {}).get(self.dish_combo.currentText(), {})
        self.variant_combo.clear()
        for variant, price in variants.items():
            self.variant_combo.addItem(f"{variant}  -  {money(price)}", variant)

    def set_order_type(self, _index=None):
        table = self.current_table
        if not table:
            return
        order_type = self.order_type_combo.currentText()
        try:
            self.order_manager.set_order_type(table, order_type)
        except PermissionError as e:
            QMessageBox.warning(self, "Pedido pagado", str(e))
            self.order_type_combo.setCurrentText(self.order_manager.get_order_type(table))

    # ----------------------------------------------------------------
    #  Lista de pedidos
    # ----------------------------------------------------------------
    def _on_orders_changed(self, event: str, table: str, info: dict):
        if event == "renamed" and info.get("old_name") == self.current_table:
            self.order_manager.set_current_table(table)
        if event == "deleted" and table == self.current_table:
            self.order_manager.set_current_table(None)
        self.refresh_table_list()
        self.update_order_display()
        if info.get("source") == "mesero":
            if event == "created":
                self.statusBar().showMessage(f"Un mesero creo el pedido '{table}'", 10_000)
            elif event == "items_added":
                self.statusBar().showMessage(
                    f"Un mesero agrego {info.get('count', 0)} platillo(s) a '{table}'", 10_000)
                QApplication.beep()

    def refresh_table_list(self):
        theme = self.theme_manager.get_current_theme()
        tables = self.order_manager.get_all_tables()
        self.table_list.blockSignals(True)
        self.table_list.clear()
        selected_item = None
        pending = 0
        for name in tables:
            order = self.order_manager.get_order(name)
            if order is None:
                continue
            total = sum(i["price"] for i in order["items"])
            icon = "\U0001F6F5" if order["order_type"] == ORDER_TYPE_TAKEAWAY else "\U0001F37D"
            title = f"{order['number']}  {icon} {name}"
            if order["paid"]:
                status = f"✔ PAGADO {money(total)}"
            else:
                status = f"{len(order['items'])} items - {money(total)}"
                kitchen = sum(1 for i in order["items"] if not i.get("kitchen_sent"))
                if kitchen:
                    # Campana: platillos que aun no salieron en una comanda de cocina
                    title += f"   \U0001F514{kitchen}"
            item = QListWidgetItem(f"{title}\n     {status}")
            # Con hoja de estilos Qt calcula la altura de una sola linea; se fija para dos
            item.setSizeHint(QSize(0, 2 * self.table_list.fontMetrics().lineSpacing() + 34))
            item.setData(Qt.ItemDataRole.UserRole, name)
            item.setToolTip(f"{order['number']} - {name}\n{order['order_type']}\n{status}")
            if order["paid"]:
                # La hoja de estilos ignora el color de fondo por item; se marca con el texto
                font = item.font()
                font.setItalic(True)
                item.setFont(font)
                item.setForeground(QColor(theme["success"]))
            elif order["items"]:
                pending += 1
            self.table_list.addItem(item)
            if name == self.current_table:
                selected_item = item
        if selected_item is not None:
            self.table_list.setCurrentItem(selected_item)
        elif self.current_table not in tables:
            self.order_manager.set_current_table(None)
        self.table_list.blockSignals(False)
        self.tables_label.setText(f"Mesas/Clientes ({pending} por cobrar):")

    def _on_current_item_changed(self, current, _previous):
        if current is None:
            return
        self.select_table(current)

    def select_table(self, item):
        table_name = item.data(Qt.ItemDataRole.UserRole)
        self.order_manager.set_current_table(table_name)
        self.update_order_display()

    # ----------------------------------------------------------------
    #  CRUD de pedidos
    # ----------------------------------------------------------------
    def _require_table(self, message="Selecciona un pedido primero") -> str:
        table = self.current_table
        if not table:
            QMessageBox.warning(self, "Sin pedido", message)
        return table

    def _require_open_table(self, action: str) -> str:
        table = self._require_table()
        if table and self.order_manager.is_paid(table):
            QMessageBox.warning(self, "Pedido pagado", f"Este pedido ya fue pagado.\n{action}")
            return ""
        return table

    def add_pedido(self):
        suggestion = self.order_manager.suggest_name(f"Mesa {len(self.order_manager.get_all_tables()) + 1}")
        dialog = AddOrderDialog(self, suggested_name=suggestion)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        ok, result = self.order_manager.create_table(dialog.get_order_name(), dialog.get_order_type())
        if not ok:
            QMessageBox.warning(
                self, "Nombre en uso",
                f"Ya existe una mesa con ese nombre.\nPrueba con: '{result}'.",
            )
            return
        self.order_manager.set_current_table(result)
        self.refresh_table_list()
        self.update_order_display()
        self.search_input.setFocus()

    def edit_table_name(self):
        table = self._require_open_table("No se puede editar el nombre.")
        if not table:
            return
        dialog = EditTableDialog(table, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        new_name = dialog.get_new_name()
        if not new_name:
            QMessageBox.warning(self, "Nombre vacio", "Ingresa un nombre valido.")
            return
        if not self.order_manager.rename_table(table, new_name):
            suggestion = self.order_manager.suggest_name(new_name)
            QMessageBox.warning(
                self, "Nombre en uso",
                f"Ya existe '{new_name}'.\nPrueba con: '{suggestion}'.",
            )

    def delete_table(self):
        table = self._require_table()
        if not table:
            return
        if self.order_manager.is_paid(table):
            text = (f"El pedido '{table}' ya fue PAGADO y guardado en Excel.\n"
                    f"\u00bfDeseas quitarlo de la lista?")
        elif self.order_manager.get_items(table):
            text = (f"El pedido '{table}' tiene platillos SIN cobrar.\n"
                    f"\u00bfEliminarlo de todas formas? (quedara registrado en la auditoria)")
        else:
            text = f"\u00bfEliminar el pedido '{table}'?"
        reply = QMessageBox.question(
            self, "Confirmar", text,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.order_manager.delete_table(table)

    def _add_items(self, category, dish, variant, price):
        table = self._require_open_table("No se pueden agregar mas platillos.")
        if not table:
            return False
        try:
            self.order_manager.add_item(table, category, dish, variant, price,
                                        note=self.note_input.text(), qty=self.qty_spin.value())
        except (KeyError, ValueError, PermissionError) as e:
            QMessageBox.warning(self, "No se pudo agregar", str(e))
            return False
        self.qty_spin.setValue(1)
        self.note_input.clear()
        return True

    def add_order(self):
        category = self.category_combo.currentText()
        dish = self.dish_combo.currentText()
        variant = self.variant_combo.currentData()
        price = self.menu_data.get_price(category, dish, variant) if variant else None
        if price is None:
            QMessageBox.warning(self, "Menu", "Selecciona un platillo valido del menu.")
            return
        self._add_items(category, dish, variant, price)

    def delete_platillo(self):
        table = self._require_open_table("No se pueden quitar platillos.")
        if not table:
            return
        lines = self.order_manager.get_order_lines(table)
        if not lines:
            QMessageBox.warning(self, "Pedido vacio", "No hay platillos para quitar")
            return
        dialog = DeleteItemDialog(lines, self)
        if dialog.exec() == QDialog.DialogCode.Accepted and dialog.get_selected_index() is not None:
            try:
                self.order_manager.remove_line(table, dialog.get_selected_index(),
                                               dialog.get_selected_count())
            except (KeyError, PermissionError) as e:
                QMessageBox.warning(self, "No se pudo quitar", str(e))

    # ----------------------------------------------------------------
    #  Display del pedido
    # ----------------------------------------------------------------
    def update_order_display(self):
        table = self.current_table
        order = self.order_manager.get_order(table) if table else None
        if order is None:
            self.order_display.clear()
            self.table_info.setText(NO_TABLE_TEXT)
            self.order_type_combo.setEnabled(False)
            return

        theme = self.theme_manager.get_current_theme()
        self.table_info.setText(f"Mesa: {table}   ({order['number']})")
        self.order_type_combo.setCurrentText(order["order_type"])
        self.order_type_combo.setEnabled(not order["paid"])

        esc = html.escape
        lines = self.order_manager.get_order_lines(table)
        total = sum(l["subtotal"] for l in lines)
        parts = [f"<h3 style='margin:0'>{esc(order['number'])} - {esc(table)}</h3>"]
        info = [f"Tipo: <b>{esc(order['order_type'])}</b>"]
        if order["paid"]:
            payment = order["payment"]
            status = f"<b style='color:{theme['success']}'>PAGADO ({esc(payment['method'])})</b>"
            if payment.get("change"):
                status += f" - Cambio: {money(payment['change'])} en {esc(payment['change_method'])}"
        else:
            status = f"<b style='color:{theme['danger']}'>PENDIENTE</b>"
        info.append(f"Estado: {status}")
        delivery = order.get("delivery")
        if delivery and order["order_type"] == ORDER_TYPE_TAKEAWAY:
            info.append(f"Moto: {money(delivery['moto_cost'])} ({esc(delivery['moto_payment_method'])})")
        parts.append("<p style='margin:4px 0 8px 0'>" + " &nbsp;|&nbsp; ".join(info) + "</p>")

        if lines:
            parts.append("<table width='100%' cellspacing='0' cellpadding='4'>")
            for line in lines:
                name = f"{line['qty']} x {esc(line['dish'])} ({esc(line['variant'])})"
                if line["note"]:
                    name += f"<br/><i style='color:{theme['note']}'>&nbsp;&nbsp;Nota: {esc(line['note'])}</i>"
                parts.append(f"<tr><td>{name}</td>"
                             f"<td align='right' width='110'>{money(line['subtotal'])}</td></tr>")
            parts.append("</table>")
        else:
            parts.append("<p><i>Pedido vacio. Agrega platillos con el menu o la busqueda rapida.</i></p>")
        parts.append(f"<hr/><p style='font-size:17px'><b>TOTAL: {money(total)}</b></p>")
        self.order_display.setHtml("".join(parts))

    # ----------------------------------------------------------------
    #  Pago
    # ----------------------------------------------------------------
    def mark_as_paid(self):
        table = self._require_table()
        if not table:
            return
        if self.order_manager.is_paid(table):
            QMessageBox.information(self, "Ya pagado", "Este pedido ya fue registrado como pagado.")
            return
        total = self.order_manager.get_total(table)
        if not self.order_manager.get_items(table):
            QMessageBox.warning(self, "Pedido vacio", "El pedido esta vacio")
            return

        if self.order_manager.get_order_type(table) == ORDER_TYPE_TAKEAWAY:
            delivery_dlg = DeliveryDialog(self, self.order_manager.get_delivery_details(table))
            if delivery_dlg.exec() != QDialog.DialogCode.Accepted:
                return
            self.order_manager.set_delivery_details(
                table, delivery_dlg.get_moto_cost(), delivery_dlg.get_moto_method())

        dialog = PaymentDialog(self, total=total)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        method = dialog.get_payment_method()
        try:
            result = self.order_manager.register_payment(
                table,
                method=method,
                cash_amount=dialog.get_cash_amount(),
                qr_amount=dialog.get_qr_amount(),
                change_method=dialog.get_change_method(),
                expected_total=total,
            )
        except OrderChangedError as e:
            QMessageBox.warning(
                self, "El pedido cambio",
                f"Mientras cobrabas se agregaron platillos a '{table}'.\n"
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
        number = self.order_manager.get_order_number(table)
        msg = (f"Pago registrado exitosamente\n\n"
               f"Pedido: {number} - {table}\n"
               f"Total: Bs. {details['total']:.2f}\n"
               f"Metodo: {method}\n")
        if method in ("Efectivo", "Mixto"):
            if method == "Mixto":
                msg += f"Efectivo: Bs. {details['cash_amount']:.2f}\nQR: Bs. {details['qr_amount']:.2f}\n"
            else:
                msg += f"Recibido: Bs. {details['cash_amount']:.2f}\n"
            if details["change"] > 0:
                msg += f"CAMBIO: Bs. {details['change']:.2f} en {details['change_method']}\n"

        if result.excel_ok:
            QMessageBox.information(self, "Pago Confirmado",
                                    msg + "\nGuardado automaticamente en el Excel del dia.")
        else:
            QMessageBox.warning(self, "Pago Confirmado (revisar Excel)",
                                msg + f"\nLa venta quedo registrada, pero:\n{result.message}")

    # ----------------------------------------------------------------
    #  Imprimir
    # ----------------------------------------------------------------
    def print_html(self, body: str) -> bool:
        try:
            from PyQt6.QtGui import QTextDocument
            from PyQt6.QtPrintSupport import QPrintDialog, QPrinter

            printer = QPrinter(QPrinter.PrinterMode.HighResolution)
            dlg = QPrintDialog(printer, self)
            if dlg.exec() != QDialog.DialogCode.Accepted:
                return False
            doc = QTextDocument()
            doc.setDefaultFont(QFont("Arial", 10))
            doc.setHtml(body)
            doc.print(printer)
            self.statusBar().showMessage("Enviado a la impresora", 5000)
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
                QMessageBox.warning(self, "Pedido vacio", "No hay nada para imprimir")
                return
            reply = QMessageBox.question(
                self, "Comanda",
                "Todos los platillos ya se enviaron a cocina.\n\u00bfReimprimir la comanda completa?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if reply != QMessageBox.StandardButton.Yes:
                return
            lines = self.order_manager.get_order_lines(table)
            reprint_all = True

        esc = html.escape
        title = "COMANDA COCINA" + (" (REIMPRESION)" if reprint_all else "")
        body = [self._ticket_header(table, order, title), "<table width='100%' cellpadding='2'>"]
        for line in lines:
            body.append(f"<tr><td valign='top' width='36'><b style='font-size:15px'>{line['qty']}x</b></td>"
                        f"<td><b style='font-size:15px'>{esc(line['dish'])}</b> ({esc(line['variant'])})")
            if line["note"]:
                body.append(f"<br/><i>&gt;&gt; {esc(line['note'])}</i>")
            body.append("</td></tr>")
        body.append("</table><hr/>")
        if self.print_html("".join(body)):
            self.order_manager.mark_sent_to_kitchen(table)

    def print_customer_bill(self):
        table = self._require_table("No hay nada para imprimir")
        if not table:
            return
        order = self.order_manager.get_order(table)
        lines = self.order_manager.get_order_lines(table)
        if not lines:
            QMessageBox.warning(self, "Pedido vacio", "No hay nada para imprimir")
            return
        esc = html.escape
        total = sum(l["subtotal"] for l in lines)
        body = [self._ticket_header(table, order, "CUENTA"), "<table width='100%' cellpadding='2'>"]
        for line in lines:
            body.append(f"<tr><td>{line['qty']}x {esc(line['dish'])} ({esc(line['variant'])})</td>"
                        f"<td align='right'>{line['subtotal']:.2f}</td></tr>")
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
        body.append("<p align='center'>Gracias por su preferencia!</p>")
        self.print_html("".join(body))

    # ----------------------------------------------------------------
    #  Busqueda rapida
    # ----------------------------------------------------------------
    def _build_quick_index(self):
        self.quick_index.clear()
        menu = self.menu_data.get_menu_prices()
        for category, dishes in menu.items():
            for dish, variants in dishes.items():
                for variant, price in variants.items():
                    label = f"{dish} ({variant}) - {money(price)}"
                    self.quick_index[label] = (category, dish, variant, float(price))

    def setup_quick_search(self, parent_layout):
        from PyQt6.QtCore import QStringListModel

        row = QHBoxLayout()
        lbl = QLabel("Busqueda rapida (Ctrl+K):")
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Ej: taco, birria, horchata...")

        self.completer = QCompleter(QStringListModel([], self), self)
        self.completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.completer.setFilterMode(Qt.MatchFlag.MatchContains)
        self.completer.setMaxVisibleItems(12)
        self.search_input.setCompleter(self.completer)

        self.search_add_btn = self.create_fancy_button("Agregar", "success", self.on_quick_add)
        self.search_input.returnPressed.connect(self.on_quick_add)
        self.completer.activated[str].connect(self.on_quick_choose)

        row.addWidget(lbl)
        row.addWidget(self.search_input, 1)
        row.addWidget(self.search_add_btn)
        parent_layout.addLayout(row)

    def on_quick_choose(self, text: str):
        # Enter sobre la lista dispara activated y luego returnPressed: se agrega una sola vez
        self._completer_just_used = True
        QTimer.singleShot(0, lambda: setattr(self, "_completer_just_used", False))
        if text in self.quick_index:
            self._add_from_quick_key(text)

    def on_quick_add(self):
        if self._completer_just_used:
            return
        txt = (self.search_input.text() or "").strip()
        if not txt:
            return
        if txt in self.quick_index:
            self._add_from_quick_key(txt)
            return
        matches = [k for k in self.quick_index if txt.lower() in k.lower()]
        if len(matches) == 1:
            self._add_from_quick_key(matches[0])
        elif matches:
            self.completer.setCompletionPrefix(txt)
            self.completer.complete()
        else:
            QMessageBox.information(self, "Sin resultados", f"No encontre '{txt}'.")

    def _add_from_quick_key(self, key: str):
        category, dish, variant, price = self.quick_index[key]
        if self._add_items(category, dish, variant, price):
            QTimer.singleShot(0, self.search_input.clear)

    # ----------------------------------------------------------------
    #  Reportes y respaldos
    # ----------------------------------------------------------------
    def show_day_summary(self):
        DaySummaryDialog(self.order_manager, self.local_name, self).exec()

    def save_to_excel(self):
        today = self.order_manager.today()
        folder = os.path.dirname(self.order_manager.daily_excel_path(today))
        filename = os.path.join(folder, f"respaldo_{today:%Y-%m-%d}_{datetime.datetime.now():%H%M}.xlsx")
        ok, message = self.order_manager.export_snapshot(filename)
        daily_ok, daily_message = self.order_manager.refresh_daily_excel(today)
        if not ok:
            QMessageBox.critical(self, "Error", f"Error al exportar: {message}")
            return
        text = (f"Respaldo exportado a:\n{filename}\n\n"
                f"Incluye todos los pedidos en pantalla (pagados y pendientes).")
        if not daily_ok:
            text += f"\n\nAtencion: {daily_message}"
        QMessageBox.information(self, "Exito", text)

    def open_data_folder(self):
        folder = os.path.dirname(self.order_manager.daily_excel_path())
        QDesktopServices.openUrl(QUrl.fromLocalFile(folder))
