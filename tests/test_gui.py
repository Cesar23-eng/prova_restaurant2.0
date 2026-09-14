import threading

import pytest

pytest.importorskip("PyQt6")

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication, QMessageBox

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

    config = {"nombre_local": "PROVA Test", "pin_meseros": "1234", "tema": "light"}
    win = ProvaRestaurant(manager, MenuData(menu_file), config)
    yield win
    win.menu_timer.stop()
    win.close()


def select(window, name):
    for i in range(window.table_list.count()):
        item = window.table_list.item(i)
        if item.data(Qt.ItemDataRole.UserRole) == name:
            window.table_list.setCurrentItem(item)
            return item
    raise AssertionError(f"{name} no esta en la lista")


def test_menu_combos_are_filled(window):
    assert window.category_combo.count() == 3
    assert window.dish_combo.currentText() == "Taco"
    assert window.variant_combo.currentData() == "Carne"
    assert "Taco (Carne) - Bs 15.00" in window.quick_index


def test_add_items_with_quantity_and_note(window, manager):
    manager.create_table("Mesa 1")
    select(window, "Mesa 1")
    window.qty_spin.setValue(3)
    window.note_input.setText("sin cebolla")
    window.add_order()
    lines = manager.get_order_lines("Mesa 1")
    assert [(l["dish"], l["qty"], l["note"]) for l in lines] == [("Taco", 3, "sin cebolla")]
    assert window.qty_spin.value() == 1 and window.note_input.text() == ""
    assert "sin cebolla" in window.order_display.toPlainText()
    assert "45.00" in window.table_list.currentItem().text()


def test_order_type_combo_follows_selected_order(window, manager):
    manager.create_table("Mesa 1")
    manager.create_table("Juan", order_type="Para llevar")
    select(window, "Juan")
    assert window.order_type_combo.currentText() == "Para llevar"
    select(window, "Mesa 1")
    assert window.order_type_combo.currentText() == "En el local"


def test_quick_search_without_table_does_not_crash(window, messages, manager):
    window.search_input.setText("Taco (Carne) - Bs 15.00")
    window.on_quick_add()
    assert messages and messages[-1][0] == "warning"
    assert manager.get_all_tables() == []


def test_waiter_add_from_other_thread_refreshes_ui(window, manager, qapp):
    manager.create_table("Mesa 1")
    select(window, "Mesa 1")
    worker = threading.Thread(target=lambda: manager.add_item(
        "Mesa 1", "Bebidas", "Coca cola", "Botella", 10, source="mesero"))
    worker.start()
    worker.join()
    qapp.processEvents()
    assert "Coca cola" in window.order_display.toPlainText()
    assert "agrego 1 platillo" in window.statusBar().currentMessage()


def test_paid_order_is_locked_in_ui(window, manager, messages):
    manager.create_table("Mesa 1")
    select(window, "Mesa 1")
    window.add_order()
    manager.register_payment("Mesa 1", "QR", qr_amount=15)
    window.add_order()
    assert messages[-1][0] == "warning"
    assert len(manager.get_items("Mesa 1")) == 1
    assert "PAGADO" in window.table_list.currentItem().text()
    assert not window.order_type_combo.isEnabled()


def test_theme_toggle_and_summary_dialog(window, manager):
    from views.dialogs import DaySummaryDialog

    manager.create_table("Mesa 1")
    manager.add_item("Mesa 1", "Platillos", "Taco", "Carne", 15, qty=2)
    manager.register_payment("Mesa 1", "Efectivo", cash_amount=50, change_method="Efectivo")
    window.toggle_theme()
    assert window.theme_manager.current_theme == "dark"
    dialog = DaySummaryDialog(manager, "PROVA Test", window)
    text = dialog.browser.toPlainText()
    assert "Efectivo neto en caja" in text and "Bs 30.00" in text
    dialog.close()


def test_export_snapshot(window, manager, messages):
    manager.create_table("Mesa 1")
    manager.add_item("Mesa 1", "Platillos", "Taco", "Carne", 15)
    window.save_to_excel()
    assert messages[-1][0] == "information"
    assert "respaldo_" in messages[-1][1]


def test_payment_dialog_cash_with_change(qapp, messages):
    from views.dialogs import PaymentDialog

    dialog = PaymentDialog(total=35)
    dialog.radio_cash.setChecked(True)
    dialog.cash_input.setText("50")
    assert dialog.change_label.text() == "CAMBIO: Bs. 15.00"
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
    assert dialog.mixed_status_label.text().startswith("FALTA: Bs. 10.00")
    dialog.confirm_payment()
    assert dialog.result() != dialog.DialogCode.Accepted
    assert messages[-1][0] == "warning"
