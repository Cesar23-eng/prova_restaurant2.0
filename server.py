# server.py
"""
Servidor web para toma de pedidos desde el celular de los meseros.
Corre en un hilo aparte junto a la app PyQt6 y comparte el mismo OrderManager.

Todas las rutas /api/* piden el PIN de meseros (cabecera X-PIN) para que un
cliente conectado al WiFi del local no pueda cargar pedidos.
"""
import datetime
import hmac
import os
import socket
import threading
import time
from collections import OrderedDict

from flask import Flask, jsonify, render_template, request, send_file

from models.order import MAX_PLATES, ORDER_TYPE_LOCAL, ORDER_TYPES
from utils.config import app_dir, resource_dir
from utils.icons import menu_icons

MAX_FAILED_PIN_ATTEMPTS = 10
PIN_LOCKOUT_SECONDS = 60
MAX_REMEMBERED_REQUESTS = 500


def _minutes_since(stamp) -> int:
    try:
        started = datetime.datetime.fromisoformat(stamp)
    except (TypeError, ValueError):
        return 0
    return max(0, int((datetime.datetime.now() - started).total_seconds() // 60))


def create_app(order_manager, menu_data, pin, table_count: int = 13) -> Flask:
    """
    `pin` puede ser un texto o una funcion que devuelve el PIN vigente.
    `table_count` es la cantidad de botones rapidos "Mesa 1..N" en el celular.
    """
    current_pin = pin if callable(pin) else (lambda: pin)
    app = Flask(__name__, template_folder=os.path.join(resource_dir(), "templates"))
    app.json.ensure_ascii = False
    app.json.sort_keys = False

    failed_attempts = {}  # ip -> (intentos, bloqueado_hasta)
    processed_requests = OrderedDict()  # request_id -> respuesta ya enviada
    requests_in_progress = set()
    guard = threading.Lock()

    def error(message: str, status: int):
        return jsonify({"ok": False, "error": message}), status

    @app.before_request
    def require_pin():
        if not request.path.startswith("/api/"):
            return None
        ip = request.remote_addr or "?"
        now = time.monotonic()
        with guard:
            attempts, blocked_until = failed_attempts.get(ip, (0, 0.0))
            if blocked_until > now:
                return error("Demasiados intentos. Espera un minuto.", 429)
        supplied = request.headers.get("X-PIN", "")
        if hmac.compare_digest(supplied.encode(), str(current_pin()).encode()):
            with guard:
                failed_attempts.pop(ip, None)
            return None
        with guard:
            attempts += 1
            blocked = now + PIN_LOCKOUT_SECONDS if attempts >= MAX_FAILED_PIN_ATTEMPTS else 0.0
            failed_attempts[ip] = (0 if blocked else attempts, blocked)
        return error("PIN incorrecto", 401)

    @app.after_request
    def no_cache(response):
        response.headers["Cache-Control"] = "no-store"
        return response

    @app.route("/")
    def index():
        return render_template("mesero.html")

    @app.route("/logo.png")
    def logo():
        """Logo del local para el encabezado del celular (publico, sin PIN)."""
        for name in ("prova.png", "PROVA.png"):
            path = os.path.join(app_dir(), name)
            if os.path.exists(path):
                return send_file(path, mimetype="image/png")
        return "", 404

    @app.route("/api/ping")
    def api_ping():
        return jsonify({"ok": True})

    @app.route("/api/ajustes")
    def api_ajustes():
        return jsonify({
            "productos_con_plato": order_manager.plate_products,
            "max_platos": MAX_PLATES,
            "iconos": menu_icons(menu_data.get_menu_prices()),
            "numero_mesas": int(table_count),
        })

    @app.route("/api/menu")
    def api_menu():
        menu = menu_data.get_menu_prices()
        if not menu:
            return error(menu_data.last_error or "Menu no disponible", 503)
        return jsonify(menu)

    def table_payload(name: str):
        order = order_manager.get_order(name)
        if order is None:
            return None
        return {
            "nombre": name,
            "numero": order["number"],
            "tipo": order["order_type"],
            "pagado": order["paid"],
            "items": len(order["items"]),
            "total": round(sum(i["price"] for i in order["items"]), 2),
            # Calculado en la caja: el reloj de cada celular puede estar desfasado
            "minutos": _minutes_since(order.get("created_at")),
        }

    @app.route("/api/mesas", methods=["GET"])
    def api_mesas():
        tables = (table_payload(n) for n in order_manager.get_all_tables())
        return jsonify([t for t in tables if t])

    @app.route("/api/mesas", methods=["POST"])
    def api_crear_mesa():
        data = request.get_json(silent=True) or {}
        nombre = (data.get("nombre") or "").strip()
        tipo = data.get("tipo") or ORDER_TYPE_LOCAL
        if not nombre:
            return error("Escribe el nombre de la mesa o cliente", 400)
        if tipo not in ORDER_TYPES:
            return error("Tipo de consumo invalido", 400)
        ok, result = order_manager.create_table(nombre, order_type=tipo, source="mesero")
        if not ok:
            return error(f"Ya existe una mesa con ese nombre. Prueba con '{result}'", 409)
        return jsonify({"ok": True, "mesa": table_payload(result)}), 201

    @app.route("/api/pedido/<path:mesa_nombre>")
    def api_pedido(mesa_nombre):
        name = order_manager.resolve_name(mesa_nombre.strip())
        if name is None:
            return error("Mesa no encontrada", 404)
        order = order_manager.get_order(name)
        if order is None:  # la caja la elimino justo ahora
            return error("Mesa no encontrada", 404)
        lines = order_manager.get_order_lines(name)
        return jsonify({
            "ok": True,
            "mesa": name,
            "numero": order["number"],
            "tipo": order["order_type"],
            "items": [
                {
                    "item": f"{l['dish']} ({l['variant']})",
                    "platillo": l["dish"],
                    "variante": l["variant"],
                    "nota": l["note"],
                    "plato": l["plate"],
                    "cantidad": l["qty"],
                    "subtotal": l["subtotal"],
                }
                for l in lines
            ],
            "total": round(sum(l["subtotal"] for l in lines), 2),
            "pagado": order["paid"],
            "metodo_pago": (order["payment"] or {}).get("method", ""),
        })

    def add_items_to_table(mesa: str, raw_items, request_id: str):
        """
        `request_id` lo genera el celular por cada envio. Si el WiFi se corta y el
        mesero reintenta, el pedido no se duplica: se devuelve la respuesta original.
        """
        if not request_id:
            return _add_items(mesa, raw_items)
        with guard:
            if request_id in processed_requests:
                return jsonify(processed_requests[request_id])
            if request_id in requests_in_progress:
                return error("El pedido se esta procesando, intenta de nuevo", 409)
            requests_in_progress.add(request_id)
        try:
            result = _add_items(mesa, raw_items)
            if isinstance(result, dict):
                with guard:
                    processed_requests[request_id] = result
                    while len(processed_requests) > MAX_REMEMBERED_REQUESTS:
                        processed_requests.popitem(last=False)
            return result
        finally:
            with guard:
                requests_in_progress.discard(request_id)

    def _add_items(mesa: str, raw_items):
        name = order_manager.resolve_name(mesa)
        if name is None:
            return error(f"La mesa '{mesa}' no existe", 404)
        if not isinstance(raw_items, list) or not raw_items:
            return error("No hay platillos para enviar", 400)

        # El precio siempre sale del menu del servidor, nunca del celular
        menu = menu_data.get_menu_prices()
        items = []
        for raw in raw_items:
            if not isinstance(raw, dict):
                return error("Formato de pedido invalido", 400)
            categoria = (raw.get("categoria") or "").strip()
            platillo = (raw.get("platillo") or "").strip()
            variante = (raw.get("variante") or "").strip()
            price = menu.get(categoria, {}).get(platillo, {}).get(variante)
            if price is None:
                return error(f"'{platillo} ({variante})' ya no esta en el menu", 404)
            items.append({
                "category": categoria, "dish": platillo, "variant": variante,
                "price": price, "note": raw.get("nota") or "",
                "qty": raw.get("cantidad") or 1,
                "plate": raw.get("plato") or 0,
            })

        try:
            count = order_manager.add_items(name, items, source="mesero")
        except PermissionError:
            return error("Este pedido ya fue pagado", 409)
        except KeyError:
            return error("La mesa ya no existe", 404)
        except ValueError as e:
            return error(str(e), 400)

        return {
            "ok": True,
            "agregados": count,
            "mensaje": f"{count} platillo(s) agregado(s) a {name}",
        }

    @app.route("/api/pedido/<path:mesa_nombre>/items", methods=["POST"])
    def api_agregar_items(mesa_nombre):
        data = request.get_json(silent=True) or {}
        return add_items_to_table(mesa_nombre.strip(), data.get("items"),
                                  str(data.get("request_id") or ""))

    @app.route("/api/agregar", methods=["POST"])
    def api_agregar():
        """Compatibilidad: agrega un solo item. Body: {mesa, categoria, platillo, variante}"""
        data = request.get_json(silent=True) or {}
        mesa = (data.get("mesa") or "").strip()
        if not mesa:
            return error("Faltan datos", 400)
        return add_items_to_table(mesa, [data], str(data.get("request_id") or ""))

    return app


def get_local_ip() -> str:
    """IP de la PC en la red del local (para que los meseros entren desde el celular)."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            # No envia nada: solo pregunta al sistema que interfaz usaria
            s.connect(("10.255.255.255", 1))
            ip = s.getsockname()[0]
            if not ip.startswith("127."):
                return ip
    except OSError:
        pass
    try:
        for ip in socket.gethostbyname_ex(socket.gethostname())[2]:
            if not ip.startswith("127."):
                return ip
    except OSError:
        pass
    return "127.0.0.1"


def _listen_exclusive(port: int) -> socket.socket:
    """
    Abre el puerto en modo exclusivo. werkzeug usa SO_REUSEADDR, que en Windows
    deja que otro programa (o una segunda copia de la app) escuche el mismo
    puerto y los celulares terminen enviando pedidos a la instancia equivocada.
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        else:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(("0.0.0.0", port))
        sock.listen(128)
    except OSError:
        sock.close()
        raise
    return sock


def _quiet_request_handler():
    from werkzeug.serving import WSGIRequestHandler

    class QuietRequestHandler(WSGIRequestHandler):
        """
        No escribe una linea por cada peticion. Los celulares consultan la caja
        cada pocos segundos y la consola se llenaba (y se abria sola en el IDE).
        Los errores del servidor se siguen registrando.
        """

        def log_request(self, code="-", size="-"):
            pass

    return QuietRequestHandler


class WaiterServer:
    """Levanta el servidor en un hilo daemon; si el puerto esta ocupado prueba los siguientes."""

    def __init__(self, app: Flask):
        self.app = app
        self.port = None
        self._server = None

    def start(self, port: int = 5000, attempts: int = 10) -> int:
        from werkzeug.serving import make_server

        last_error = None
        for candidate in range(port, port + attempts):
            try:
                sock = _listen_exclusive(candidate)
                break
            except OSError as e:
                last_error = e
        else:
            raise OSError(f"No hay puertos libres entre {port} y {port + attempts - 1}: {last_error}")
        try:
            # Con fd, werkzeug usa el socket ya abierto y no llama a sys.exit si falla
            self._server = make_server("0.0.0.0", candidate, self.app, threaded=True,
                                       request_handler=_quiet_request_handler(), fd=sock.fileno())
        finally:
            sock.close()
        self.port = candidate
        threading.Thread(target=self._server.serve_forever, daemon=True,
                         name="servidor-meseros").start()
        return self.port

    def stop(self):
        if self._server is not None:
            self._server.shutdown()
            self._server = None
