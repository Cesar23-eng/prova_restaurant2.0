# models/inventory.py
"""
Inventario nivel 1: productos agotados.

La caja marca, por ejemplo, "Fanta papaya: agotada" y desde ese momento ni la
caja ni los celulares de los meseros la dejan pedir, hasta marcarla disponible.
Asi un pedido con una soda que no hay no llega a cocina.

Se guarda en data/inventario.json y no se reinicia cada dia: si hoy se acabo,
manana sigue agotada hasta que llegue y se marque disponible.
"""
import datetime
import json
import os
import threading
from typing import Callable, Dict, List, Optional

from utils.config import atomic_write_text

FILENAME = "inventario.json"


def _norm(text: str) -> str:
    return " ".join(str(text or "").split()).lower()


def item_key(category: str, dish: str, variant: str) -> str:
    return "|".join(_norm(part) for part in (category, dish, variant))


class UnavailableError(ValueError):
    """Se intento pedir productos agotados. `items` trae (categoria, platillo, variante)."""

    def __init__(self, items: List[tuple]):
        names = ", ".join(f"{dish} ({variant})" for _category, dish, variant in items)
        super().__init__(f"Se acabó: {names}")
        self.items = items


class Inventory:
    def __init__(self, root: str, audit: Optional[Callable] = None, notify: Optional[Callable] = None):
        self.path = os.path.join(root, FILENAME)
        self._audit = audit or (lambda *args: None)
        self._notify = notify or (lambda *args, **kwargs: None)
        self._lock = threading.Lock()
        self._unavailable: Dict[str, Dict] = self._read()

    def _read(self) -> Dict[str, Dict]:
        if not os.path.exists(self.path):
            return {}
        try:
            with open(self.path, encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, ValueError):
            return {}
        return {item_key(e["categoria"], e["platillo"], e["variante"]): e
                for e in data.get("agotados", []) if {"categoria", "platillo", "variante"} <= e.keys()}

    def _save(self):
        data = {"agotados": list(self._unavailable.values())}
        atomic_write_text(self.path, json.dumps(data, ensure_ascii=False, indent=1))

    def is_available(self, category: str, dish: str, variant: str) -> bool:
        with self._lock:
            return item_key(category, dish, variant) not in self._unavailable

    def unavailable(self) -> List[Dict]:
        with self._lock:
            return [dict(e) for e in self._unavailable.values()]

    def set_available(self, category: str, dish: str, variant: str, available: bool,
                      source: str = "caja") -> bool:
        """Devuelve True si cambio algo."""
        key = item_key(category, dish, variant)
        with self._lock:
            if available == (key not in self._unavailable):
                return False
            if available:
                del self._unavailable[key]
            else:
                self._unavailable[key] = {
                    "categoria": category, "platillo": dish, "variante": variant,
                    "desde": datetime.datetime.now().isoformat(timespec="seconds"),
                }
            self._save()
        self._audit("DISPONIBLE" if available else "AGOTADO", "-", f"{dish} ({variant}) origen={source}")
        self._notify("inventory")
        return True

    def mark_all_available(self, source: str = "caja") -> int:
        with self._lock:
            count = len(self._unavailable)
            if not count:
                return 0
            self._unavailable = {}
            self._save()
        self._audit("DISPONIBLE", "-", f"todos ({count}) origen={source}")
        self._notify("inventory")
        return count
