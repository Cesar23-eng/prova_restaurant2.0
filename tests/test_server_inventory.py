from models.menu import MenuData
from server import create_app

PIN = "4821"


def make_client(manager, menu_file):
    app = create_app(manager, MenuData(menu_file), PIN)
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
#  Los meseros ya no imprimen
# ---------------------------------------------------------------------------
def test_waiters_cannot_print(manager, menu_file):
    client = make_client(manager, menu_file)
    manager.create_table("Mesa 1")
    manager.add_item("Mesa 1", "Platillos", "Taco", "Carne", 15)
    assert "meseros_imprimen" not in api(client, "get", "/api/ajustes").get_json()
    res = api(client, "post", "/api/pedido/Mesa 1/imprimir", json={"tipo": "comanda"})
    assert res.status_code in (404, 405)


# ---------------------------------------------------------------------------
#  Mesas cobradas
# ---------------------------------------------------------------------------
def test_paid_tables_leave_the_phone_list_and_can_be_reopened(manager, menu_file):
    client = make_client(manager, menu_file)
    manager.create_table("Mesa 1")
    manager.add_item("Mesa 1", "Platillos", "Taco", "Carne", 15)
    manager.register_payment("Mesa 1", "QR", qr_amount=15)
    manager.create_table("Mesa 2")
    assert [m["nombre"] for m in api(client, "get", "/api/mesas").get_json()] == ["Mesa 2"]

    res = api(client, "post", "/api/mesas", json={"nombre": "mesa 1"})
    assert res.status_code == 201 and res.get_json()["mesa"]["numero"] == "#0003"
    assert not manager.is_paid("mesa 1")
