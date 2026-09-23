# models/cash.py
"""
Caja de cada jornada: apertura (efectivo, QR y fondo para imprevistos), gastos
que salen de la caja durante el dia y arqueo (efectivo contado) al cierre.

Se guarda en data/AAAA-MM-DD/caja_AAAA-MM-DD.json, aparte del registro de
ventas: si un dia no se abre caja, el cierre funciona igual que antes.
"""
import datetime
import json
import os
import threading
import uuid
from typing import Callable, Dict, Optional

from utils.config import atomic_write_text, day_dir

EXPENSE_METHODS = ("Efectivo", "QR")
MAX_REASON_LENGTH = 80
MAX_TEXT_LENGTH = 120


def _now() -> datetime.datetime:
    return datetime.datetime.now()


def _clean(text: str, limit: int) -> str:
    return " ".join(str(text or "").split())[:limit]


def _amount(value) -> float:
    try:
        amount = round(float(str(value).replace(",", ".") if value not in (None, "") else 0), 2)
    except (TypeError, ValueError):
        raise ValueError(f"Monto inválido: {value}")
    if amount < 0:
        raise ValueError("El monto no puede ser negativo")
    return amount


def empty_state() -> Dict:
    return {"opening": None, "expenses": [], "count": None}


class CashRegister:
    def __init__(self, root: str, today: Callable[[], datetime.date],
                 audit: Optional[Callable] = None, notify: Optional[Callable] = None):
        self.root = root
        self._today = today
        self._audit = audit or (lambda *args: None)
        self._notify = notify or (lambda *args, **kwargs: None)
        self._lock = threading.Lock()

    def path(self, date: Optional[datetime.date] = None) -> str:
        date = date or self._today()
        return os.path.join(day_dir(self.root, date), f"caja_{date:%Y-%m-%d}.json")

    def load(self, date: Optional[datetime.date] = None) -> Dict:
        path = self.path(date)
        state = empty_state()
        if not os.path.exists(path):
            return state
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, ValueError):
            return state
        for key in state:
            if key in data:
                state[key] = data[key]
        return state

    def _save(self, state: Dict, date: Optional[datetime.date] = None):
        atomic_write_text(self.path(date), json.dumps(state, ensure_ascii=False, indent=1))

    def is_open(self, date: Optional[datetime.date] = None) -> bool:
        return self.load(date)["opening"] is not None

    def open(self, cash, qr=0, reserve=0, cashier: str = "", note: str = "",
             date: Optional[datetime.date] = None) -> Dict:
        """Abre la caja o corrige la apertura (queda registrado en la auditoria)."""
        stamp = _now().strftime("%H:%M:%S")
        opening = {
            "cash": _amount(cash),
            "qr": _amount(qr),
            "reserve": _amount(reserve),
            "cashier": _clean(cashier, 40),
            "note": _clean(note, MAX_TEXT_LENGTH),
            "time": stamp,
        }
        with self._lock:
            state = self.load(date)
            corrected = state["opening"] is not None
            if corrected:
                opening["time"] = state["opening"].get("time", stamp)
                opening["corrected_at"] = stamp
            state["opening"] = opening
            self._save(state, date)
        detail = (f"efectivo=Bs{opening['cash']:.2f} qr=Bs{opening['qr']:.2f} "
                  f"imprevistos=Bs{opening['reserve']:.2f}")
        if opening["cashier"]:
            detail += f" cajero={opening['cashier']}"
        self._audit("CAJA_CORRIGE" if corrected else "CAJA_ABRE", "-", detail)
        self._notify("cash")
        return opening

    def add_expense(self, amount, method: str = "Efectivo", reason: str = "", source: str = "caja",
                    date: Optional[datetime.date] = None) -> Dict:
        amount = _amount(amount)
        if amount <= 0:
            raise ValueError("Ingresa el monto del gasto")
        if method not in EXPENSE_METHODS:
            raise ValueError(f"Medio de pago inválido: {method}")
        reason = _clean(reason, MAX_REASON_LENGTH)
        if not reason:
            raise ValueError("Escribe el motivo del gasto")
        expense = {
            "id": uuid.uuid4().hex[:8],
            "amount": amount,
            "method": method,
            "reason": reason,
            "time": _now().strftime("%H:%M:%S"),
            "source": source,
            "voided": False,
        }
        with self._lock:
            state = self.load(date)
            state["expenses"].append(expense)
            self._save(state, date)
        self._audit("GASTO", "-", f"Bs{amount:.2f} {method} motivo={reason}")
        self._notify("cash")
        return expense

    def void_expense(self, expense_id: str, date: Optional[datetime.date] = None) -> bool:
        with self._lock:
            state = self.load(date)
            expense = next((e for e in state["expenses"] if e["id"] == expense_id), None)
            if expense is None or expense.get("voided"):
                return False
            expense["voided"] = True
            expense["voided_at"] = _now().strftime("%H:%M:%S")
            self._save(state, date)
        self._audit("GASTO_ANULA", "-", f"Bs{expense['amount']:.2f} motivo={expense['reason']}")
        self._notify("cash")
        return True

    def set_count(self, counted_cash, note: str = "", date: Optional[datetime.date] = None) -> Dict:
        """Arqueo: efectivo que el cajero conto en la caja al cerrar."""
        count = {
            "cash": _amount(counted_cash),
            "note": _clean(note, MAX_TEXT_LENGTH),
            "time": _now().strftime("%H:%M:%S"),
        }
        with self._lock:
            state = self.load(date)
            state["count"] = count
            self._save(state, date)
        self._audit("ARQUEO", "-", f"contado=Bs{count['cash']:.2f}")
        self._notify("cash")
        return count


def cash_summary(state: Dict, sales: Dict, motos_from_drawer: bool = True) -> Dict:
    """
    Lo que deberia haber al cerrar:
      efectivo = efectivo inicial + fondo de imprevistos + ventas en efectivo (ya
                 descontado el cambio) - gastos en efectivo - motos pagadas en efectivo
      QR       = QR inicial + ventas por QR - gastos por QR - motos pagadas por QR
    Las motos se descuentan porque el local les paga de la caja
    (config "motos_salen_de_caja"). Con arqueo, diferencia = contado - esperado.
    """
    opening = state.get("opening") or {}
    expenses = [e for e in state.get("expenses", []) if not e.get("voided")]
    cash_start = float(opening.get("cash", 0) or 0)
    qr_start = float(opening.get("qr", 0) or 0)
    reserve = float(opening.get("reserve", 0) or 0)
    expenses_cash = round(sum(e["amount"] for e in expenses if e["method"] == "Efectivo"), 2)
    expenses_qr = round(sum(e["amount"] for e in expenses if e["method"] == "QR"), 2)
    moto_cash = float(sales.get("moto_cash", 0) or 0) if motos_from_drawer else 0.0
    moto_qr = float(sales.get("moto_qr", 0) or 0) if motos_from_drawer else 0.0
    expected_cash = round(cash_start + reserve + sales.get("cash_net", 0) - expenses_cash - moto_cash, 2)
    expected_qr = round(qr_start + sales.get("qr_net", 0) - expenses_qr - moto_qr, 2)
    count = state.get("count")
    counted = float(count["cash"]) if count else None
    return {
        "opened": bool(state.get("opening")),
        "opening_time": opening.get("time", ""),
        "cashier": opening.get("cashier", ""),
        "cash_start": round(cash_start, 2),
        "qr_start": round(qr_start, 2),
        "reserve": round(reserve, 2),
        "reserve_left": round(reserve - expenses_cash - expenses_qr, 2),
        "expenses": expenses,
        "expenses_cash": expenses_cash,
        "expenses_qr": expenses_qr,
        "moto_cash_from_drawer": round(moto_cash, 2),
        "moto_qr_from_drawer": round(moto_qr, 2),
        "expected_cash": expected_cash,
        "expected_qr": expected_qr,
        "counted_cash": counted,
        "count_time": count.get("time", "") if count else "",
        "difference": round(counted - expected_cash, 2) if counted is not None else None,
    }
