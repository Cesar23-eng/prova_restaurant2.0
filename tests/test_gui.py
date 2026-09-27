import threading

import pytest

pytest.importorskip("PyQt6")

from PyQt6.QtWidgets import QApplication, QDialog, QInputDialog, QLabel, QMessageBox

from models.menu import MenuData


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def messages(monkeypatch):
    shown = []
    for name in ("information", "warning", "critical"):
        monkeypatch.setattr(QMessageBox, name,
                            lambda *args, _n=name, **kw: shown.append((_n, args[2] if len(args) > 2 else "")))
    monkeypatch.setattr(QMessageBox, "question",
                        lambda *args, **kw: QMessageBox.StandardButton.Yes)
    return shown


@pytest.fixture
def window(qapp, manager, menu_file, data_dir, messages):
    from views.main_window import ProvaRestaurant

    config = {"nombre_local": "PRÖVA Test", "pin_meseros": "1234", "tema_visual": "noche",
              "numero_mesas": 13}
    win = ProvaRestaurant(manager, MenuData(menu_file), config)
    yield win
    win.menu_timer.stop()
    win.clock_timer.stop()
    win.close()


def fake_new_order(monkeypatch, name="Mesa 5", order_type="En el local"):
    class FakeAddOrderDialog:
        def __init__(self, *args, **kwargs):
            pass

        def exec(self):
            return QDialog.DialogCode.Accepted

        def get_order_name(self):
            return name

        def get_order_type(self):
            return order_type

    monkeypatch.setattr("views.main_window.AddOrderDialog", FakeAddOrderDialog)


def ticket_rows(window):
    """Texto del ticket: encabezados de plato y lineas 'cantidad x platillo variante'."""
    rows = []
    layout = window.lines_layout
    for i in range(layout.count()):
        widget = layout.itemAt(i).widget()
        if widget is None or widget.isHidden():
            continue
        if isinstance(widget, QLabel) and widget.objectName() == "plateHeader":
            rows.append(widget.text().split("·")[0].strip())
        elif hasattr(widget, "line"):
            line = widget.line
            rows.append(f"{line['qty']}x {line['dish']} {line['variant']}")
    return rows


# ---------------------------------------------------------------------------
#  Menu
# ---------------------------------------------------------------------------
def test_menu_shows_category_chips_and_product_cards(window):
    assert list(window.category_buttons) == ["Platillos", "Bebidas", "Extras"]
    assert window.category_buttons["Platillos"].isChecked()
    assert set(window.variant_buttons) == {
        ("Platillos", "Taco", "Carne"), ("Platillos", "Taco", "Pastor"),
        ("Platillos", "Taco con queso", "Carne"), ("Platillos", "Taco con queso", "Lengua"),
        ("Platillos", "Quesadilla", "Pollo"),
    }
    window.set_category("Bebidas")
    assert set(window.variant_buttons) == {("Bebidas", "Coca cola", "Botella")}


def test_search_filters_across_categories_ignoring_accents(window):
    window.search_input.setText("coca")
    assert set(window.variant_buttons) == {("Bebidas", "Coca cola", "Botella")}
    window.search_input.setText("TACO pástor")
    assert set(window.variant_buttons) == {("Platillos", "Taco", "Pastor")}
    window.search_input.setText("pizza")
    assert window.variant_buttons == {} and not window.no_results.isHidden()


def test_enter_in_search_adds_the_only_result(window, manager):
    manager.create_table("Mesa 1")
    window.select_order("Mesa 1")
    window.search_input.setText("coca")
    window._add_single_search_result()
    assert [l["dish"] for l in manager.get_order_lines("Mesa 1")] == ["Coca cola"]
    assert window.search_input.text() == ""


def test_tapping_a_product_without_order_opens_new_order(window, manager, monkeypatch):
    fake_new_order(monkeypatch, "Mesa 5")
    button = window.variant_buttons[("Platillos", "Taco", "Carne")]
    button.click()
    assert window.current_table == "Mesa 5"
    assert manager.get_order_lines("Mesa 5")[0]["dish"] == "Taco"
    assert "Taco (Carne)" in window.toast.last_message


def test_products_go_to_active_plate_with_quantity(window, manager):
    manager.create_table("Mesa 1")
    window.select_order("Mesa 1")
    assert window.active_plate == 1
    window.qty_spin.setValue(3)
    window.add_product("Platillos", "Taco", "Pastor")
    assert window.qty_spin.value() == 1
    window.plate_buttons[2].click()
    assert window.active_plate == 2
    window.add_product("Platillos", "Taco", "Carne")
    # Solo los tacos llevan plato: la quesadilla y la bebida van a "otros"
    window.add_product("Platillos", "Quesadilla", "Pollo")
    window.add_product("Bebidas", "Coca cola", "Botella")
    assert ticket_rows(window) == [
        "\U0001F37D  PLATO 1", "3x Taco Pastor",
        "\U0001F37D  PLATO 2", "1x Taco Carne",
        "OTROS", "1x Quesadilla Pollo", "1x Coca cola Botella",
    ]
    assert window.total_label.text() == "Bs 105.00"
    assert "Bs 105.00" in window.pay_btn.text()
    assert "(6)" in window.kitchen_btn.text()
    plate_buttons = {w.line["dish"]: w.plate_btn is not None for w in window.ticket_lines}
    assert plate_buttons == {"Taco": True, "Quesadilla": False, "Coca cola": False}


def test_plate_bar_defaults_to_last_used_plate_when_switching_tables(window, manager):
    manager.create_table("Mesa 1")
    manager.create_table("Mesa 2")
    manager.add_item("Mesa 1", "Platillos", "Taco", "Pastor", 15, plate=3)
    window.select_order("Mesa 1")
    assert window.active_plate == 3
    assert list(window.plate_buttons) == [3, 4, 0]
    window.select_order("Mesa 2")
    assert window.active_plate == 1


def test_ticket_line_quantity_note_move_and_remove(window, manager, monkeypatch):
    manager.create_table("Mesa 1")
    manager.add_item("Mesa 1", "Platillos", "Taco", "Pastor", 15, qty=2, plate=1)
    window.select_order("Mesa 1")
    window.ticket_lines[0].plus_btn.click()
    assert manager.get_order_lines("Mesa 1")[0]["qty"] == 3
    window.ticket_lines[0].minus_btn.click()
    assert manager.get_order_lines("Mesa 1")[0]["qty"] == 2

    monkeypatch.setattr(QInputDialog, "getText", lambda *a, **k: ("sin cebolla", True))
    window.edit_line_note(0)
    assert manager.get_order_lines("Mesa 1")[0]["note"] == "sin cebolla"

    window.move_line(0, 2)
    assert manager.get_order_lines("Mesa 1")[0]["plate"] == 2
    window.remove_whole_line(0)
    assert manager.get_items("Mesa 1") == []
    assert not window.lines_empty.isHidden()


def test_order_type_buttons_follow_selected_order(window, manager):
    manager.create_table("Mesa 1")
    manager.create_table("Juan", order_type="Para llevar")
    window.select_order("Juan")
    assert window.type_buttons["Para llevar"].isChecked()
    window.select_order("Mesa 1")
    assert window.type_buttons["En el local"].isChecked()
    window.type_buttons["Para llevar"].click()
    assert manager.get_order_type("Mesa 1") == "Para llevar"


# ---------------------------------------------------------------------------
#  Pedidos
# ---------------------------------------------------------------------------
def test_order_cards_show_time_kitchen_and_waiter_badges(window, manager):
    manager.create_table("Mesa 1", source="mesero")
    manager.add_item("Mesa 1", "Platillos", "Taco", "Pastor", 15, qty=2)
    card = window.order_cards["Mesa 1"]
    badges = {label.text(): label.property("kind") for label in card.findChildren(QLabel)
              if label.objectName() == "badge"}
    assert "\U0001F514 2 sin comanda" in badges
    assert "\U0001F4F1 Mesero" in badges
    assert window.pending_label.text() == "1 por cobrar"


def test_selecting_a_card_opens_its_ticket(window, manager):
    manager.create_table("Mesa 1")
    manager.create_table("Mesa 2")
    window.order_cards["Mesa 2"].selected_name.emit("Mesa 2")
    assert window.current_table == "Mesa 2"
    assert window.ticket_name.text() == "Mesa 2"
    assert window.order_cards["Mesa 2"].property("selected") is True


def test_waiter_add_from_other_thread_refreshes_ui(window, manager, qapp):
    manager.create_table("Mesa 1")
    window.select_order("Mesa 1")
    worker = threading.Thread(target=lambda: manager.add_item(
        "Mesa 1", "Bebidas", "Coca cola", "Botella", 10, source="mesero"))
    worker.start()
    worker.join()
    qapp.processEvents()
    assert "1x Coca cola Botella" in ticket_rows(window)
    assert "Mesero" in window.toast.last_message


def pay(manager, table="Mesa 1", dish=("Platillos", "Taco", "Carne", 15), qty=1, **payment):
    manager.create_table(table)
    manager.add_item(table, *dish, qty=qty)
    total = dish[3] * qty
    return manager.register_payment(table, payment.pop("method", "QR"), **(payment or {"qr_amount": total}))


def test_paid_order_leaves_open_list_and_shows_read_only(window, manager):
    manager.create_table("Mesa 1")
    window.select_order("Mesa 1")
    window.add_product("Platillos", "Taco", "Pastor")
    window.add_product("Platillos", "Taco", "Pastor")
    manager.register_payment("Mesa 1", "Efectivo", cash_amount=50, change_method="Efectivo")

    # Sale de «Por cobrar» y el ticket queda en solo lectura, sin controles
    assert "Mesa 1" not in window.order_cards and window.current_table is None
    assert window.ticket_body.isHidden() and not window.ticket_paid.isHidden()
    assert window.paid_name.text() == "Mesa 1" and "PAGADO" in window.paid_status.text()
    assert window.paid_total.text() == "Bs 30.00"
    lines = [w for w in window.ticket_paid.findChildren(QLabel) if w.objectName() == "lineName"]
    assert [w.text() for w in lines] == ["Taco"]
    details = [w.text() for w in window.paid_details.findChildren(QLabel)]
    assert "Efectivo recibido" in details and "Cambio (Efectivo)" in details and "Bs 20.00" in details
    assert not window.paid_menu_hint.isHidden()

    # Tocar el menu no modifica el pedido pagado
    assert window.add_product("Platillos", "Taco", "Carne") is False
    assert "pagado" in window.toast.last_message
    assert len(manager.get_items("Mesa 1")) == 2


def test_paid_tab_lists_sales_and_filters(window, manager):
    pay(manager, "Mesa 1")
    pay(manager, "Juan", ("Bebidas", "Coca cola", "Botella", 10), qty=2, method="Efectivo", cash_amount=20)
    manager.create_table("Mesa 3")
    assert window.tab_buttons["open"].text() == "Por cobrar (1)"
    assert window.tab_buttons["paid"].text() == "Pagados (2)"

    window.tab_buttons["paid"].click()
    assert window.open_view.isHidden() and not window.paid_view.isHidden()
    assert list(window.paid_cards) == ["#0002", "#0001"]  # el ultimo cobro primero
    assert "2 pagados en la jornada" in window.paid_summary.text() and "Bs 35.00" in window.paid_summary.text()
    window.paid_search.setText("juan")
    assert list(window.paid_cards) == ["#0002"]
    window.paid_search.setText("zzz")
    assert window.paid_cards == {} and not window.paid_empty.isHidden()
    window.paid_search.clear()

    window.paid_cards["#0001"].clicked.emit()
    assert window.paid_number.text() == "#0001" and window.paid_name.text() == "Mesa 1"
    assert window.paid_cards["#0001"].property("selected") is True
    # Elegir un pedido por cobrar vuelve a la otra pestana y deja de mostrar el pagado
    window.select_order("Mesa 3")
    assert not window.open_view.isHidden() and window.ticket_paid.isHidden()


def test_paid_tab_survives_restart_and_cleared_list(window, manager, data_dir):
    from models.order import OrderManager
    from views.main_window import ProvaRestaurant

    pay(manager, "Mesa 1")
    manager.remove_paid_orders()
    restarted = ProvaRestaurant(OrderManager(root=data_dir, cutoff_hour=4), window.menu_data, window.config)
    try:
        restarted.show_orders_tab("paid")
        assert list(restarted.paid_cards) == ["#0001"]
    finally:
        restarted.menu_timer.stop()
        restarted.clock_timer.stop()
        restarted.close()


def test_paid_table_name_is_free_for_a_new_order(window, manager, monkeypatch):
    pay(manager, "Mesa 1")
    captured = {}

    class FakeAddOrderDialog:
        def __init__(self, *args, occupied=None, **kwargs):
            captured["occupied"] = occupied

        def exec(self):
            return QDialog.DialogCode.Accepted

        def get_order_name(self):
            return "Mesa 1"

        def get_order_type(self):
            return "En el local"

    monkeypatch.setattr("views.main_window.AddOrderDialog", FakeAddOrderDialog)
    assert window.add_pedido()
    assert captured["occupied"] == []
    assert window.current_table == "Mesa 1" and not manager.is_paid("Mesa 1")
    assert manager.get_order_number("Mesa 1") == "#0002"


def test_reprint_bill_of_paid_order(window, manager, monkeypatch):
    from utils import tickets

    printed = []
    monkeypatch.setattr(window, "send_ticket", lambda ticket, title: printed.append(tickets.to_text(ticket)) or True)
    pay(manager, "Mesa 1", qty=2, method="Efectivo", cash_amount=50, change_method="Efectivo")
    window.view_paid_order("#0001")
    window.reprint_bill_btn.click()
    assert "2 x Taco (Carne)" in printed[0] and "Cambio" in printed[0]
    window.print_customer_bill()  # Ctrl+P con el pagado a la vista
    assert len(printed) == 2
    assert manager.get_items("Mesa 1")  # imprimir no cambia nada del pedido


def test_add_order_dialog_quick_tables(qapp, messages):
    from views.dialogs import AddOrderDialog

    dialog = AddOrderDialog(occupied=["Mesa 1"], table_count=13)
    assert list(dialog.table_buttons)[-1] == "Mesa 13"
    assert not dialog.table_buttons["Mesa 1"].isEnabled()
    assert not dialog.ok_button.isEnabled()
    dialog.type_buttons["Para llevar"].setChecked(True)
    dialog.table_buttons["Mesa 2"].click()
    assert dialog.result() == QDialog.DialogCode.Accepted
    assert (dialog.get_order_name(), dialog.get_order_type()) == ("Mesa 2", "En el local")


def test_theme_toggle_and_summary_dialog(window, manager, data_dir):
    import json
    import os

    from views.dialogs import DaySummaryDialog

    manager.create_table("Mesa 1")
    manager.add_item("Mesa 1", "Platillos", "Taco", "Carne", 15, qty=2)
    manager.register_payment("Mesa 1", "Efectivo", cash_amount=50, change_method="Efectivo")
    window.toggle_theme()
    assert window.theme_manager.current_theme == "dia"
    with open(os.path.join(data_dir, "config.json"), encoding="utf-8") as f:
        assert json.load(f)["tema_visual"] == "dia"
    dialog = DaySummaryDialog(manager, "PRÖVA Test", window, colors=window.theme_manager.get_current_theme())
    assert dialog.kpi_labels["expected_cash"].text() == "Bs 30.00"
    assert "Efectivo neto de ventas" in dialog.browser.toPlainText()
    dialog.close()


def test_export_snapshot(window, manager):
    manager.create_table("Mesa 1")
    manager.add_item("Mesa 1", "Platillos", "Taco", "Carne", 15)
    window.save_to_excel()
    assert window.toast.last_kind == "success"
    assert "respaldo_" in window.toast.last_message


# ---------------------------------------------------------------------------
#  Cobro
# ---------------------------------------------------------------------------
def test_payment_dialog_cash_with_change(qapp, messages):
    from views.dialogs import PaymentDialog

    dialog = PaymentDialog(total=35)
    dialog.radio_cash.setChecked(True)
    dialog.cash_input.setText("50")
    assert dialog.change_label.text() == "CAMBIO  Bs 15.00"
    assert dialog.change_label.property("state") == "change"
    dialog.radio_change_qr.setChecked(True)
    dialog.confirm_payment()
    assert dialog.result() == dialog.DialogCode.Accepted
    assert (dialog.get_payment_method(), dialog.get_cash_amount(), dialog.get_change(),
            dialog.get_change_method()) == ("Efectivo", 50.0, 15.0, "QR")


def test_payment_dialog_rejects_insufficient_mixed(qapp, messages):
    from views.dialogs import PaymentDialog

    dialog = PaymentDialog(total=100)
    dialog.radio_mixed.setChecked(True)
    dialog.mixed_cash_input.setText("40")
    dialog.mixed_qr_input.setText("50")
    assert dialog.mixed_status_label.text().startswith("FALTA  Bs 10.00")
    dialog.confirm_payment()
    assert dialog.result() != dialog.DialogCode.Accepted
    assert messages[-1][0] == "warning"
    dialog._fill_rest_with_qr()
    assert dialog.mixed_qr_input.text() == "60"


def test_payment_quick_amounts():
    from views.dialogs import PaymentDialog

    assert PaymentDialog.quick_amounts(167) == [167, 170, 200]
    assert PaymentDialog.quick_amounts(35) == [35, 40, 50, 100]
    assert PaymentDialog.quick_amounts(50) == [50, 100, 200]


# ---------------------------------------------------------------------------
#  Platos, comandas y cuenta
# ---------------------------------------------------------------------------
def test_kitchen_button_prints_only_new_items_grouped_by_plate(window, manager, monkeypatch):
    from utils import tickets

    sent = []
    monkeypatch.setattr(window.ticket_printer, "print_ticket",
                        lambda ticket, job: sent.append(tickets.to_text(ticket)) or "EPSON TM-T20III Receipt")
    manager.create_table("Mesa 1")
    manager.add_item("Mesa 1", "Platillos", "Taco", "Pastor", 15, qty=3, plate=1)
    manager.add_item("Mesa 1", "Platillos", "Taco", "Carne", 15, qty=2, plate=2, note="sin cebolla")
    manager.add_item("Mesa 1", "Bebidas", "Coca cola", "Botella", 10)
    window.select_order("Mesa 1")
    window.print_kitchen_ticket()
    first = sent[-1]
    assert (first.index("PLATO 1") < first.index("Pastor") < first.index("PLATO 2")
            < first.index("Carne") < first.index("SIN PLATO"))
    assert "sin cebolla" in first
    assert "Comanda enviada a EPSON TM-T20III Receipt" in window.toast.last_message

    manager.add_item("Mesa 1", "Platillos", "Taco", "Carne", 15, plate=2)
    window.print_kitchen_ticket()
    assert "PLATO 2 (agregar)" in sent[-1] and "PLATO 1" not in sent[-1]


def test_print_error_keeps_items_pending(window, manager, monkeypatch, messages):
    from utils.printer import PrinterError

    def fail(ticket, job):
        raise PrinterError("Abrir la impresora fallo")

    monkeypatch.setattr(window.ticket_printer, "print_ticket", fail)
    manager.create_table("Mesa 1")
    manager.add_item("Mesa 1", "Platillos", "Taco", "Pastor", 15, qty=2)
    window.select_order("Mesa 1")
    window.print_kitchen_ticket()
    assert manager.kitchen_pending_count("Mesa 1") == 2
    assert messages[-1][0] == "warning" and "Impresora de tickets" in messages[-1][1]


def test_printer_dialog_detects_epson_and_saves(qapp, data_dir, monkeypatch):
    import json
    import os

    from utils import printer
    from views.dialogs import PrinterDialog

    sent = []
    monkeypatch.setattr(printer, "send_raw", lambda name, data, job: sent.append((name, data)))
    config = {"impresora_tickets": "", "modo_impresion": "auto", "ancho_papel_mm": 80}
    dialog = PrinterDialog(config, data_dir, "PRÖVA", printers=["Microsoft Print to PDF", "EPSON TM-T20III Receipt"],
                           default="Microsoft Print to PDF")
    assert "EPSON TM-T20III Receipt" in dialog.result_label.text()
    assert "ESC/POS" in dialog.result_label.text() and "48 columnas" in dialog.result_label.text()
    dialog.print_test()
    assert sent and sent[0][0] == "EPSON TM-T20III Receipt"
    dialog.paper_combo.setCurrentIndex(dialog.paper_combo.findData(58))
    dialog.printer_combo.setCurrentIndex(dialog.printer_combo.findData("EPSON TM-T20III Receipt"))
    dialog.save()
    assert config["ancho_papel_mm"] == 58 and config["impresora_tickets"] == "EPSON TM-T20III Receipt"
    with open(os.path.join(data_dir, "config.json"), encoding="utf-8") as f:
        assert json.load(f)["impresora_tickets"] == "EPSON TM-T20III Receipt"


def test_plate_dialog_splits_line_between_plates(window, manager, qapp):
    from views.dialogs import PlateDialog

    manager.create_table("Mesa 1")
    manager.add_item("Mesa 1", "Platillos", "Taco", "Pastor", 15, qty=5, plate=1)
    manager.add_item("Mesa 1", "Bebidas", "Coca cola", "Botella", 10)
    dialog = PlateDialog(manager, "Mesa 1", window)
    assert dialog.selected_line()["variant"] == "Pastor"
    dialog.count_spin.setValue(2)
    dialog.target_combo.setCurrentIndex(dialog.target_combo.findData(2))
    dialog.move_selected()
    assert {l["plate"]: l["qty"] for l in manager.get_order_lines("Mesa 1") if l["dish"] == "Taco"} == {1: 3, 2: 2}
    assert "movido(s) al Plato 2" in dialog.status_label.text()

    for i in range(dialog.list_widget.count()):
        item = dialog.list_widget.item(i)
        if "Coca cola" in item.text():
            dialog.list_widget.setCurrentItem(item)
    assert not dialog.move_btn.isEnabled()
    dialog.close()


def test_customer_bill_merges_plates(window, manager, monkeypatch):
    from utils import tickets

    printed = []
    monkeypatch.setattr(window, "send_ticket", lambda ticket, title: printed.append(tickets.to_text(ticket)) or True)
    manager.create_table("Mesa 1")
    manager.add_item("Mesa 1", "Platillos", "Taco", "Pastor", 15, qty=3, plate=1)
    manager.add_item("Mesa 1", "Platillos", "Taco", "Pastor", 15, qty=2, plate=2)
    window.select_order("Mesa 1")
    window.print_customer_bill()
    assert "5 x Taco (Pastor)" in printed[0] and "Plato" not in printed[0]


def test_printing_kitchen_ticket_marks_items_as_sent(window, manager, monkeypatch):
    monkeypatch.setattr(window, "send_ticket", lambda ticket, title: True)
    manager.create_table("Mesa 1")
    manager.add_item("Mesa 1", "Platillos", "Taco", "Pastor", 15, qty=2)
    window.select_order("Mesa 1")
    assert window.kitchen_btn.property("attention") is True
    window.kitchen_btn.click()
    assert manager.kitchen_pending_count("Mesa 1") == 0
    assert window.kitchen_btn.property("attention") is False


def test_split_one_taco_con_queso_to_another_plate(window, manager):
    from PyQt6.QtWidgets import QMenu

    manager.create_table("Mesa 1")
    manager.add_item("Mesa 1", "Platillos", "Taco con queso", "Carne", 17, qty=3, plate=1)
    window.select_order("Mesa 1")
    line = window._line(0)
    menu = QMenu(window)
    window.fill_plate_menu(menu, 0, line)
    texts = [action.text() for action in menu.actions()]
    assert "Separar 1 de los 3 a…" in texts and "Mover los 3 a…" in texts
    split_to_plate_2 = next(a for a in menu.actions()
                            if a.text().startswith("\u2702") and "Plato 2" in a.text())
    split_to_plate_2.trigger()
    assert ticket_rows(window) == [
        "\U0001F37D  PLATO 1", "2x Taco con queso Carne",
        "\U0001F37D  PLATO 2", "1x Taco con queso Carne",
    ]
    assert "separado" in window.toast.last_message


# ---------------------------------------------------------------------------
#  Caja: apertura, gastos y arqueo
# ---------------------------------------------------------------------------
def fake_dialog(monkeypatch, name, values):
    class FakeDialog:
        def __init__(self, *args, **kwargs):
            pass

        def exec(self):
            return QDialog.DialogCode.Accepted

        def values(self):
            return values

    monkeypatch.setattr(f"views.main_window.{name}", FakeDialog)


def test_cash_opening_expense_and_count(window, manager, monkeypatch):
    from views.dialogs import DaySummaryDialog

    assert "Abrir caja" in window.cash_btn.text() and window.cash_btn.property("status") == "warn"
    fake_dialog(monkeypatch, "CashOpeningDialog", {"cash": 200, "qr": 0, "reserve": 50, "cashier": "Ana"})
    window.on_cash_button()
    assert "Caja abierta" in window.cash_btn.text() and window.cash_btn.property("status") == "ok"

    fake_dialog(monkeypatch, "ExpenseDialog", {"amount": 20, "method": "Efectivo", "reason": "Hielo"})
    assert window.register_expense()
    assert "Hielo" in window.toast.last_message

    manager.create_table("Mesa 1")
    manager.add_item("Mesa 1", "Platillos", "Taco", "Carne", 15, qty=2)
    manager.register_payment("Mesa 1", "Efectivo", cash_amount=50, change_method="Efectivo")
    dialog = DaySummaryDialog(manager, "PRÖVA Test", window)
    # 200 inicial + 50 imprevistos + 30 ventas - 20 hielo
    assert dialog.kpi_labels["expected_cash"].text() == "Bs 260.00"
    dialog.count_input.setText("255")
    dialog.save_count()
    assert dialog.difference_label.text() == "FALTAN  Bs 5.00"
    assert dialog.difference_label.property("state") == "missing"
    assert "Hielo" in dialog.browser.toPlainText()
    dialog.close()


def test_cash_opening_is_only_a_reminder(window, manager):
    window._remind_cash_opening()
    assert window.toast.last_kind == "warning" and "Caja sin abrir" in window.toast.last_message
    manager.cash.open(100)
    window.toast.last_message = ""
    window._remind_cash_opening()
    assert window.toast.last_message == ""


def test_day_summary_prints_cash_block(window, manager, monkeypatch):
    from utils import tickets

    printed = []
    monkeypatch.setattr(window, "send_ticket", lambda ticket, title: printed.append(tickets.to_text(ticket)) or True)
    manager.cash.open(150, reserve=50)
    manager.cash.add_expense(30, "Efectivo", "Gas")
    summary = manager.day_summary()
    window.print_day_summary(summary, "01/01/2026", manager.cash_summary(None, summary))
    assert "ARQUEO DE CAJA" in printed[0] and "Gas" in printed[0]


# ---------------------------------------------------------------------------
#  Inventario: agotados
# ---------------------------------------------------------------------------
def test_sold_out_soda_cannot_be_added_from_caja(window, manager):
    manager.create_table("Mesa 1")
    window.select_order("Mesa 1")
    window.set_category("Bebidas")
    manager.inventory.set_available("Bebidas", "Coca cola", "Botella", False)
    button = window.variant_buttons[("Bebidas", "Coca cola", "Botella")]
    assert "AGOTADO" in button.text() and button.property("soldOut") is True
    assert "1 agotado" in window.inventory_btn.text()

    assert window.add_product("Bebidas", "Coca cola", "Botella") is False
    assert window.toast.last_kind == "error" and "Se acabó" in window.toast.last_message
    assert manager.get_items("Mesa 1") == []

    manager.inventory.set_available("Bebidas", "Coca cola", "Botella", True)
    assert window.variant_buttons[("Bebidas", "Coca cola", "Botella")].property("soldOut") is False
    assert "Inventario" in window.inventory_btn.text()
    assert window.add_product("Bebidas", "Coca cola", "Botella") is True


def test_inventory_dialog_toggles(window, manager):
    from views.dialogs import InventoryDialog

    dialog = InventoryDialog(manager, window.menu_data.get_menu_prices(), ["Bebidas"], window)
    key = ("Bebidas", "Coca cola", "Botella")
    assert key in dialog.toggles and ("Platillos", "Taco", "Carne") not in dialog.toggles
    dialog.toggles[key].click()
    assert not manager.inventory.is_available(*key)
    assert dialog.toggles[key].text() == "✖ AGOTADO" and dialog.status_label.text().startswith("1 producto")
    dialog.filter_input.setText("zzz")
    assert all(item.isHidden() for _key, item in dialog.rows)
    dialog.mark_all_available()
    assert manager.inventory.is_available(*key) and dialog.status_label.text() == "Todo disponible"
    dialog.close()


def test_new_business_day_asks_to_open_cash_again(window, manager, frozen_now):
    import datetime

    manager.cash.open(200)
    assert "Caja abierta" in window.cash_btn.text()
    frozen_now(datetime.datetime(2026, 9, 15, 4, 30))  # paso la hora de corte: otra jornada
    window._tick()
    assert "Abrir caja" in window.cash_btn.text()
