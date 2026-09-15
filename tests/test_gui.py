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
              "numero_mesas": 8}
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
        ("Platillos", "Taco", "Carne"), ("Platillos", "Taco", "Pastor"), ("Platillos", "Quesadilla", "Pollo"),
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
    window.add_product("Bebidas", "Coca cola", "Botella")  # las bebidas van sin plato
    assert ticket_rows(window) == [
        "\U0001F37D  PLATO 1", "3x Taco Pastor",
        "\U0001F37D  PLATO 2", "1x Taco Carne",
        "SIN PLATO", "1x Coca cola Botella",
    ]
    assert window.total_label.text() == "Bs 70.00"
    assert "Bs 70.00" in window.pay_btn.text()
    assert "(3)" not in window.kitchen_btn.text() and "(5)" in window.kitchen_btn.text()


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


def test_paid_order_is_locked_in_ui(window, manager):
    manager.create_table("Mesa 1")
    window.select_order("Mesa 1")
    window.add_product("Platillos", "Taco", "Carne")
    manager.register_payment("Mesa 1", "QR", qr_amount=15)
    assert window.add_product("Platillos", "Taco", "Carne") is False
    assert window.toast.last_kind == "error"
    assert len(manager.get_items("Mesa 1")) == 1
    assert window.pay_btn.isHidden() and not window.remove_paid_btn.isHidden()
    assert window.ticket_lines[0].plus_btn.isHidden()
    assert "COBRADO" in window.paid_banner.text()
    assert not window.type_buttons["En el local"].isEnabled()


def test_clear_paid_orders(window, manager):
    manager.create_table("Mesa 1")
    manager.add_item("Mesa 1", "Platillos", "Taco", "Carne", 15)
    manager.register_payment("Mesa 1", "QR", qr_amount=15)
    manager.create_table("Mesa 2")
    assert not window.clear_paid_btn.isHidden()
    window.clear_paid_btn.click()
    assert list(window.order_cards) == ["Mesa 2"]
    assert window.clear_paid_btn.isHidden()


def test_add_order_dialog_quick_tables(qapp, messages):
    from views.dialogs import AddOrderDialog

    dialog = AddOrderDialog(occupied=["Mesa 1"], table_count=8)
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
    assert dialog.kpi_labels["cash_net"].text() == "Bs 30.00"
    assert "Efectivo neto en caja" in dialog.browser.toPlainText()
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
def test_kitchen_ticket_groups_by_plate_and_marks_additions(window, manager):
    manager.create_table("Mesa 1")
    manager.add_item("Mesa 1", "Platillos", "Taco", "Pastor", 15, qty=3, plate=1)
    manager.add_item("Mesa 1", "Platillos", "Taco", "Carne", 15, qty=2, plate=2, note="sin cebolla")
    manager.add_item("Mesa 1", "Bebidas", "Coca cola", "Botella", 10)
    order = manager.get_order("Mesa 1")
    html_text = window.kitchen_ticket_html("Mesa 1", order, manager.get_order_lines("Mesa 1"), False)
    assert (html_text.index("PLATO 1") < html_text.index("Pastor") < html_text.index("PLATO 2")
            < html_text.index("Carne") < html_text.index("SIN PLATO / BEBIDAS"))
    assert "sin cebolla" in html_text

    manager.mark_sent_to_kitchen("Mesa 1")
    manager.add_item("Mesa 1", "Platillos", "Quesadilla", "Pollo", 35, plate=2)
    order = manager.get_order("Mesa 1")
    pending = manager.get_order_lines("Mesa 1", kitchen_pending_only=True)
    html_text = window.kitchen_ticket_html("Mesa 1", order, pending, False)
    assert "PLATO 2 (agregar)" in html_text and "PLATO 1" not in html_text


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
    printed = []
    monkeypatch.setattr(window, "print_html", lambda body: printed.append(body) or True)
    manager.create_table("Mesa 1")
    manager.add_item("Mesa 1", "Platillos", "Taco", "Pastor", 15, qty=3, plate=1)
    manager.add_item("Mesa 1", "Platillos", "Taco", "Pastor", 15, qty=2, plate=2)
    window.select_order("Mesa 1")
    window.print_customer_bill()
    assert "5x Taco (Pastor)" in printed[0] and "Plato" not in printed[0]


def test_printing_kitchen_ticket_marks_items_as_sent(window, manager, monkeypatch):
    monkeypatch.setattr(window, "print_html", lambda body: True)
    manager.create_table("Mesa 1")
    manager.add_item("Mesa 1", "Platillos", "Taco", "Pastor", 15, qty=2)
    window.select_order("Mesa 1")
    assert window.kitchen_btn.property("attention") is True
    window.kitchen_btn.click()
    assert manager.kitchen_pending_count("Mesa 1") == 0
    assert window.kitchen_btn.property("attention") is False
