import datetime
import json
import os
import threading

import pytest

from models.order import (
    ORDER_TYPE_LOCAL, ORDER_TYPE_TAKEAWAY, OrderChangedError, OrderManager,
)


def test_create_table_assigns_sequential_numbers_and_rejects_duplicates(manager):
    assert manager.create_table("Mesa 1") == (True, "Mesa 1")
    assert manager.create_table("  mesa   1 ") == (False, "mesa 1 2")
    assert manager.create_table("Mesa 2") == (True, "Mesa 2")
    assert manager.get_order_number("Mesa 1") == "#0001"
    assert manager.get_order_number("Mesa 2") == "#0002"


def test_order_type_is_per_order(manager):
    manager.create_table("Mesa 1")
    manager.create_table("Juan", order_type=ORDER_TYPE_TAKEAWAY)
    assert manager.get_order_type("Mesa 1") == ORDER_TYPE_LOCAL
    assert manager.get_order_type("Juan") == ORDER_TYPE_TAKEAWAY
    manager.set_order_type("Mesa 1", ORDER_TYPE_TAKEAWAY)
    assert manager.get_order_type("Juan") == ORDER_TYPE_TAKEAWAY
    assert manager.get_order_type("Mesa 1") == ORDER_TYPE_TAKEAWAY


def test_lines_group_by_dish_variant_and_note(manager):
    manager.create_table("Mesa 1")
    manager.add_item("Mesa 1", "Platillos", "Taco", "Carne", 15, qty=3)
    manager.add_item("Mesa 1", "Platillos", "Taco", "Carne", 15, note="sin cebolla")
    lines = manager.get_order_lines("Mesa 1")
    assert [(l["dish"], l["note"], l["qty"], l["subtotal"]) for l in lines] == [
        ("Taco", "", 3, 45.0),
        ("Taco", "sin cebolla", 1, 15.0),
    ]
    assert manager.get_total("Mesa 1") == 60.0


def test_add_items_is_atomic(manager):
    manager.create_table("Mesa 1")
    with pytest.raises(ValueError):
        manager.add_items("Mesa 1", [
            {"dish": "Taco", "variant": "Carne", "price": 15},
            {"dish": "Taco", "variant": "", "price": 15},
        ])
    assert manager.get_items("Mesa 1") == []


def test_remove_line_removes_units(manager):
    manager.create_table("Mesa 1")
    manager.add_item("Mesa 1", "Platillos", "Taco", "Carne", 15, qty=3)
    manager.add_item("Mesa 1", "Bebidas", "Coca cola", "Botella", 10)
    assert manager.remove_line("Mesa 1", 0, count=2) == 2
    lines = manager.get_order_lines("Mesa 1")
    assert [(l["dish"], l["qty"]) for l in lines] == [("Taco", 1), ("Coca cola", 1)]


def test_rename_keeps_position_number_and_items(manager):
    manager.create_table("Mesa 1")
    manager.create_table("Mesa 2")
    manager.add_item("Mesa 1", "Platillos", "Taco", "Carne", 15)
    manager.set_current_table("Mesa 1")
    assert manager.rename_table("Mesa 1", "Terraza")
    assert manager.get_all_tables() == ["Terraza", "Mesa 2"]
    assert manager.get_order_number("Terraza") == "#0001"
    assert manager.current_table == "Terraza"
    assert not manager.rename_table("Terraza", "mesa 2")


def test_payment_locks_order_and_records_sale(manager, data_dir):
    manager.create_table("Mesa 1")
    manager.add_item("Mesa 1", "Platillos", "Taco", "Carne", 15, qty=2)
    result = manager.register_payment("Mesa 1", "Efectivo", cash_amount=50,
                                      change_method="Efectivo", expected_total=30)
    assert result.excel_ok, result.message
    assert manager.get_payment_status("Mesa 1") == (True, "Efectivo")
    assert manager.get_payment_details("Mesa 1")["change"] == 20.0
    with pytest.raises(PermissionError):
        manager.add_item("Mesa 1", "Platillos", "Taco", "Carne", 15)
    with pytest.raises(PermissionError):
        manager.set_order_type("Mesa 1", ORDER_TYPE_TAKEAWAY)
    assert os.path.exists(manager.daily_excel_path())
    summary = manager.day_summary()
    assert summary["orders"] == 1 and summary["total"] == 30.0


def test_payment_rejected_if_order_changed_while_charging(manager):
    manager.create_table("Mesa 1")
    manager.add_item("Mesa 1", "Platillos", "Taco", "Carne", 15)
    manager.add_item("Mesa 1", "Bebidas", "Coca cola", "Botella", 10, source="mesero")
    with pytest.raises(OrderChangedError) as exc:
        manager.register_payment("Mesa 1", "QR", qr_amount=15, expected_total=15)
    assert exc.value.new_total == 25.0
    assert not manager.is_paid("Mesa 1")


def test_payment_rejects_insufficient_amount(manager):
    manager.create_table("Mesa 1")
    manager.add_item("Mesa 1", "Platillos", "Taco", "Carne", 15)
    with pytest.raises(ValueError):
        manager.register_payment("Mesa 1", "Efectivo", cash_amount=10)
    assert not manager.is_paid("Mesa 1")


def test_open_orders_survive_restart(manager, data_dir, frozen_now):
    manager.create_table("Mesa 1")
    manager.add_item("Mesa 1", "Platillos", "Taco", "Carne", 15, note="sin cebolla")
    manager.create_table("Juan", order_type=ORDER_TYPE_TAKEAWAY)

    restored = OrderManager(root=data_dir, cutoff_hour=4)
    assert restored.get_all_tables() == ["Mesa 1", "Juan"]
    assert restored.get_items("Mesa 1")[0]["note"] == "sin cebolla"
    assert restored.get_order_type("Juan") == ORDER_TYPE_TAKEAWAY
    assert restored.restored_count == 2
    restored.create_table("Mesa 3")
    assert restored.get_order_number("Mesa 3") == "#0003"


def test_numbering_resets_per_business_day(manager, data_dir, frozen_now):
    manager.create_table("Mesa 1")
    manager.add_item("Mesa 1", "Platillos", "Taco", "Carne", 15)
    manager.register_payment("Mesa 1", "QR", qr_amount=15)
    manager.create_table("Pendiente")

    # 01:30 de la madrugada sigue siendo la misma jornada
    frozen_now(datetime.datetime(2026, 9, 15, 1, 30))
    manager.create_table("Trasnoche")
    assert manager.get_order_number("Trasnoche") == "#0003"

    # Al dia siguiente la numeracion reinicia y los pagados de ayer salen de la lista
    frozen_now(datetime.datetime(2026, 9, 15, 12, 0))
    manager.create_table("Mesa nueva")
    assert "Mesa 1" not in manager.get_all_tables()
    assert "Pendiente" in manager.get_all_tables()
    assert manager.get_order_number("Mesa nueva") == "#0001"


def test_restart_same_day_continues_numbering_from_sales(manager, data_dir):
    manager.create_table("Mesa 1")
    manager.add_item("Mesa 1", "Platillos", "Taco", "Carne", 15)
    manager.register_payment("Mesa 1", "QR", qr_amount=15)
    manager.delete_table("Mesa 1")
    os.remove(os.path.join(data_dir, "estado_pedidos.json"))

    restarted = OrderManager(root=data_dir, cutoff_hour=4)
    restarted.create_table("Mesa 2")
    assert restarted.get_order_number("Mesa 2") == "#0002"


def test_corrupt_state_file_is_backed_up(data_dir, frozen_now):
    with open(os.path.join(data_dir, "estado_pedidos.json"), "w") as f:
        f.write("{no es json")
    manager = OrderManager(root=data_dir, cutoff_hour=4)
    assert manager.get_all_tables() == []
    assert any(n.startswith("estado_pedidos.json.corrupto") for n in os.listdir(data_dir))


def test_concurrent_adds_from_waiters_and_cashier(manager):
    manager.create_table("Mesa 1")
    manager.create_table("Mesa 2")

    def worker(table):
        for _ in range(50):
            manager.add_item(table, "Platillos", "Taco", "Carne", 15)

    threads = [threading.Thread(target=worker, args=(t,)) for t in ["Mesa 1", "Mesa 2"] * 3]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len(manager.get_items("Mesa 1")) == 150
    assert len(manager.get_items("Mesa 2")) == 150


def test_listeners_receive_events(manager):
    events = []
    manager.add_listener(lambda event, table, info: events.append((event, table, info.get("source"))))
    manager.create_table("Mesa 1")
    manager.add_item("Mesa 1", "Platillos", "Taco", "Carne", 15, source="mesero")
    assert events == [("created", "Mesa 1", "caja"), ("items_added", "Mesa 1", "mesero")]


def test_state_file_is_valid_json(manager, data_dir):
    manager.create_table("Mesa 1")
    with open(os.path.join(data_dir, "estado_pedidos.json"), encoding="utf-8") as f:
        data = json.load(f)
    assert data["orders"][0]["name"] == "Mesa 1"


def test_kitchen_ticket_only_includes_new_items(manager):
    manager.create_table("Mesa 1")
    manager.add_item("Mesa 1", "Platillos", "Taco", "Carne", 15, qty=2)
    assert manager.kitchen_pending_count("Mesa 1") == 2
    assert manager.mark_sent_to_kitchen("Mesa 1") == 2
    manager.add_item("Mesa 1", "Bebidas", "Coca cola", "Botella", 10, source="mesero")
    pending = manager.get_order_lines("Mesa 1", kitchen_pending_only=True)
    assert [(l["dish"], l["qty"]) for l in pending] == [("Coca cola", 1)]
    assert len(manager.get_order_lines("Mesa 1")) == 2


def test_items_are_grouped_by_plate(manager):
    from models.order import group_lines_by_plate

    manager.create_table("Mesa 1")
    manager.add_item("Mesa 1", "Platillos", "Taco", "Pastor", 15, qty=3, plate=1)
    manager.add_item("Mesa 1", "Platillos", "Taco", "Pastor", 15, qty=2, plate=2)
    manager.add_item("Mesa 1", "Platillos", "Taco", "Birria", 15, qty=1, plate=1)
    manager.add_item("Mesa 1", "Bebidas", "Coca cola", "Botella", 10, plate=2)
    groups = group_lines_by_plate(manager.get_order_lines("Mesa 1"))
    assert [(plate, [(l["variant"], l["qty"]) for l in lines]) for plate, lines in groups] == [
        (1, [("Pastor", 3), ("Birria", 1)]),
        (2, [("Pastor", 2)]),
        (0, [("Botella", 1)]),
    ]
    assert manager.used_plates("Mesa 1") == [1, 2]


def test_drinks_never_get_a_plate(manager):
    manager.create_table("Mesa 1")
    manager.add_item("Mesa 1", "Jugos", "Horchata", "Vaso", 15, plate=3)
    assert manager.get_items("Mesa 1")[0]["plate"] == 0
    with pytest.raises(ValueError):
        manager.move_line_to_plate("Mesa 1", 0, 1)


def test_invalid_plate_is_rejected(manager):
    manager.create_table("Mesa 1")
    with pytest.raises(ValueError):
        manager.add_item("Mesa 1", "Platillos", "Taco", "Pastor", 15, plate=99)
    assert manager.get_items("Mesa 1") == []


def test_move_units_between_plates_prefers_unsent_units(manager):
    manager.create_table("Mesa 1")
    manager.add_item("Mesa 1", "Platillos", "Taco", "Pastor", 15, qty=2, plate=1)
    manager.mark_sent_to_kitchen("Mesa 1")
    manager.add_item("Mesa 1", "Platillos", "Taco", "Pastor", 15, qty=3, plate=1)
    assert manager.move_line_to_plate("Mesa 1", 0, 2, count=3) == (3, 0)
    assert manager.move_line_to_plate("Mesa 1", 0, 2, count=1) == (1, 1)
    lines = {l["plate"]: l["qty"] for l in manager.get_order_lines("Mesa 1")}
    assert lines == {1: 1, 2: 4}
    assert manager.get_total("Mesa 1") == 75.0


def test_plates_survive_restart_and_old_items_have_no_plate(manager, data_dir):
    manager.create_table("Mesa 1")
    manager.add_item("Mesa 1", "Platillos", "Taco", "Pastor", 15, plate=2)
    state_path = os.path.join(data_dir, "estado_pedidos.json")
    with open(state_path, encoding="utf-8") as f:
        state = json.load(f)
    state["orders"][0]["items"].append({"category": "Platillos", "dish": "Taco", "variant": "Carne",
                                        "price": 15, "note": ""})
    with open(state_path, "w", encoding="utf-8") as f:
        json.dump(state, f)
    restored = OrderManager(root=data_dir, cutoff_hour=4)
    assert [i["plate"] for i in restored.get_items("Mesa 1")] == [2, 0]


def test_sale_excel_text_merges_plates(manager):
    from models import reports

    manager.create_table("Mesa 1")
    manager.add_item("Mesa 1", "Platillos", "Taco", "Pastor", 15, qty=3, plate=1)
    manager.add_item("Mesa 1", "Platillos", "Taco", "Pastor", 15, qty=2, plate=2)
    manager.register_payment("Mesa 1", "QR", qr_amount=75)
    sale = reports.read_sales(manager.root, manager.today())[0]
    assert [l["plate"] for l in sale["items"]] == [1, 2]
    assert reports.items_text(sale["items"]) == "Taco (Pastor) x5"
    assert manager.day_summary()["products"][0]["qty"] == 5
