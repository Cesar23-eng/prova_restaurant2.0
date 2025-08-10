# models/order.py (solo en memoria)
from collections import defaultdict
from typing import Dict, List, Tuple, Any

class OrderManager:
    def __init__(self):
        self.table_orders = defaultdict(list)
        self.payment_status = {}
        self.current_table = None
        self.order_type = "Mesa"

    # --- NUEVO: normalizador y validaciones ---
    @staticmethod
    def _norm(name: str) -> str:
        # quita dobles espacios, bordes y hace case-insensitive
        return " ".join(name.split()).strip().lower()

    def name_exists(self, name: str) -> bool:
        n = self._norm(name)
        return any(self._norm(k) == n for k in self.table_orders.keys())

    def suggest_name(self, base: str) -> str:
        base = " ".join(base.split()).strip()
        # si base está libre, úsalo
        if not self.name_exists(base):
            return base
        i = 2
        while True:
            candidate = f"{base} {i}"
            if not self.name_exists(candidate):
                return candidate
            i += 1
    # --- FIN NUEVO ---
    from typing import Tuple  # ya lo tienes importado arriba

    def create_table(self, name: str) -> Tuple[bool, str]:
        """
        Devuelve (True, nombre_creado) si se creó.
        Si falla: (False, 'Nombre inválido' o sugerencia).
        """
        base = " ".join((name or "").split()).strip()
        if not base:
            return False, "Nombre inválido"

        if self.name_exists(base):
            return False, self.suggest_name(base)

        self.table_orders[base] = []
        self.payment_status.pop(base, None)  # limpia cualquier estado viejo
        return True, base

    def set_current_table(self, table_name: str):
        self.current_table = table_name

    def add_item_to_order(self, category, dish, variant, price):
        if not self.current_table:
            raise ValueError("No hay mesa seleccionada")
        self.table_orders[self.current_table].append(
            {"category": category, "dish": dish, "variant": variant, "price": price}
        )

    def remove_item_from_order(self, table_name: str, index: int) -> bool:
        if table_name in self.table_orders and 0 <= index < len(self.table_orders[table_name]):
            del self.table_orders[table_name][index]
            return True
        return False

    def get_order_summary(self, table_name: str):
        from collections import defaultdict
        order_summary = defaultdict(int)
        total = 0.0
        for item in self.table_orders.get(table_name, []):
            key = f"{item['dish']} ({item['variant']})"
            order_summary[key] += 1
            total += item['price']
        return order_summary, total

    def set_payment_status(self, table_name: str, paid: bool, method: str = ""):
        self.payment_status[table_name] = (paid, method)

    def get_payment_status(self, table_name: str):
        return self.payment_status.get(table_name, (False, ""))

    def delete_table(self, table_name: str):
        self.table_orders.pop(table_name, None)
        self.payment_status.pop(table_name, None)
        if self.current_table == table_name:
            self.current_table = None

    def rename_table(self, old_name: str, new_name: str) -> bool:
        """
        Renombra evitando colisiones (case/espacios incluidos).
        """
        if old_name not in self.table_orders:
            return False

        new_clean = " ".join((new_name or "").split()).strip()
        if not new_clean:
            return False

        # Si normalizado es el mismo, permite (solo cambia casing/espacios)
        if self._norm(old_name) == self._norm(new_clean):
            if old_name == new_clean:
                return True  # nada que hacer
            self.table_orders[new_clean] = self.table_orders.pop(old_name)
            if old_name in self.payment_status:
                self.payment_status[new_clean] = self.payment_status.pop(old_name)
            if self.current_table == old_name:
                self.current_table = new_clean
            return True

        # Si colisiona con otra mesa existente, niega
        if self.name_exists(new_clean):
            return False

        # Renombrar efectivo
        self.table_orders[new_clean] = self.table_orders.pop(old_name)
        if old_name in self.payment_status:
            self.payment_status[new_clean] = self.payment_status.pop(old_name)
        if self.current_table == old_name:
            self.current_table = new_clean
        return True

    def set_order_type(self, order_type: str):
        self.order_type = order_type
