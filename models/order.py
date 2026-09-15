import copy
import datetime
import json
import os
import threading
from collections import OrderedDict
from dataclasses import dataclass
from typing import Callable, Dict, Iterable, List, Optional, Tuple

from models import reports
from utils.config import atomic_write_text, business_date, data_root, day_dir, load_config

ORDER_TYPE_LOCAL = "En el local"
ORDER_TYPE_TAKEAWAY = "Para llevar"
ORDER_TYPES = (ORDER_TYPE_LOCAL, ORDER_TYPE_TAKEAWAY)
PAYMENT_METHODS = ("Efectivo", "QR", "Mixto")

STATE_FILENAME = "estado_pedidos.json"
MAX_NOTE_LENGTH = 120
MAX_QTY_PER_ADD = 100
# Plato 0 = sin plato. Solo los productos que se piden por unidad se reparten en platos.
MAX_PLATES = 30
DEFAULT_PLATE_PRODUCTS = ("Taco", "Taco con queso")


class OrderChangedError(Exception):
    """El pedido cambio (p. ej. un mesero agrego algo) mientras se cobraba."""

    def __init__(self, new_total: float):
        super().__init__(f"El pedido cambio. Nuevo total: Bs {new_total:.2f}")
        self.new_total = new_total


@dataclass
class PaymentResult:
    excel_ok: bool
    message: str = ""


Listener = Callable[[str, str, Dict], None]


def _now() -> datetime.datetime:
    return datetime.datetime.now()


def plate_label(plate: int) -> str:
    return f"Plato {plate}" if plate else "Sin plato"


def group_lines_by_plate(lines: List[Dict]) -> List[Tuple[int, List[Dict]]]:
    """Agrupa lineas por plato: Plato 1, Plato 2... y al final las que no tienen plato."""
    groups: "OrderedDict[int, List[Dict]]" = OrderedDict()
    for line in sorted(lines, key=lambda l: (not l.get("plate"), l.get("plate", 0))):
        groups.setdefault(line.get("plate", 0), []).append(line)
    return list(groups.items())


class OrderManager:
    """
    Pedidos abiertos del local.

    Lo usan a la vez la ventana de caja (hilo de Qt) y el servidor de meseros
    (hilos de Flask), por eso todo acceso pasa por un RLock. Cada cambio se
    guarda en data/estado_pedidos.json para recuperar los pedidos abiertos si
    la app se cierra o se corta la luz.
    """

    def __init__(self, root: Optional[str] = None, cutoff_hour: Optional[int] = None,
                 restore: bool = True, plate_products: Optional[Iterable[str]] = None):
        self.root = root or data_root()
        os.makedirs(self.root, exist_ok=True)
        if cutoff_hour is None or plate_products is None:
            config = load_config(self.root)
            if cutoff_hour is None:
                cutoff_hour = int(config.get("hora_corte_jornada", 4))
            if plate_products is None:
                plate_products = config.get("productos_con_plato", DEFAULT_PLATE_PRODUCTS)
        self.cutoff_hour = cutoff_hour
        self.plate_products = [str(p) for p in plate_products]
        self._plate_products_norm = {self._norm(p) for p in self.plate_products}

        self._lock = threading.RLock()
        self._excel_lock = threading.Lock()
        self._orders: "OrderedDict[str, Dict]" = OrderedDict()
        self._listeners: List[Listener] = []
        self._counter_date = ""
        self._counter = 0
        self.last_save_error = ""
        self.restored_count = 0

        # Mesa seleccionada en la ventana de caja (estado de UI, no lo usa el servidor)
        self.current_table: Optional[str] = None

        if restore:
            self._load_state()

    # -----------------------------------------------
    #  Notificaciones
    # -----------------------------------------------
    def add_listener(self, listener: Listener):
        self._listeners.append(listener)

    def _notify(self, event: str, table: str = "", **info):
        for listener in list(self._listeners):
            try:
                listener(event, table, info)
            except Exception:
                pass

    # -----------------------------------------------
    #  Jornada, auditoria y persistencia
    # -----------------------------------------------
    def today(self) -> datetime.date:
        return business_date(_now(), self.cutoff_hour)

    def _audit(self, action: str, table_name: str, detail: str = ""):
        today = self.today()
        log_file = os.path.join(day_dir(self.root, today), f"audit_log_{today:%Y-%m-%d}.txt")
        line = f"[{_now():%H:%M:%S}] {action:12s} | {table_name}"
        if detail:
            line += f" | {detail}"
        try:
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(line + "\n")
        except OSError:
            pass

    def _state_path(self) -> str:
        return os.path.join(self.root, STATE_FILENAME)

    def _save_state(self):
        data = {
            "version": 1,
            "saved_at": _now().isoformat(timespec="seconds"),
            "counter_date": self._counter_date,
            "counter": self._counter,
            "orders": list(self._orders.values()),
        }
        try:
            atomic_write_text(self._state_path(), json.dumps(data, ensure_ascii=False, indent=1))
            self.last_save_error = ""
        except OSError as e:
            self.last_save_error = str(e)
            self._audit("ERROR_ESTADO", "-", str(e))

    def _load_state(self):
        path = self._state_path()
        if not os.path.exists(path):
            return
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, ValueError) as e:
            backup = f"{path}.corrupto-{_now():%Y%m%d-%H%M%S}"
            try:
                os.replace(path, backup)
            except OSError:
                pass
            self._audit("ERROR_ESTADO", "-", f"estado ilegible ({e}), respaldado en {backup}")
            return

        today = self.today().isoformat()
        for order in data.get("orders", []):
            name = order.get("name")
            if not name:
                continue
            # Los pagados de jornadas anteriores ya estan en su Excel
            if order.get("paid") and order.get("paid_date") != today:
                continue
            order.setdefault("number", "")
            order.setdefault("order_type", ORDER_TYPE_LOCAL)
            order.setdefault("items", [])
            order.setdefault("paid", False)
            order.setdefault("payment", None)
            order.setdefault("delivery", None)
            for item in order["items"]:
                item.setdefault("note", "")
                item.setdefault("kitchen_sent", False)
                item.setdefault("plate", 0)
                if not self.plate_applies(item.get("dish", "")):
                    item["plate"] = 0
            self._orders[name] = order
            if not order["paid"]:
                self.restored_count += 1
        if data.get("counter_date") == today:
            self._counter_date = today
            self._counter = int(data.get("counter") or 0)

    def _purge_previous_days(self):
        """Si la app quedo abierta de un dia a otro, retira los pagados del dia anterior."""
        today = self.today().isoformat()
        stale = [n for n, o in self._orders.items() if o["paid"] and o.get("paid_date") != today]
        for name in stale:
            del self._orders[name]
            if self.current_table == name:
                self.current_table = None
        return bool(stale)

    def _next_order_number(self) -> str:
        """Numeracion por jornada; nunca repite un numero visible en pantalla."""
        today = self.today()
        if self._counter_date != today.isoformat():
            self._counter_date = today.isoformat()
            self._counter = 0
        self._counter = max(self._counter, reports.max_order_number(self.root, today))
        used = {reports.parse_order_number(o["number"]) for o in self._orders.values()}
        self._counter += 1
        while self._counter in used:
            self._counter += 1
        return f"#{self._counter:04d}"

    # -----------------------------------------------
    #  Utilidades de nombre
    # -----------------------------------------------
    @staticmethod
    def _norm(name: str) -> str:
        return " ".join((name or "").split()).strip().lower()

    @staticmethod
    def _clean(name: str) -> str:
        return " ".join((name or "").split()).strip()

    def name_exists(self, name: str) -> bool:
        return self.resolve_name(name) is not None

    def resolve_name(self, name: str) -> Optional[str]:
        """Devuelve el nombre real de la mesa, ignorando mayusculas y espacios."""
        with self._lock:
            if name in self._orders:
                return name
            n = self._norm(name)
            return next((k for k in self._orders if self._norm(k) == n), None)

    def suggest_name(self, base: str) -> str:
        base = self._clean(base)
        if not self.name_exists(base):
            return base
        i = 2
        while self.name_exists(f"{base} {i}"):
            i += 1
        return f"{base} {i}"

    def _get(self, table_name: str) -> Dict:
        order = self._orders.get(table_name)
        if order is None:
            raise KeyError(f"La mesa '{table_name}' no existe")
        return order

    def _ensure_open(self, order: Dict):
        if order["paid"]:
            raise PermissionError("El pedido ya fue pagado y no puede modificarse.")

    # -----------------------------------------------
    #  Gestion de mesas / ordenes
    # -----------------------------------------------
    def create_table(self, name: str, order_type: str = ORDER_TYPE_LOCAL,
                     source: str = "caja") -> Tuple[bool, str]:
        base = self._clean(name)
        if not base:
            return False, "Nombre invalido"
        if order_type not in ORDER_TYPES:
            order_type = ORDER_TYPE_LOCAL
        with self._lock:
            self._purge_previous_days()
            if self.name_exists(base):
                return False, self.suggest_name(base)
            number = self._next_order_number()
            self._orders[base] = {
                "name": base,
                "number": number,
                "order_type": order_type,
                "items": [],
                "created_at": _now().isoformat(timespec="seconds"),
                "created_by": source,
                "paid": False,
                "paid_date": None,
                "paid_at": None,
                "payment": None,
                "delivery": None,
            }
            self._save_state()
        self._audit("CREAR", base, f"numero={number} tipo={order_type} origen={source}")
        self._notify("created", base, source=source)
        return True, base

    def get_order_number(self, table_name: str) -> str:
        with self._lock:
            order = self._orders.get(table_name)
            return order["number"] if order else ""

    def set_current_table(self, table_name: Optional[str]):
        self.current_table = table_name

    def get_all_tables(self) -> List[str]:
        with self._lock:
            return list(self._orders.keys())

    def get_order(self, table_name: str) -> Optional[Dict]:
        with self._lock:
            order = self._orders.get(table_name)
            return copy.deepcopy(order) if order else None

    def get_items(self, table_name: str) -> List[Dict]:
        with self._lock:
            order = self._orders.get(table_name)
            return copy.deepcopy(order["items"]) if order else []

    def get_order_type(self, table_name: str) -> str:
        with self._lock:
            order = self._orders.get(table_name)
            return order["order_type"] if order else ORDER_TYPE_LOCAL

    def set_order_type(self, table_name: str, order_type: str):
        if order_type not in ORDER_TYPES:
            raise ValueError(f"Tipo de consumo invalido: {order_type}")
        with self._lock:
            order = self._get(table_name)
            if order["order_type"] == order_type:
                return
            self._ensure_open(order)
            order["order_type"] = order_type
            if order_type == ORDER_TYPE_LOCAL:
                order["delivery"] = None
            self._save_state()
        self._audit("TIPO", table_name, order_type)
        self._notify("updated", table_name)

    def add_item(self, table_name: str, category: str, dish: str, variant: str, price: float,
                 note: str = "", qty: int = 1, source: str = "caja", plate: int = 0):
        self.add_items(table_name, [{
            "category": category, "dish": dish, "variant": variant,
            "price": price, "note": note, "qty": qty, "plate": plate,
        }], source=source)

    def plate_applies(self, dish: str) -> bool:
        """
        Solo los productos de `productos_con_plato` (los tacos, que se piden por
        unidad) se reparten en platos; todo lo demas va sin plato.
        """
        return self._norm(dish) in self._plate_products_norm

    @staticmethod
    def _parse_plate(value) -> int:
        try:
            plate = int(value or 0)
        except (TypeError, ValueError):
            raise ValueError(f"Plato invalido: {value}")
        if not 0 <= plate <= MAX_PLATES:
            raise ValueError(f"El plato debe estar entre 1 y {MAX_PLATES}")
        return plate

    def add_items(self, table_name: str, items: List[Dict], source: str = "caja") -> int:
        """Agrega varios items de una sola vez: o entran todos o ninguno."""
        prepared = []
        stamp = _now().isoformat(timespec="seconds")
        for item in items:
            dish = self._clean(item.get("dish", ""))
            variant = self._clean(item.get("variant", ""))
            if not dish or not variant:
                raise ValueError("Platillo o variante vacio")
            try:
                price = round(float(item.get("price")), 2)
                qty = int(item.get("qty", 1))
            except (TypeError, ValueError):
                raise ValueError(f"Precio o cantidad invalida para {dish}")
            if price < 0 or not 1 <= qty <= MAX_QTY_PER_ADD:
                raise ValueError(f"Precio o cantidad invalida para {dish}")
            note = self._clean(item.get("note", ""))[:MAX_NOTE_LENGTH]
            category = self._clean(item.get("category", ""))
            plate = self._parse_plate(item.get("plate")) if self.plate_applies(dish) else 0
            unit = {
                "category": category,
                "dish": dish,
                "variant": variant,
                "price": price,
                "note": note,
                "plate": plate,
                "source": source,
                "added_at": stamp,
                "kitchen_sent": False,
            }
            prepared.extend(dict(unit) for _ in range(qty))
        if not prepared:
            return 0

        with self._lock:
            order = self._get(table_name)
            self._ensure_open(order)
            order["items"].extend(prepared)
            self._save_state()
        for line in self._group_lines(prepared):
            detail = f"{line['dish']} ({line['variant']}) x{line['qty']} Bs{line['unit_price']:.2f}"
            if line["note"]:
                detail += f" nota={line['note']}"
            if line["plate"]:
                detail += f" plato={line['plate']}"
            self._audit("AGREGAR", table_name, f"{detail} origen={source}")
        self._notify("items_added", table_name, source=source, count=len(prepared))
        return len(prepared)

    def add_item_to_order(self, category, dish, variant, price, note: str = "", qty: int = 1,
                          plate: int = 0):
        if not self.current_table:
            raise ValueError("No hay mesa seleccionada")
        self.add_item(self.current_table, category, dish, variant, price, note=note, qty=qty,
                      plate=plate)

    def remove_line(self, table_name: str, line_index: int, count: int = 1) -> int:
        """Quita `count` unidades de una linea agrupada del pedido."""
        with self._lock:
            order = self._get(table_name)
            self._ensure_open(order)
            lines = self._group_lines(order["items"])
            if not 0 <= line_index < len(lines):
                return 0
            key = lines[line_index]["key"]
            removed = 0
            for i in range(len(order["items"]) - 1, -1, -1):
                if removed >= count:
                    break
                if self._line_key(order["items"][i]) == key:
                    del order["items"][i]
                    removed += 1
            self._save_state()
            line = lines[line_index]
        self._audit("ELIMINAR", table_name, f"{line['dish']} ({line['variant']}) x{removed}")
        self._notify("items_removed", table_name, count=removed)
        return removed

    def move_line_to_plate(self, table_name: str, line_index: int, plate: int,
                           count: Optional[int] = None) -> Tuple[int, int]:
        """
        Mueve unidades de una linea a otro plato (p. ej. 2 de los 5 tacos al Plato 2).
        Devuelve (unidades movidas, cuantas de ellas ya habian salido en una comanda).
        """
        plate = self._parse_plate(plate)
        with self._lock:
            order = self._get(table_name)
            self._ensure_open(order)
            lines = self._group_lines(order["items"])
            if not 0 <= line_index < len(lines):
                return 0, 0
            line = lines[line_index]
            if plate and not self.plate_applies(line["dish"]):
                raise ValueError(f"{line['dish']} no se reparte en platos (solo los tacos)")
            if line["plate"] == plate:
                return 0, 0
            count = line["qty"] if count is None else max(0, min(int(count), line["qty"]))
            matching = [i for i in order["items"] if self._line_key(i) == line["key"]]
            # Primero las unidades que cocina todavia no recibio
            matching.sort(key=lambda i: bool(i.get("kitchen_sent")))
            moved = matching[:count]
            for item in moved:
                item["plate"] = plate
            already_sent = sum(1 for i in moved if i.get("kitchen_sent"))
            if moved:
                self._save_state()
        if moved:
            self._audit("PLATO", table_name,
                        f"{line['dish']} ({line['variant']}) x{len(moved)} "
                        f"{plate_label(line['plate'])} -> {plate_label(plate)}")
            self._notify("updated", table_name)
        return len(moved), already_sent

    def used_plates(self, table_name: str) -> List[int]:
        with self._lock:
            order = self._orders.get(table_name)
            return sorted({i.get("plate", 0) for i in order["items"]} - {0}) if order else []

    @staticmethod
    def _line_key(item: Dict) -> Tuple:
        return item["dish"], item["variant"], item.get("note", ""), item["price"], item.get("plate", 0)

    @classmethod
    def _group_lines(cls, items: List[Dict]) -> List[Dict]:
        lines: "OrderedDict[Tuple, Dict]" = OrderedDict()
        for item in items:
            key = cls._line_key(item)
            line = lines.get(key)
            if line is None:
                line = lines[key] = {
                    "key": key,
                    "category": item.get("category", ""),
                    "dish": item["dish"],
                    "variant": item["variant"],
                    "note": item.get("note", ""),
                    "plate": item.get("plate", 0),
                    "unit_price": item["price"],
                    "qty": 0,
                    "subtotal": 0.0,
                    "pending_kitchen": 0,
                }
            line["qty"] += 1
            line["subtotal"] = round(line["subtotal"] + item["price"], 2)
            if not item.get("kitchen_sent"):
                line["pending_kitchen"] += 1
        return list(lines.values())

    def _line_at(self, order: Dict, line_index: int) -> Optional[Dict]:
        lines = self._group_lines(order["items"])
        return lines[line_index] if 0 <= line_index < len(lines) else None

    def add_to_line(self, table_name: str, line_index: int, count: int = 1,
                    source: str = "caja") -> int:
        """Suma unidades iguales a una linea (mismo precio, nota y plato)."""
        with self._lock:
            line = self._line_at(self._get(table_name), line_index)
        if line is None:
            return 0
        return self.add_items(table_name, [{
            "category": line["category"], "dish": line["dish"], "variant": line["variant"],
            "price": line["unit_price"], "note": line["note"], "qty": count, "plate": line["plate"],
        }], source=source)

    def set_line_note(self, table_name: str, line_index: int, note: str) -> Tuple[int, int]:
        """Cambia la nota de una linea. Devuelve (unidades, cuantas ya salieron en comanda)."""
        note = self._clean(note)[:MAX_NOTE_LENGTH]
        with self._lock:
            order = self._get(table_name)
            self._ensure_open(order)
            line = self._line_at(order, line_index)
            if line is None or line["note"] == note:
                return 0, 0
            changed = [i for i in order["items"] if self._line_key(i) == line["key"]]
            for item in changed:
                item["note"] = note
            already_sent = sum(1 for i in changed if i.get("kitchen_sent"))
            self._save_state()
        self._audit("NOTA", table_name, f"{line['dish']} ({line['variant']}) nota={note or '-'}")
        self._notify("updated", table_name)
        return len(changed), already_sent

    def remove_paid_orders(self) -> int:
        """Quita de la lista los pedidos ya cobrados (siguen en el Excel del dia)."""
        with self._lock:
            paid = [name for name, order in self._orders.items() if order["paid"]]
            for name in paid:
                del self._orders[name]
            if self.current_table in paid:
                self.current_table = None
            if paid:
                self._save_state()
        if paid:
            self._audit("LIMPIAR", "-", f"{len(paid)} pedidos pagados: {', '.join(paid)}")
            self._notify("deleted", "")
        return len(paid)

    def get_order_lines(self, table_name: str, kitchen_pending_only: bool = False) -> List[Dict]:
        with self._lock:
            order = self._orders.get(table_name)
            items = order["items"] if order else []
            if kitchen_pending_only:
                items = [i for i in items if not i.get("kitchen_sent")]
            lines = self._group_lines(items)
        for line in lines:
            line.pop("key")
        return lines

    def kitchen_pending_count(self, table_name: str) -> int:
        with self._lock:
            order = self._orders.get(table_name)
            return sum(1 for i in order["items"] if not i.get("kitchen_sent")) if order else 0

    def mark_sent_to_kitchen(self, table_name: str) -> int:
        """Marca como enviados a cocina los items que aun no tenian comanda."""
        with self._lock:
            order = self._get(table_name)
            pending = [i for i in order["items"] if not i.get("kitchen_sent")]
            for item in pending:
                item["kitchen_sent"] = True
            if pending:
                self._save_state()
        if pending:
            self._audit("COMANDA", table_name, f"{len(pending)} items")
            self._notify("updated", table_name)
        return len(pending)

    def get_total(self, table_name: str) -> float:
        with self._lock:
            order = self._orders.get(table_name)
            return round(sum(i["price"] for i in order["items"]), 2) if order else 0.0

    def get_order_summary(self, table_name: str) -> Tuple[Dict[str, int], float]:
        summary = OrderedDict()
        for line in self.get_order_lines(table_name):
            key = f"{line['dish']} ({line['variant']})"
            summary[key] = summary.get(key, 0) + line["qty"]
        return summary, self.get_total(table_name)

    def delete_table(self, table_name: str):
        with self._lock:
            order = self._orders.pop(table_name, None)
            if order is None:
                return
            if self.current_table == table_name:
                self.current_table = None
            self._save_state()
        detail = "pagado" if order["paid"] else f"sin pagar, {len(order['items'])} items"
        self._audit("ELIMINAR_MESA", table_name, detail)
        self._notify("deleted", table_name)

    def rename_table(self, old_name: str, new_name: str) -> bool:
        new_clean = self._clean(new_name)
        with self._lock:
            if old_name not in self._orders or not new_clean:
                return False
            if old_name == new_clean:
                return True
            existing = self.resolve_name(new_clean)
            if existing is not None and existing != old_name:
                return False
            self._orders = OrderedDict(
                (new_clean if k == old_name else k, v) for k, v in self._orders.items()
            )
            self._orders[new_clean]["name"] = new_clean
            if self.current_table == old_name:
                self.current_table = new_clean
            self._save_state()
        self._audit("RENOMBRAR", old_name, f"nuevo={new_clean}")
        self._notify("renamed", new_clean, old_name=old_name)
        return True

    def pending_tables(self) -> List[str]:
        with self._lock:
            return [n for n, o in self._orders.items() if o["items"] and not o["paid"]]

    # -----------------------------------------------
    #  Delivery
    # -----------------------------------------------
    def set_delivery_details(self, table_name: str, moto_cost: float, moto_payment_method: str):
        with self._lock:
            order = self._get(table_name)
            self._ensure_open(order)
            order["delivery"] = {
                "moto_cost": round(float(moto_cost), 2),
                "moto_payment_method": moto_payment_method,
            }
            self._save_state()

    def get_delivery_details(self, table_name: str) -> Optional[Dict]:
        with self._lock:
            order = self._orders.get(table_name)
            return dict(order["delivery"]) if order and order["delivery"] else None

    # -----------------------------------------------
    #  Pagos
    # -----------------------------------------------
    def is_paid(self, table_name: str) -> bool:
        with self._lock:
            order = self._orders.get(table_name)
            return bool(order and order["paid"])

    def get_payment_status(self, table_name: str) -> Tuple[bool, str]:
        with self._lock:
            order = self._orders.get(table_name)
            if not order or not order["paid"]:
                return False, ""
            return True, order["payment"]["method"]

    def get_payment_details(self, table_name: str) -> Optional[Dict]:
        with self._lock:
            order = self._orders.get(table_name)
            return dict(order["payment"]) if order and order["payment"] else None

    def register_payment(self, table_name: str, method: str, cash_amount: float = 0,
                         qr_amount: float = 0, change_method: str = "",
                         expected_total: Optional[float] = None) -> PaymentResult:
        """
        Cobra el pedido: lo registra en el libro de ventas del dia, lo bloquea y
        regenera el Excel. `expected_total` es el total que vio el cajero; si un
        mesero agrego algo mientras tanto se rechaza el cobro.
        """
        if method not in PAYMENT_METHODS:
            raise ValueError(f"Metodo de pago invalido: {method}")
        cash_amount = round(float(cash_amount or 0), 2)
        qr_amount = round(float(qr_amount or 0), 2)
        today = self.today()
        now = _now()

        with self._lock:
            order = self._get(table_name)
            self._ensure_open(order)
            if not order["items"]:
                raise ValueError("El pedido esta vacio")
            total = round(sum(i["price"] for i in order["items"]), 2)
            if expected_total is not None and abs(total - float(expected_total)) > 0.005:
                raise OrderChangedError(total)
            received = round(cash_amount + qr_amount, 2)
            if received < total - 0.005:
                raise ValueError(f"Monto insuficiente: faltan Bs {total - received:.2f}")
            change = round(received - total, 2)
            if change <= 0:
                change, change_method = 0.0, ""
            elif change_method not in ("Efectivo", "QR"):
                change_method = "Efectivo"

            payment = {
                "method": method,
                "cash_amount": cash_amount,
                "qr_amount": qr_amount,
                "amount_paid": received,
                "change": change,
                "change_method": change_method,
                "total": total,
            }
            is_takeaway = order["order_type"] == ORDER_TYPE_TAKEAWAY
            delivery = order["delivery"] if is_takeaway else None
            sale = {
                "date": today.isoformat(),
                "time": now.strftime("%H:%M:%S"),
                "number": order["number"],
                "table": table_name,
                "order_type": order["order_type"],
                "items": [
                    {k: v for k, v in line.items() if k != "key"}
                    for line in self._group_lines(order["items"])
                ],
                **payment,
                "moto_cost": delivery["moto_cost"] if delivery else None,
                "moto_payment_method": delivery["moto_payment_method"] if delivery else "",
            }
            # Primero el registro: si falla, el pedido sigue abierto y nada se pierde
            reports.append_sale(self.root, today, sale)
            order["paid"] = True
            order["paid_date"] = today.isoformat()
            order["paid_at"] = now.isoformat(timespec="seconds")
            order["payment"] = payment
            self._save_state()

        self._audit("PAGAR", table_name, f"num={order['number']} metodo={method} total=Bs{total:.2f}")
        ok, message = self.refresh_daily_excel()
        if not ok:
            self._audit("ERROR_EXCEL", table_name, message)
        self._notify("paid", table_name)
        return PaymentResult(ok, message)

    # -----------------------------------------------
    #  Reportes
    # -----------------------------------------------
    def refresh_daily_excel(self, date: Optional[datetime.date] = None) -> Tuple[bool, str]:
        with self._excel_lock:
            return reports.write_daily_excel(self.root, date or self.today())

    def daily_excel_path(self, date: Optional[datetime.date] = None) -> str:
        return reports.excel_path(self.root, date or self.today())

    def day_summary(self, date: Optional[datetime.date] = None) -> Dict:
        return reports.summarize(reports.read_sales(self.root, date or self.today()))

    def export_snapshot(self, path: str) -> Tuple[bool, str]:
        with self._lock:
            records = []
            for name, order in self._orders.items():
                lines = [{k: v for k, v in l.items() if k != "key"}
                         for l in self._group_lines(order["items"])]
                payment = order["payment"] or {}
                delivery = order["delivery"] or {}
                stamp = order.get("paid_at") or order.get("created_at") or ""
                records.append({
                    "number": order["number"],
                    "table": name,
                    "order_type": order["order_type"],
                    "items": lines,
                    "total": round(sum(i["price"] for i in order["items"]), 2),
                    "paid": order["paid"],
                    "time": stamp[11:19],
                    **payment,
                    "moto_cost": delivery.get("moto_cost"),
                    "moto_payment_method": delivery.get("moto_payment_method", ""),
                })
        with self._excel_lock:
            return reports.write_orders_snapshot(path, records)
