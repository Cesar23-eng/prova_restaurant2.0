import pytest

from models.menu import MenuData
from server import MAX_FAILED_PIN_ATTEMPTS, WaiterServer, create_app

PIN = "4821"


@pytest.fixture
def client(manager, menu_file):
    app = create_app(manager, MenuData(menu_file), PIN)
    app.testing = True
    return app.test_client()


def api(client, method, url, pin=PIN, **kwargs):
    return getattr(client, method)(url, headers={"X-PIN": pin}, **kwargs)


def taco(**extra):
    return {"categoria": "Platillos", "platillo": "Taco", "variante": "Carne", **extra}


def test_page_is_public_but_api_requires_pin(client):
    assert client.get("/").status_code == 200
    assert client.get("/api/mesas").status_code == 401
    assert api(client, "get", "/api/mesas", pin="0000").status_code == 401
    assert api(client, "get", "/api/mesas").status_code == 200


def test_pin_brute_force_is_locked_out(client):
    for _ in range(MAX_FAILED_PIN_ATTEMPTS):
        api(client, "get", "/api/ping", pin="0000")
    assert api(client, "get", "/api/ping").status_code == 429


def test_waiter_creates_table_and_sends_batch(client, manager):
    res = api(client, "post", "/api/mesas", json={"nombre": "Mesa 7", "tipo": "Para llevar"})
    assert res.status_code == 201
    assert res.get_json()["mesa"]["numero"] == "#0001"
    assert api(client, "post", "/api/mesas", json={"nombre": "mesa 7"}).status_code == 409

    res = api(client, "post", "/api/pedido/Mesa 7/items", json={
        "request_id": "abc",
        "items": [taco(cantidad=2, nota="sin cebolla"),
                  {"categoria": "Bebidas", "platillo": "Coca cola", "variante": "Botella"}],
    })
    assert res.get_json() == {"ok": True, "agregados": 3, "mensaje": "3 platillo(s) agregado(s) a Mesa 7"}
    assert manager.get_total("Mesa 7") == 40.0
    assert manager.get_order_type("Mesa 7") == "Para llevar"

    detail = api(client, "get", "/api/pedido/mesa 7").get_json()
    assert detail["items"][0] == {
        "item": "Taco (Carne)", "platillo": "Taco", "variante": "Carne",
        "nota": "sin cebolla", "cantidad": 2, "subtotal": 30.0,
    }


def test_retry_with_same_request_id_does_not_duplicate(client, manager):
    manager.create_table("Mesa 1")
    body = {"request_id": "retry-1", "items": [taco()]}
    first = api(client, "post", "/api/pedido/Mesa 1/items", json=body).get_json()
    second = api(client, "post", "/api/pedido/Mesa 1/items", json=body).get_json()
    assert first == second
    assert len(manager.get_items("Mesa 1")) == 1


def test_batch_with_unknown_dish_adds_nothing(client, manager):
    manager.create_table("Mesa 1")
    res = api(client, "post", "/api/pedido/Mesa 1/items", json={
        "items": [taco(), {"categoria": "Platillos", "platillo": "Pizza", "variante": "Grande"}],
    })
    assert res.status_code == 404
    assert manager.get_items("Mesa 1") == []


def test_price_comes_from_server_menu(client, manager):
    manager.create_table("Mesa 1")
    api(client, "post", "/api/pedido/Mesa 1/items", json={"items": [taco(precio=0.01)]})
    assert manager.get_total("Mesa 1") == 15.0


def test_paid_order_rejects_new_items(client, manager):
    manager.create_table("Mesa 1")
    manager.add_item("Mesa 1", "Platillos", "Taco", "Carne", 15)
    manager.register_payment("Mesa 1", "QR", qr_amount=15)
    res = api(client, "post", "/api/pedido/Mesa 1/items", json={"items": [taco()]})
    assert res.status_code == 409


def test_legacy_single_item_endpoint(client, manager):
    manager.create_table("Mesa 1")
    res = api(client, "post", "/api/agregar", json={"mesa": "Mesa 1", **taco()})
    assert res.get_json()["ok"] is True
    assert manager.get_total("Mesa 1") == 15.0


def test_server_falls_back_to_next_free_port(manager, menu_file):
    app = create_app(manager, MenuData(menu_file), PIN)
    first, second = WaiterServer(app), WaiterServer(app)
    try:
        port = first.start(port=5750)
        assert second.start(port=port) == port + 1
    finally:
        first.stop()
        second.stop()
