import pytest

from models.menu import MenuData
from server import create_app

PIN = "4821"


class FakePrinter:
    """Hace de caja: registra lo que el mesero manda a imprimir."""

    def __init__(self, mode="comanda_y_cuenta", status=200):
        self.mode = mode
        self.status = status
        self.calls = []

    def waiter_print_mode(self):
        return self.mode

    def print_for_waiter(self, kind, table, full):
        self.calls.append((kind, table, full))
        if self.status != 200:
            return {"ok": False, "error": "Impresora sin papel"}, self.status
        return {"ok": True, "mensaje": f"{kind} impresa"}, 200


def make_client(manager, menu_file, printer=None):
    app = create_app(manager, MenuData(menu_file), PIN, printer=printer)
    app.testing = True
    return app.test_client()


def api(client, method, url, **kwargs):
    return getattr(client, method)(url, headers={"X-PIN": PIN}, **kwargs)


def taco(**extra):
    return {"categoria": "Platillos", "platillo": "Taco", "variante": "Carne", **extra}


def coca(**extra):
    return {"categoria": "Bebidas", "platillo": "Coca cola", "variante": "Botella", **extra}


# ---------------------------------------------------------------------------
#  Agotados
# ---------------------------------------------------------------------------
def test_unavailable_soda_is_rejected_and_listed(manager, menu_file):
    client = make_client(manager, menu_file)
    manager.create_table("Mesa 1")
    manager.inventory.set_available("Bebidas", "Coca cola", "Botella", False)

    listed = api(client, "get", "/api/agotados").get_json()["agotados"]
    assert [(a["platillo"], a["variante"]) for a in listed] == [("Coca cola", "Botella")]
    assert api(client, "get", "/api/ajustes").get_json()["agotados"][0]["platillo"] == "Coca cola"

    res = api(client, "post", "/api/pedido/Mesa 1/items", json={"items": [taco(), coca()]})
    body = res.get_json()
    assert res.status_code == 409 and "Se acabó: Coca cola (Botella)" in body["error"]
    assert body["agotados"] == [{"categoria": "Bebidas", "platillo": "Coca cola", "variante": "Botella"}]
    assert manager.get_items("Mesa 1") == []  # ni el taco entra: el mesero corrige y reenvia

    manager.inventory.set_available("Bebidas", "Coca cola", "Botella", True)
    assert api(client, "post", "/api/pedido/Mesa 1/items", json={"items": [taco(), coca()]}).status_code == 200


# ---------------------------------------------------------------------------
#  Impresion desde el celular
# ---------------------------------------------------------------------------
def test_order_detail_reports_items_without_kitchen_ticket(manager, menu_file):
    client = make_client(manager, menu_file)
    manager.create_table("Mesa 1")
    manager.add_item("Mesa 1", "Platillos", "Taco", "Carne", 15, qty=3)
    assert api(client, "get", "/api/pedido/Mesa 1").get_json()["sin_comanda"] == 3
    manager.mark_sent_to_kitchen("Mesa 1")
    manager.add_item("Mesa 1", "Bebidas", "Coca cola", "Botella", 10)
    assert api(client, "get", "/api/pedido/Mesa 1").get_json()["sin_comanda"] == 1


def test_print_needs_printer_valid_type_and_existing_table(manager, menu_file):
    manager.create_table("Mesa 1")
    no_printer = make_client(manager, menu_file)
    assert api(no_printer, "get", "/api/ajustes").get_json()["meseros_imprimen"] == "no"
    assert api(no_printer, "post", "/api/pedido/Mesa 1/imprimir", json={"tipo": "comanda"}).status_code == 503

    client = make_client(manager, menu_file, FakePrinter())
    assert api(client, "post", "/api/pedido/Mesa 1/imprimir", json={"tipo": "menu"}).status_code == 400
    assert api(client, "post", "/api/pedido/Mesa 9/imprimir", json={"tipo": "comanda"}).status_code == 404


def test_waiter_prints_kitchen_ticket_and_bill(manager, menu_file):
    printer = FakePrinter()
    client = make_client(manager, menu_file, printer)
    manager.create_table("Mesa 1")
    res = api(client, "post", "/api/pedido/mesa 1/imprimir", json={"tipo": "comanda"})
    assert res.status_code == 200 and res.get_json()["ok"]
    api(client, "post", "/api/pedido/Mesa 1/imprimir", json={"tipo": "comanda", "todo": True})
    api(client, "post", "/api/pedido/Mesa 1/imprimir", json={"tipo": "cuenta"})
    assert printer.calls == [("comanda", "Mesa 1", False), ("comanda", "Mesa 1", True), ("cuenta", "Mesa 1", False)]


def test_print_permissions(manager, menu_file):
    manager.create_table("Mesa 1")
    only_kitchen = FakePrinter(mode="solo_comanda")
    client = make_client(manager, menu_file, only_kitchen)
    assert api(client, "get", "/api/ajustes").get_json()["meseros_imprimen"] == "solo_comanda"
    assert api(client, "post", "/api/pedido/Mesa 1/imprimir", json={"tipo": "cuenta"}).status_code == 403
    assert api(client, "post", "/api/pedido/Mesa 1/imprimir", json={"tipo": "comanda"}).status_code == 200

    nothing = FakePrinter(mode="no")
    client = make_client(manager, menu_file, nothing)
    assert api(client, "post", "/api/pedido/Mesa 1/imprimir", json={"tipo": "comanda"}).status_code == 403
    assert nothing.calls == []


def test_retry_with_same_request_id_prints_once(manager, menu_file):
    printer = FakePrinter()
    client = make_client(manager, menu_file, printer)
    manager.create_table("Mesa 1")
    body = {"tipo": "comanda", "request_id": "abc123"}
    first = api(client, "post", "/api/pedido/Mesa 1/imprimir", json=body).get_json()
    second = api(client, "post", "/api/pedido/Mesa 1/imprimir", json=body).get_json()
    assert first == second and len(printer.calls) == 1


def test_printer_error_is_reported_and_retry_prints_again(manager, menu_file):
    printer = FakePrinter(status=502)
    client = make_client(manager, menu_file, printer)
    manager.create_table("Mesa 1")
    body = {"tipo": "comanda", "request_id": "err1"}
    res = api(client, "post", "/api/pedido/Mesa 1/imprimir", json=body)
    assert res.status_code == 502 and res.get_json()["error"] == "Impresora sin papel"
    printer.status = 200
    assert api(client, "post", "/api/pedido/Mesa 1/imprimir", json=body).status_code == 200
    assert len(printer.calls) == 2
