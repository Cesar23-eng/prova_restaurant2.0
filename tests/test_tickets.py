import datetime

import pytest

from utils import printer, tickets

NOW = datetime.datetime(2026, 9, 15, 14, 32)


def order_with(manager, name="Mesa 4"):
    return manager.get_order(name)


@pytest.fixture
def mesa(manager):
    manager.create_table("Mesa 4")
    manager.add_item("Mesa 4", "Platillos", "Taco con queso", "Carne", 17, qty=2, plate=1, note="sin cebolla")
    manager.add_item("Mesa 4", "Platillos", "Taco con queso", "Carne", 17, qty=1, plate=2)
    manager.add_item("Mesa 4", "Platillos", "Quesadilla", "Pollo", 35)
    manager.add_item("Mesa 4", "Bebidas", "Coca cola", "Botella", 10, qty=2)
    return manager


def test_kitchen_ticket_layout_fits_80mm_paper(mesa):
    lines = mesa.get_order_lines("Mesa 4")
    ticket = tickets.kitchen_ticket("PRÖVA México", order_with(mesa), "Mesa 4", lines, False, 48, NOW)
    text = tickets.to_text(ticket)
    assert all(len(row) <= 48 for row in text.splitlines())
    assert (text.index("== PLATO 1 ==") < text.index(" 2 x Taco con queso (Carne)")
            < text.index(">> sin cebolla") < text.index("== PLATO 2 ==") < text.index("== SIN PLATO =="))
    assert "Bs" not in text  # la comanda de cocina no lleva precios
    assert "15/09/2026 14:32" in text and text.rstrip().endswith("6 items")
    styles = {line.text: (line.bold, line.size) for line in ticket.lines}
    assert styles["== PLATO 1 =="] == (True, "tall")
    assert styles[" 2 x Taco con queso (Carne)"] == (True, "normal")
    assert styles["#0001  Mesa 4"] == (True, "tall")


def test_kitchen_ticket_marks_additions_and_reprint(mesa):
    mesa.mark_sent_to_kitchen("Mesa 4")
    mesa.add_item("Mesa 4", "Platillos", "Taco", "Pastor", 15, plate=2)
    pending = mesa.get_order_lines("Mesa 4", kitchen_pending_only=True)
    text = tickets.to_text(tickets.kitchen_ticket("PRÖVA", order_with(mesa), "Mesa 4", pending, False, 48, NOW))
    assert "== PLATO 2 (agregar) ==" in text and "PLATO 1" not in text
    reprint = tickets.to_text(tickets.kitchen_ticket(
        "PRÖVA", order_with(mesa), "Mesa 4", mesa.get_order_lines("Mesa 4"), True, 48, NOW))
    assert "COMANDA COCINA - REIMPRESION" in reprint and "(agregar)" not in reprint


def test_long_names_wrap_with_indent_on_58mm(manager):
    manager.create_table("Mesa 1")
    manager.add_item("Mesa 1", "Jugos", "Tamarindo llevar 1 litro", "Botella", 30, qty=12,
                     note="con poco hielo y sin azúcar por favor")
    text = tickets.to_text(tickets.kitchen_ticket(
        "PRÖVA", manager.get_order("Mesa 1"), "Mesa 1", manager.get_order_lines("Mesa 1"), False, 32, NOW))
    rows = text.splitlines()
    assert all(len(row) <= 32 for row in rows)
    assert any(row.startswith("     ") and "Botella" in row for row in rows)


def test_customer_bill_merges_plates_and_totals(mesa):
    mesa.set_delivery_details("Mesa 4", 10, "Efectivo")
    text = tickets.to_text(tickets.customer_bill(
        "PRÖVA México", "Santa Cruz de la Sierra", order_with(mesa), "Mesa 4", mesa.get_order_lines("Mesa 4"),
        48, NOW))
    rows = text.splitlines()
    assert all(len(row) <= 48 for row in rows)
    assert "3 x Taco con queso (Carne)" in text and "Plato" not in text
    assert any(row.startswith("3 x Taco con queso (Carne)") and row.endswith("51.00") for row in rows)
    assert "sin cebolla" not in text
    total = next(line for line in tickets.customer_bill(
        "PRÖVA", "", order_with(mesa), "Mesa 4", mesa.get_order_lines("Mesa 4"), 48, NOW).lines
        if line.text.startswith("TOTAL"))
    assert total.size == "big" and len(total.text) == 24 and total.text.endswith("Bs 106.00")


def test_escpos_bytes_use_native_font_codepage_and_cut(mesa):
    ticket = tickets.kitchen_ticket("PRÖVA México", order_with(mesa), "Mesa 4",
                                    mesa.get_order_lines("Mesa 4"), False, 48, NOW)
    data = tickets.to_escpos(ticket)
    assert data.startswith(b"\x1b@\x1bt\x10\x1bM\x00")        # reinicio, WPC1252, Font A
    assert data.endswith(b"\x1bd\x04\x1dVB\x00")              # avance y corte parcial
    assert "PRÖVA México".encode("cp1252") in data
    plate_header = data.index(b"== PLATO 1 ==")
    assert data.rfind(b"\x1d!\x01", 0, plate_header) > data.rfind(b"\x1d!\x00", 0, plate_header)
    item = data.index(b" 2 x Taco con queso (Carne)")
    assert data.rfind(b"\x1d!\x00", 0, item) > plate_header


def test_day_summary_and_test_tickets_fit_width(manager):
    manager.create_table("Mesa 1")
    manager.add_item("Mesa 1", "Platillos", "Taco", "Pastor", 15, qty=2)
    manager.register_payment("Mesa 1", "Efectivo", cash_amount=50, change_method="Efectivo")
    summary = tickets.to_text(tickets.day_summary_ticket("PRÖVA México", manager.day_summary(), "15/09/2026", 48, NOW))
    assert all(len(row) <= 48 for row in summary.splitlines())
    assert "Efectivo neto en caja" in summary and "Bs 30.00" in summary
    for columns in (48, 32):
        prueba = tickets.test_ticket("PRÖVA", "EPSON TM-T20III Receipt", columns, NOW)
        assert all(len(line.text) <= prueba.width_for(line.size) for line in prueba.lines)


def test_choose_printer_prefers_configured_then_epson_then_default():
    installed = ["Microsoft Print to PDF", "EPSON TM-T20III Receipt", "HP LaserJet"]
    assert printer.choose_printer(installed, "HP LaserJet", "Microsoft Print to PDF") == "HP LaserJet"
    assert printer.choose_printer(installed, "Impresora que ya no existe", "HP LaserJet") == "EPSON TM-T20III Receipt"
    assert printer.choose_printer(["Microsoft Print to PDF", "Fax"], "", "Microsoft Print to PDF") == "Microsoft Print to PDF"
    assert printer.choose_printer([], "", "") is None
    assert printer.looks_thermal("EPSON TM-T20III Receipt5")
    assert not printer.looks_thermal("Microsoft XPS Document Writer")
    assert printer.resolve_mode("auto", "EPSON TM-T20III Receipt") == "escpos"
    assert printer.resolve_mode("auto", "HP LaserJet") == "windows"
    assert printer.resolve_mode("escpos", "HP LaserJet") == "escpos"


def test_ticket_printer_sends_escpos_to_epson(monkeypatch):
    sent = []
    monkeypatch.setattr(printer, "send_raw", lambda name, data, job: sent.append((name, data, job)))
    ticket_printer = printer.TicketPrinter({"modo_impresion": "auto", "ancho_papel_mm": 80},
                                           ["Microsoft Print to PDF", "EPSON TM-T20III Receipt"],
                                           "Microsoft Print to PDF")
    ticket = tickets.test_ticket("PRÖVA", "EPSON", ticket_printer.columns, NOW)
    assert ticket_printer.print_ticket(ticket, "PROVA prueba") == "EPSON TM-T20III Receipt"
    assert sent[0][0] == "EPSON TM-T20III Receipt" and sent[0][1].startswith(b"\x1b@")
    with pytest.raises(printer.PrinterError):
        printer.TicketPrinter({}, [], "").print_ticket(ticket)


def test_large_kitchen_font_option(mesa):
    lines = mesa.get_order_lines("Mesa 4")
    normal = tickets.kitchen_ticket("PRÖVA", order_with(mesa), "Mesa 4", lines, False, 48, NOW)
    large = tickets.kitchen_ticket("PRÖVA", order_with(mesa), "Mesa 4", lines, False, 48, NOW, large_items=True)
    item = " 2 x Taco con queso (Carne)"
    assert next(l.size for l in normal.lines if l.text == item) == "normal"
    assert next(l.size for l in large.lines if l.text == item) == "tall"
    assert next(l.size for l in large.lines if ">> sin cebolla" in l.text) == "normal"
    assert printer.TicketPrinter({"letra_comanda": "grande"}, [], "").large_kitchen_items
