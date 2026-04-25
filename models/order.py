# models/order.py
from collections import defaultdict
from typing import Dict, List, Tuple, Any, Optional


class OrderManager:
    def __init__(self):
        self.table_orders = defaultdict(list)
        self.payment_status = {}
        self.payment_details = {}      # Detalles completos del pago
        self.delivery_details = {}     # Detalles de delivery por mesa
        self.current_table = None
        self.order_type = "En el local"   # "En el local" | "Para llevar"

    # -----------------------------------------------
    #  Utilidades de nombre
    # -----------------------------------------------
    @staticmethod
    def _norm(name: str) -> str:
        return " ".join(name.split()).strip().lower()

    def name_exists(self, name: str) -> bool:
        n = self._norm(name)
        return any(self._norm(k) == n for k in self.table_orders.keys())

    def suggest_name(self, base: str) -> str:
        base = " ".join(base.split()).strip()
        if not self.name_exists(base):
            return base
        i = 2
        while True:
            candidate = f"{base} {i}"
            if not self.name_exists(candidate):
                return candidate
            i += 1

    # -----------------------------------------------
    #  Gestion de mesas / ordenes
    # -----------------------------------------------
    def create_table(self, name: str) -> Tuple[bool, str]:
        base = " ".join((name or "").split()).strip()
        if not base:
            return False, "Nombre invalido"
        if self.name_exists(base):
            return False, self.suggest_name(base)
        self.table_orders[base] = []
        self.payment_status.pop(base, None)
        self.payment_details.pop(base, None)
        self.delivery_details.pop(base, None)
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

    def get_order_summary(self, table_name: str) -> Tuple[Dict[str, int], float]:
        order_summary = defaultdict(int)
        total = 0.0
        for item in self.table_orders.get(table_name, []):
            key = f"{item['dish']} ({item['variant']})"
            order_summary[key] += 1
            total += item["price"]
        return order_summary, total

    def delete_table(self, table_name: str):
        self.table_orders.pop(table_name, None)
        self.payment_status.pop(table_name, None)
        self.payment_details.pop(table_name, None)
        self.delivery_details.pop(table_name, None)
        if self.current_table == table_name:
            self.current_table = None

    def rename_table(self, old_name: str, new_name: str) -> bool:
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
            if old_name in self.delivery_details:
                self.delivery_details[new_clean] = self.delivery_details.pop(old_name)
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
        if old_name in self.delivery_details:
            self.delivery_details[new_clean] = self.delivery_details.pop(old_name)
        if self.current_table == old_name:
            self.current_table = new_clean
        return True

    def get_all_tables(self) -> List[str]:
        return list(self.table_orders.keys())

    def clear_order(self, table_name: str):
        if table_name in self.table_orders:
            self.table_orders[table_name] = []

    def set_order_type(self, order_type: str):
        self.order_type = order_type

    # -----------------------------------------------
    #  Pagos  (req. 1 y 4)
    #  payment_details estructura:
    #  {
    #    'method':        'Efectivo' | 'QR' | 'Mixto',
    #    'cash_amount':   float,   # monto pagado en efectivo
    #    'qr_amount':     float,   # monto pagado en QR
    #    'amount_paid':   float,   # total recibido
    #    'change':        float,   # cambio devuelto
    #    'change_method': 'Efectivo' | 'QR' | '',
    #    'total':         float,
    #  }
    # -----------------------------------------------
    def set_payment_status(
        self,
        table_name: str,
        paid: bool,
        method: str = "",
        amount_paid: float = 0,
        change: float = 0,
        cash_amount: float = 0,
        qr_amount: float = 0,
        change_method: str = "",
    ):
        """Registra pago con soporte para mixtos y cambio en QR/efectivo."""
        self.payment_status[table_name] = (paid, method)
        if paid:
            _, total = self.get_order_summary(table_name)
            self.payment_details[table_name] = {
                "method": method,
                "cash_amount": cash_amount,
                "qr_amount": qr_amount,
                "amount_paid": amount_paid,
                "change": change,
                "change_method": change_method,
                "total": total,
            }

    def get_payment_status(self, table_name: str) -> Tuple[bool, str]:
        return self.payment_status.get(table_name, (False, ""))

    def get_payment_details(self, table_name: str) -> Optional[Dict]:
        return self.payment_details.get(table_name)

    # -----------------------------------------------
    #  Delivery  (req. 2)
    #  delivery_details estructura por mesa:
    #  { 'moto_cost': float, 'moto_payment_method': 'Efectivo' | 'QR' }
    # -----------------------------------------------
    def set_delivery_details(self, table_name: str, moto_cost: float, moto_payment_method: str):
        """Registra costo de la moto y metodo de pago para pedidos delivery."""
        self.delivery_details[table_name] = {
            "moto_cost": moto_cost,
            "moto_payment_method": moto_payment_method,
        }

    def get_delivery_details(self, table_name: str) -> Optional[Dict]:
        return self.delivery_details.get(table_name)

    # -----------------------------------------------
    #  Excel  (req. 3)
    #  Hoja "En el local"  -> pedidos de mesa
    #  Hoja "Para llevar"  -> pedidos delivery
    # -----------------------------------------------
    def save_all_to_excel(self, filepath: str = "pedidos.xlsx"):
        """
        Guarda todos los pedidos en pedidos.xlsx con dos hojas separadas.
        Sobreescribe el archivo completo cada vez.
        """
        from openpyxl import Workbook
        from openpyxl.styles import Font, PatternFill, Alignment
        from openpyxl.utils import get_column_letter
        from collections import Counter

        wb = Workbook()

        # Hoja 1: En el local
        ws_local = wb.active
        ws_local.title = "En el local"
        headers_local = [
            "Mesa/Cliente", "Platillos", "Total (Bs)",
            "Metodo de Pago", "Efectivo recibido (Bs)", "Monto QR (Bs)",
            "Cambio (Bs)", "Cambio dado en", "Pagado"
        ]

        # Hoja 2: Para llevar
        ws_delivery = wb.create_sheet("Para llevar")
        headers_delivery = [
            "Mesa/Cliente", "Platillos", "Total (Bs)",
            "Metodo de Pago", "Efectivo recibido (Bs)", "Monto QR (Bs)",
            "Cambio (Bs)", "Cambio dado en",
            "Costo Moto (Bs)", "Pago Moto (metodo)", "Pagado"
        ]

        def style_header_row(ws, headers):
            ws.append(headers)
            for col, _ in enumerate(headers, 1):
                cell = ws.cell(1, col)
                cell.font = Font(bold=True, color="FFFFFF")
                cell.fill = PatternFill("solid", fgColor="1A5276")
                cell.alignment = Alignment(horizontal="center")

        style_header_row(ws_local, headers_local)
        style_header_row(ws_delivery, headers_delivery)

        for mesa, items in self.table_orders.items():
            if not items:
                continue

            total = sum(i["price"] for i in items)
            paid_status = self.get_payment_status(mesa)
            details = self.get_payment_details(mesa) or {}
            delivery = self.get_delivery_details(mesa) or {}

            summary = Counter(f"{i['dish']} ({i['variant']})" for i in items)
            platillos_str = "; ".join(f"{k} x{v}" for k, v in summary.items())

            is_delivery = bool(delivery)

            if is_delivery:
                ws_delivery.append([
                    mesa,
                    platillos_str,
                    round(total, 2),
                    details.get("method", ""),
                    details.get("cash_amount") or "",
                    details.get("qr_amount") or "",
                    details.get("change") or "",
                    details.get("change_method", ""),
                    delivery.get("moto_cost", ""),
                    delivery.get("moto_payment_method", ""),
                    "Si" if paid_status[0] else "No",
                ])
            else:
                ws_local.append([
                    mesa,
                    platillos_str,
                    round(total, 2),
                    details.get("method", ""),
                    details.get("cash_amount") or "",
                    details.get("qr_amount") or "",
                    details.get("change") or "",
                    details.get("change_method", ""),
                    "Si" if paid_status[0] else "No",
                ])

        # Auto-ajustar anchos de columnas
        for ws in [ws_local, ws_delivery]:
            for col in ws.columns:
                max_len = max((len(str(c.value or "")) for c in col), default=0)
                ws.column_dimensions[get_column_letter(col[0].column)].width = min(max_len + 4, 60)

        wb.save(filepath)
