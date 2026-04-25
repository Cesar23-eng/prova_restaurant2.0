# models/order.py - COMPLETO
from collections import defaultdict
from typing import Dict, List, Tuple, Any, Optional

class OrderManager:
    def __init__(self):
        self.table_orders = defaultdict(list)
        self.payment_status = {}
        self.payment_details = {}  # Almacena detalles del pago
        self.current_table = None
        self.order_type = "Mesa"

    @staticmethod
    def _norm(name: str) -> str:
        """Normaliza nombres: quita dobles espacios, bordes y hace case-insensitive"""
        return " ".join(name.split()).strip().lower()

    def name_exists(self, name: str) -> bool:
        """Verifica si un nombre ya existe (normalizado)"""
        n = self._norm(name)
        return any(self._norm(k) == n for k in self.table_orders.keys())

    def suggest_name(self, base: str) -> str:
        """Sugiere un nombre alternativo si el base está ocupado"""
        base = " ".join(base.split()).strip()
        if not self.name_exists(base):
            return base
        i = 2
        while True:
            candidate = f"{base} {i}"
            if not self.name_exists(candidate):
                return candidate
            i += 1

    def create_table(self, name: str) -> Tuple[bool, str]:
        """Crea una nueva mesa/orden"""
        base = " ".join((name or "").split()).strip()
        if not base:
            return False, "Nombre inválido"

        if self.name_exists(base):
            return False, self.suggest_name(base)

        self.table_orders[base] = []
        self.payment_status.pop(base, None)
        self.payment_details.pop(base, None)
        return True, base

    def set_current_table(self, table_name: str):
        """Establece la mesa actual"""
        self.current_table = table_name

    def add_item_to_order(self, category, dish, variant, price):
        """Agrega un item a la orden actual"""
        if not self.current_table:
            raise ValueError("No hay mesa seleccionada")
        self.table_orders[self.current_table].append(
            {"category": category, "dish": dish, "variant": variant, "price": price}
        )

    def remove_item_from_order(self, table_name: str, index: int) -> bool:
        """Elimina un item de la orden"""
        if table_name in self.table_orders and 0 <= index < len(self.table_orders[table_name]):
            del self.table_orders[table_name][index]
            return True
        return False

    def get_order_summary(self, table_name: str) -> Tuple[Dict[str, int], float]:
        """Obtiene resumen de la orden con totales"""
        from collections import defaultdict
        order_summary = defaultdict(int)
        total = 0.0
        for item in self.table_orders.get(table_name, []):
            key = f"{item['dish']} ({item['variant']})"
            order_summary[key] += 1
            total += item['price']
        return order_summary, total

    def set_payment_status(self, table_name: str, paid: bool, method: str = "",
                          amount_paid: float = 0, change: float = 0):
        """Registra el estado de pago con detalles completos"""
        self.payment_status[table_name] = (paid, method)
        if paid:
            _, total = self.get_order_summary(table_name)
            self.payment_details[table_name] = {
                'method': method,
                'amount_paid': amount_paid,
                'change': change,
                'total': total
            }

    def get_payment_status(self, table_name: str) -> Tuple[bool, str]:
        """Obtiene el estado de pago básico"""
        return self.payment_status.get(table_name, (False, ""))

    def get_payment_details(self, table_name: str) -> Optional[Dict]:
        """Obtiene los detalles completos del pago"""
        return self.payment_details.get(table_name)

    def calculate_change(self, total: float, amount_paid: float) -> float:
        """Calcula el cambio a devolver"""
        return round(amount_paid - total, 2)

    def delete_table(self, table_name: str):
        """Elimina una mesa/orden completamente"""
        self.table_orders.pop(table_name, None)
        self.payment_status.pop(table_name, None)
        self.payment_details.pop(table_name, None)
        if self.current_table == table_name:
            self.current_table = None

    def rename_table(self, old_name: str, new_name: str) -> bool:
        """Renombra una mesa evitando colisiones"""
        if old_name not in self.table_orders:
            return False

        new_clean = " ".join((new_name or "").split()).strip()
        if not new_clean:
            return False

        if self._norm(old_name) == self._norm(new_clean):
            if old_name == new_clean:
                return True
            self.table_orders[new_clean] = self.table_orders.pop(old_name)
            if old_name in self.payment_status:
                self.payment_status[new_clean] = self.payment_status.pop(old_name)
            if old_name in self.payment_details:
                self.payment_details[new_clean] = self.payment_details.pop(old_name)
            if self.current_table == old_name:
                self.current_table = new_clean
            return True

        if self.name_exists(new_clean):
            return False

        self.table_orders[new_clean] = self.table_orders.pop(old_name)
        if old_name in self.payment_status:
            self.payment_status[new_clean] = self.payment_status.pop(old_name)
        if old_name in self.payment_details:
            self.payment_details[new_clean] = self.payment_details.pop(old_name)
        if self.current_table == old_name:
            self.current_table = new_clean
        return True

    def set_order_type(self, order_type: str):
        """Establece el tipo de orden"""
        self.order_type = order_type

    def get_all_tables(self) -> List[str]:
        """Obtiene lista de todas las mesas/órdenes"""
        return list(self.table_orders.keys())

    def clear_order(self, table_name: str):
        """Limpia todos los items de una orden"""
        if table_name in self.table_orders:
            self.table_orders[table_name] = []
