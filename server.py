# server.py
"""
Mini servidor Flask para toma de pedidos desde celular.
Corre en segundo plano junto a la app PyQt6.
"""
import threading
import socket
from flask import Flask, jsonify, request, render_template

flask_app = Flask(__name__, template_folder="templates")

# Referencia global al OrderManager (se inyecta desde main.py)
_order_manager = None
_menu_data = None
_on_new_item_callback = None  # Callback para refrescar la UI de PyQt6


def init_server(order_manager, menu_data, on_new_item_callback=None):
    """Inyecta dependencias antes de arrancar el servidor."""
    global _order_manager, _menu_data, _on_new_item_callback
    _order_manager = order_manager
    _menu_data = menu_data
    _on_new_item_callback = on_new_item_callback


def get_local_ip() -> str:
    """Obtiene la IP local de la PC en la red WiFi."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


# -----------------------------------------------
#  Rutas de la API
# -----------------------------------------------

@flask_app.route("/")
def index():
    """Pantalla principal del mesero."""
    return render_template("mesero.html")


@flask_app.route("/api/menu")
def api_menu():
    """Devuelve el menu completo en JSON."""
    if _menu_data is None:
        return jsonify({"error": "Menu no disponible"}), 503
    menu = _menu_data.get_menu_prices()
    return jsonify(menu)


@flask_app.route("/api/mesas")
def api_mesas():
    """Devuelve la lista de mesas/pedidos activos."""
    if _order_manager is None:
        return jsonify([]), 503
    mesas = []
    for tabla in _order_manager.get_all_tables():
        paid, _ = _order_manager.get_payment_status(tabla)
        mesas.append({
            "nombre": tabla,
            "pagado": paid,
        })
    return jsonify(mesas)


@flask_app.route("/api/agregar", methods=["POST"])
def api_agregar():
    """
    Agrega un item al pedido de una mesa.
    Body JSON: { mesa, categoria, platillo, variante }
    """
    if _order_manager is None:
        return jsonify({"ok": False, "error": "Sistema no listo"}), 503

    data = request.get_json(force=True)
    mesa     = (data.get("mesa") or "").strip()
    categoria = (data.get("categoria") or "").strip()
    platillo  = (data.get("platillo") or "").strip()
    variante  = (data.get("variante") or "").strip()

    if not all([mesa, categoria, platillo, variante]):
        return jsonify({"ok": False, "error": "Faltan datos"}), 400

    if not _order_manager.name_exists(mesa):
        return jsonify({"ok": False, "error": f"La mesa '{mesa}' no existe"}), 404

    paid, _ = _order_manager.get_payment_status(mesa)
    if paid:
        return jsonify({"ok": False, "error": "Este pedido ya fue pagado"}), 400

    try:
        menu = _menu_data.get_menu_prices()
        price = menu[categoria][platillo][variante]
    except (KeyError, TypeError):
        return jsonify({"ok": False, "error": "Platillo no encontrado en el menu"}), 404

    tabla_anterior = _order_manager.current_table
    _order_manager.set_current_table(mesa)
    try:
        _order_manager.add_item_to_order(categoria, platillo, variante, price)
    except PermissionError as e:
        _order_manager.set_current_table(tabla_anterior)
        return jsonify({"ok": False, "error": str(e)}), 403
    _order_manager.set_current_table(tabla_anterior)

    # Notificar a la UI de PyQt6 para que refresque el display
    if _on_new_item_callback:
        _on_new_item_callback(mesa)

    return jsonify({"ok": True, "mensaje": f"'{platillo} ({variante})' agregado a {mesa}"})


@flask_app.route("/api/pedido/<mesa_nombre>")
def api_pedido(mesa_nombre):
    """Devuelve el resumen del pedido de una mesa."""
    if _order_manager is None:
        return jsonify({"error": "Sistema no listo"}), 503

    mesa_nombre = mesa_nombre.strip()
    if not _order_manager.name_exists(mesa_nombre):
        return jsonify({"error": "Mesa no encontrada"}), 404

    items = _order_manager.table_orders.get(mesa_nombre, [])
    total = sum(i["price"] for i in items)
    paid, method = _order_manager.get_payment_status(mesa_nombre)

    from collections import Counter
    summary = Counter(f"{i['dish']} ({i['variant']})" for i in items)
    detalle = [{"item": k, "cantidad": v} for k, v in summary.items()]

    return jsonify({
        "mesa": mesa_nombre,
        "items": detalle,
        "total": round(total, 2),
        "pagado": paid,
        "metodo_pago": method,
    })


# -----------------------------------------------
#  Arranque en hilo separado
# -----------------------------------------------

def start_server(port: int = 5000):
    """Arranca Flask en un hilo daemon (no bloquea la UI)."""
    def run():
        flask_app.run(
            host="0.0.0.0",
            port=port,
            debug=False,
            use_reloader=False,
        )
    t = threading.Thread(target=run, daemon=True)
    t.start()
    return port
