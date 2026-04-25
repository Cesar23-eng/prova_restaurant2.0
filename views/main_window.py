import os
import sys

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QListWidget, QComboBox, QTextEdit, QFrame,
    QDialog, QMessageBox, QLineEdit, QCompleter,
)
from PyQt6.QtGui import QFont, QPixmap, QColor, QPalette, QKeySequence, QShortcut
from PyQt6.QtCore import Qt
from models.menu import MenuData
from models.order import OrderManager
from views.dialogs import (
    AddOrderDialog, EditTableDialog, DeleteItemDialog,
    PaymentDialog, DeliveryDialog
)
from utils.styles import ThemeManager


class ProvaRestaurant(QMainWindow):
    def __init__(self):
        super().__init__()
        self.menu_data = MenuData()
        self.order_manager = OrderManager()
        self.theme_manager = ThemeManager()

        self.quick_index = {}
        self._build_quick_index()

        self.setup_window()
        self.init_ui()
        self.apply_stylesheet()

    def setup_window(self):
        self.setWindowTitle("PROVA - Sistema de Pedidos")
        self.setGeometry(100, 100, 1200, 800)
        self.setMinimumSize(1100, 750)

    def init_ui(self):
        self.main_widget = QWidget()
        self.setCentralWidget(self.main_widget)
        self.main_layout = QHBoxLayout()
        self.main_widget.setLayout(self.main_layout)
        self.setup_left_panel()
        self.setup_right_panel()

    # ----------------------------------------------------------------
    #  Panel izquierdo
    # ----------------------------------------------------------------
    def setup_left_panel(self):
        self.left_panel = QFrame()
        self.left_panel.setObjectName("leftPanel")
        self.left_panel.setMaximumWidth(350)

        layout = QVBoxLayout()
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
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

        self.table_list = QListWidget()
        self.table_list.setObjectName("tableList")
        self.table_list.setFont(QFont("Arial", 12))
        self.table_list.itemClicked.connect(self.select_table)
        layout.addWidget(QLabel("Mesas/Clientes:"))
        layout.addWidget(self.table_list)

        self.setup_left_panel_buttons(layout)
        self.main_layout.addWidget(self.left_panel)

    def setup_logo(self, layout):
        self.local_image_label = QLabel()
        self.local_image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.local_image_label.setFixedSize(300, 200)

        if getattr(sys, "frozen", False):
            app_dir = os.path.dirname(sys.executable)
        else:
            app_dir = os.path.dirname(os.path.abspath(sys.argv[0]))

        candidate_paths = [
            os.path.join(app_dir, "prova.png"),
            os.path.join(app_dir, "PROVA.png"),
        ]

        pixmap = QPixmap()
        for p in candidate_paths:
            if os.path.exists(p):
                pixmap = QPixmap(p)
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
        self.edit_table_btn   = self.create_fancy_button("Editar",         "secondary", self.edit_table_name)
        self.delete_table_btn = self.create_fancy_button("Eliminar",       "danger",    self.delete_table)
        self.theme_toggle_btn = self.create_fancy_button("Cambiar Tema",   "accent",    self.toggle_theme)

        btn_layout.addWidget(self.add_table_btn,    0, 0)
        btn_layout.addWidget(self.edit_table_btn,   0, 1)
        btn_layout.addWidget(self.delete_table_btn, 1, 0)
        btn_layout.addWidget(self.theme_toggle_btn, 1, 1)
        layout.addLayout(btn_layout)

    # ----------------------------------------------------------------
    #  Panel derecho
    # ----------------------------------------------------------------
    def setup_right_panel(self):
        self.right_panel = QFrame()
        self.right_panel.setObjectName("rightPanel")

        layout = QVBoxLayout()
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(20)
        self.right_panel.setLayout(layout)

        # Encabezado
        self.current_order_header = QLabel("Pedido Actual")
        self.current_order_header.setFont(QFont("Arial", 18, QFont.Weight.Bold))
        self.current_order_header.setObjectName("orderHeader")
        layout.addWidget(self.current_order_header)

        self.table_info = QLabel("Seleccione una mesa o cree un nuevo pedido")
        self.table_info.setFont(QFont("Arial", 12))
        self.table_info.setObjectName("tableInfo")
        layout.addWidget(self.table_info)

        # Selectores de menu + tipo de consumo
        self.setup_menu_selectors(layout)

        # Busqueda rapida
        self.setup_quick_search(layout)

        # Botones de accion
        self.setup_action_buttons(layout)

        # Display del pedido
        self.order_display = QTextEdit()
        self.order_display.setObjectName("orderDisplay")
        self.order_display.setFont(QFont("Arial", 12))
        self.order_display.setReadOnly(True)
        layout.addWidget(self.order_display)

        # Boton exportar
        self.export_btn = self.create_fancy_button("Exportar a Excel", "accent", self.save_to_excel)
        layout.addWidget(self.export_btn)

        self.main_layout.addWidget(self.right_panel)

    # ----------------------------------------------------------------
    #  Selectores de menu  (req. 3: tipo de consumo)
    # ----------------------------------------------------------------
    def setup_menu_selectors(self, layout):
        form_layout = QGridLayout()
        form_layout.setSpacing(15)

        # Categoria
        lbl_category = QLabel("Categoria:")
        lbl_category.setFont(QFont("Arial", 13))
        self.category_combo = QComboBox()
        self.category_combo.addItems(self.menu_data.get_menu_prices().keys())
        self.category_combo.setObjectName("categoryCombo")
        self.category_combo.currentIndexChanged.connect(self.update_dishes)
        form_layout.addWidget(lbl_category, 0, 0)
        form_layout.addWidget(self.category_combo, 0, 1)

        # Platillo
        lbl_dish = QLabel("Platillo:")
        lbl_dish.setFont(QFont("Arial", 13))
        self.dish_combo = QComboBox()
        self.dish_combo.setObjectName("dishCombo")
        self.dish_combo.currentIndexChanged.connect(self.update_variants)
        form_layout.addWidget(lbl_dish, 1, 0)
        form_layout.addWidget(self.dish_combo, 1, 1)

        # Variante
        lbl_variant = QLabel("Variante:")
        lbl_variant.setFont(QFont("Arial", 13))
        self.variant_combo = QComboBox()
        self.variant_combo.setObjectName("variantCombo")
        form_layout.addWidget(lbl_variant, 2, 0)
        form_layout.addWidget(self.variant_combo, 2, 1)

        # --- req. 3: Tipo de Consumo ---
        lbl_order_type = QLabel("Tipo de Consumo:")
        lbl_order_type.setFont(QFont("Arial", 13))
        self.order_type_combo = QComboBox()
        self.order_type_combo.addItems(["En el local", "Para llevar"])
        self.order_type_combo.setObjectName("orderTypeCombo")
        self.order_type_combo.currentTextChanged.connect(self.set_order_type)
        form_layout.addWidget(lbl_order_type, 3, 0)
        form_layout.addWidget(self.order_type_combo, 3, 1)

        layout.addLayout(form_layout)
        self.update_dishes()
        self.update_variants()

    def setup_action_buttons(self, layout):
        action_layout = QHBoxLayout()
        action_layout.setSpacing(15)

        self.add_item_btn    = self.create_fancy_button("Agregar",  "success",   self.add_order)
        self.remove_item_btn = self.create_fancy_button("Eliminar", "warning",   self.delete_platillo)
        self.pay_btn         = self.create_fancy_button("Pagar",    "primary",   self.mark_as_paid)
        self.print_btn       = self.create_fancy_button("Imprimir", "secondary", self.print_order)

        action_layout.addWidget(self.add_item_btn)
        action_layout.addWidget(self.remove_item_btn)
        action_layout.addWidget(self.pay_btn)
        action_layout.addWidget(self.print_btn)
        layout.addLayout(action_layout)

    def create_fancy_button(self, text, color_type, callback):
        btn = QPushButton(text)
        btn.setFont(QFont("Arial", 11, QFont.Weight.Bold))
        btn.setObjectName(f"{color_type}Button")
        btn.clicked.connect(callback)
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

    # ----------------------------------------------------------------
    #  Combos de menu
    # ----------------------------------------------------------------
    def update_dishes(self):
        current_category = self.category_combo.currentText()
        self.dish_combo.clear()
        self.dish_combo.addItems(self.menu_data.get_menu_prices()[current_category].keys())

    def update_variants(self):
        current_category = self.category_combo.currentText()
        current_dish = self.dish_combo.currentText()
        self.variant_combo.clear()
        menu = self.menu_data.get_menu_prices()
        if current_category in menu and current_dish in menu[current_category]:
            self.variant_combo.addItems(menu[current_category][current_dish].keys())

    def set_order_type(self, tipo):
        self.order_manager.set_order_type(tipo)

    # ----------------------------------------------------------------
    #  CRUD de pedidos
    # ----------------------------------------------------------------
    def add_pedido(self):
        dialog = AddOrderDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            name = dialog.get_order_name()
            ok, result = self.order_manager.create_table(name)
            if not ok:
                QMessageBox.warning(
                    self, "Nombre en uso",
                    f"Ya existe una mesa con ese nombre.\nPrueba con: '{result}'.",
                )
                return
            self.table_list.addItem(result)

    def select_table(self, item):
        table_name = item.text()
        self.order_manager.set_current_table(table_name)
        self.table_info.setText(f"Mesa: {table_name}")
        self.update_order_display()

    def edit_table_name(self):
        if not self.order_manager.current_table:
            QMessageBox.warning(self, "Error", "Selecciona un pedido primero")
            return
        dialog = EditTableDialog(self.order_manager.current_table, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            new_name = dialog.get_new_name()
            if not new_name.strip():
                QMessageBox.warning(self, "Nombre vacio", "Ingresa un nombre valido.")
                return
            if not self.order_manager.rename_table(self.order_manager.current_table, new_name):
                suggestion = self.order_manager.suggest_name(new_name)
                QMessageBox.warning(
                    self, "Nombre en uso",
                    f"Ya existe '{new_name}'.\nPrueba con: '{suggestion}'.",
                )
                return
            self.table_list.currentItem().setText(new_name)
            self.order_manager.set_current_table(new_name)
            self.table_info.setText(f"Mesa: {new_name}")

    def delete_table(self):
        if not self.order_manager.current_table:
            QMessageBox.warning(self, "Error", "Selecciona un pedido primero")
            return
        reply = QMessageBox.question(
            self, "Confirmar",
            f"Eliminar el pedido de {self.order_manager.current_table}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.order_manager.delete_table(self.order_manager.current_table)
            self.table_list.takeItem(self.table_list.row(self.table_list.currentItem()))
            self.order_manager.current_table = None
            self.table_info.setText("Seleccione una mesa o cree un nuevo pedido")
            self.order_display.clear()

    def add_order(self):
        if not self.order_manager.current_table:
            QMessageBox.warning(self, "Error", "Selecciona o crea un pedido primero")
            return
        category = self.category_combo.currentText()
        dish = self.dish_combo.currentText()
        variant = self.variant_combo.currentText()
        price = self.menu_data.get_menu_prices()[category][dish][variant]
        self.order_manager.add_item_to_order(category, dish, variant, price)
        self.update_order_display()

    def delete_platillo(self):
        if not self.order_manager.current_table or not self.order_manager.table_orders.get(
            self.order_manager.current_table
        ):
            QMessageBox.warning(self, "Error", "No hay platillos para eliminar")
            return
        dialog = DeleteItemDialog(
            self.order_manager.table_orders[self.order_manager.current_table], self
        )
        if dialog.exec() == QDialog.DialogCode.Accepted:
            index = dialog.get_selected_index()
            if index is not None:
                self.order_manager.remove_item_from_order(
                    self.order_manager.current_table, index
                )
                self.update_order_display()

    # ----------------------------------------------------------------
    #  Display del pedido
    # ----------------------------------------------------------------
    def update_order_display(self):
        if not self.order_manager.current_table:
            self.order_display.clear()
            return

        order_summary, total = self.order_manager.get_order_summary(
            self.order_manager.current_table
        )
        paid_status = self.order_manager.get_payment_status(self.order_manager.current_table)
        details = self.order_manager.get_payment_details(self.order_manager.current_table) or {}
        delivery = self.order_manager.get_delivery_details(self.order_manager.current_table) or {}

        text = f"=== {self.order_manager.current_table} ===\n"
        text += f"Tipo: {self.order_manager.order_type}\n"

        if paid_status[0]:
            method = paid_status[1]
            change = details.get("change", 0)
            change_method = details.get("change_method", "")
            text += f"Estado: PAGADO ({method})"
            if change > 0:
                text += f" | Cambio: Bs{change:.2f} en {change_method}"
            text += "\n"
        else:
            text += "Estado: PENDIENTE\n"

        if delivery:
            text += f"Moto: Bs{delivery.get('moto_cost', 0):.2f} ({delivery.get('moto_payment_method', '')})\n"

        text += "-" * 40 + "\n"
        for item, count in order_summary.items():
            price_per_unit = next(
                p["price"]
                for p in self.order_manager.table_orders[self.order_manager.current_table]
                if f"{p['dish']} ({p['variant']})" == item
            )
            subtotal = price_per_unit * count
            text += f"{item} x{count} = Bs{subtotal}\n"
        text += "-" * 40 + f"\nTOTAL: Bs{total}"
        self.order_display.setPlainText(text)

    # ----------------------------------------------------------------
    #  Pago  (req. 1, 2, 4)
    # ----------------------------------------------------------------
    def mark_as_paid(self):
        if not self.order_manager.current_table:
            QMessageBox.warning(self, "Error", "Selecciona un pedido primero")
            return
        if not self.order_manager.table_orders.get(self.order_manager.current_table):
            QMessageBox.warning(self, "Error", "El pedido esta vacio")
            return

        # --- req. 2: si es 'Para llevar', pedir detalles de moto primero ---
        if self.order_manager.order_type == "Para llevar":
            delivery_dlg = DeliveryDialog(self)
            if delivery_dlg.exec() != QDialog.DialogCode.Accepted:
                return
            self.order_manager.set_delivery_details(
                self.order_manager.current_table,
                delivery_dlg.get_moto_cost(),
                delivery_dlg.get_moto_method(),
            )

        # --- req. 1 + 4: dialogo de pago con mixto y cambio ---
        dialog = PaymentDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.order_manager.set_payment_status(
                self.order_manager.current_table,
                paid=True,
                method=dialog.get_payment_method(),
                amount_paid=dialog.get_amount_paid(),
                change=dialog.get_change(),
                cash_amount=dialog.get_cash_amount(),
                qr_amount=dialog.get_qr_amount(),
                change_method=dialog.get_change_method(),
            )

            _, total = self.order_manager.get_order_summary(self.order_manager.current_table)
            method = dialog.get_payment_method()

            msg = f"Pago registrado exitosamente\n\n"
            msg += f"Mesa: {self.order_manager.current_table}\n"
            msg += f"Total: Bs. {total:.2f}\n"
            msg += f"Metodo: {method}\n"

            if method == "Efectivo":
                msg += f"Recibido: Bs. {dialog.get_amount_paid():.2f}\n"
                if dialog.get_change() > 0:
                    msg += f"Cambio: Bs. {dialog.get_change():.2f} en {dialog.get_change_method()}"
            elif method == "Mixto":
                msg += f"Efectivo: Bs. {dialog.get_cash_amount():.2f}\n"
                msg += f"QR: Bs. {dialog.get_qr_amount():.2f}\n"
                if dialog.get_change() > 0:
                    msg += f"Cambio: Bs. {dialog.get_change():.2f} en {dialog.get_change_method()}"

            QMessageBox.information(self, "Pago Confirmado", msg)
            self.update_order_display()

            items = self.table_list.findItems(
                self.order_manager.current_table, Qt.MatchFlag.MatchExactly
            )
            if items:
                theme = self.theme_manager.get_current_theme()
                items[0].setBackground(QColor(theme["success"]))
                items[0].setForeground(QColor("white"))

    # ----------------------------------------------------------------
    #  Imprimir
    # ----------------------------------------------------------------
    def print_order(self):
        if not self.order_manager.current_table or not self.order_manager.table_orders.get(
            self.order_manager.current_table
        ):
            QMessageBox.warning(self, "Error", "No hay nada para imprimir")
            return
        try:
            from PyQt6.QtPrintSupport import QPrinter, QPrintDialog
            from PyQt6.QtGui import QPainter

            printer = QPrinter(QPrinter.PrinterMode.HighResolution)
            dlg = QPrintDialog(printer, self)
            if dlg.exec() == QDialog.DialogCode.Accepted:
                order_summary, total = self.order_manager.get_order_summary(
                    self.order_manager.current_table
                )
                order_details = []
                for item, count in order_summary.items():
                    price_per_unit = next(
                        p["price"]
                        for p in self.order_manager.table_orders[self.order_manager.current_table]
                        if f"{p['dish']} ({p['variant']})" == item
                    )
                    order_details.append(f"{count}x {item} - {price_per_unit * count} bs")

                delivery = self.order_manager.get_delivery_details(
                    self.order_manager.current_table
                ) or {}
                delivery_line = ""
                if delivery:
                    delivery_line = (
                        f"Moto: Bs{delivery.get('moto_cost', 0):.2f} "
                        f"({delivery.get('moto_payment_method', '')})\n"
                    )

                comanda = (
                    f"           PROVA - Comida Mexicana\n"
                    f"           -------------------------\n\n"
                    f"Pedido: {self.order_manager.current_table}\n"
                    f"Tipo: {self.order_manager.order_type}\n"
                    f"{delivery_line}"
                    f"{'-' * 40}\n"
                    f"{chr(10).join(order_details)}\n"
                    f"{'-' * 40}\n"
                    f"TOTAL: {total} bs\n\n"
                    f"Gracias por su preferencia!"
                )

                painter = QPainter()
                painter.begin(printer)
                painter.setFont(QFont("Arial", 12))
                painter.drawText(
                    painter.viewport(), Qt.TextFlag.TextWordWrap, comanda
                )
                painter.end()
                QMessageBox.information(self, "Exito", "La comanda se ha enviado a imprimir")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error al imprimir: {str(e)}")

    # ----------------------------------------------------------------
    #  Busqueda rapida
    # ----------------------------------------------------------------
    def _build_quick_index(self):
        self.quick_index.clear()
        menu = self.menu_data.get_menu_prices()
        for category, dishes in menu.items():
            for dish, variants in dishes.items():
                for variant, price in variants.items():
                    label = f"{dish} ({variant}) - Bs{price}"
                    self.quick_index[label] = (category, dish, variant, float(price))

    def setup_quick_search(self, parent_layout):
        row = QHBoxLayout()
        lbl = QLabel("Busqueda rapida:")
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Ej: taco, birria, horchata...")

        self.completer = QCompleter(list(self.quick_index.keys()))
        self.completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.completer.setFilterMode(Qt.MatchFlag.MatchContains)
        self.search_input.setCompleter(self.completer)

        self.search_add_btn = self.create_fancy_button("Agregar", "success", self.on_quick_add)
        self.search_input.returnPressed.connect(self.on_quick_add)
        self.completer.activated[str].connect(self.on_quick_choose)

        row.addWidget(lbl)
        row.addWidget(self.search_input, 1)
        row.addWidget(self.search_add_btn)
        parent_layout.addLayout(row)

        QShortcut(QKeySequence("Ctrl+K"), self, activated=lambda: self.search_input.setFocus())

    def on_quick_choose(self, text: str):
        if text and text in self.quick_index:
            self._add_from_quick_key(text)

    def on_quick_add(self):
        if not self.order_manager.current_table:
            QMessageBox.warning(self, "Sin mesa", "Selecciona o crea un pedido primero.")
            return
        txt = (self.search_input.text() or "").strip()
        if not txt:
            return
        if txt in self.quick_index:
            self._add_from_quick_key(txt)
            return
        for k in self.quick_index.keys():
            if txt.lower() in k.lower():
                self._add_from_quick_key(k)
                return
        QMessageBox.information(self, "Sin resultados", f"No encontre '{txt}'.")

    def _add_from_quick_key(self, key: str):
        category, dish, variant, price = self.quick_index[key]
        self.order_manager.add_item_to_order(category, dish, variant, price)
        self.update_order_display()
        self.search_input.clear()

    # ----------------------------------------------------------------
    #  Exportar a Excel  (req. 3 - dos hojas)
    # ----------------------------------------------------------------
    def save_to_excel(self):
        try:
            self.order_manager.save_all_to_excel("pedidos.xlsx")
            QMessageBox.information(
                self, "Exito",
                "Datos exportados a pedidos.xlsx\n"
                "Hoja 1: En el local | Hoja 2: Para llevar"
            )
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error al exportar: {str(e)}")
