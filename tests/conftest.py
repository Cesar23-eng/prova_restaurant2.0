import datetime
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture
def data_dir(tmp_path, monkeypatch):
    path = tmp_path / "data"
    path.mkdir()
    monkeypatch.setenv("PROVA_DATA_DIR", str(path))
    return str(path)


@pytest.fixture
def frozen_now(monkeypatch):
    """Permite fijar la hora que ve OrderManager."""
    from models import order as order_module

    state = {"now": datetime.datetime(2026, 9, 14, 13, 0, 0)}
    monkeypatch.setattr(order_module, "_now", lambda: state["now"])

    def set_now(value: datetime.datetime):
        state["now"] = value

    return set_now


@pytest.fixture
def manager(data_dir, frozen_now):
    from models.order import OrderManager

    return OrderManager(root=data_dir, cutoff_hour=4)


@pytest.fixture
def menu_file(tmp_path):
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.append(["categoria", "producto", "variante", "precio"])
    ws.append(["Platillos", "Taco", "Carne", 15])
    ws.append(["Platillos", "Taco", "Pastor", 15])
    ws.append(["Platillos", "Quesadilla", "Pollo", 35])
    ws.append(["Bebidas", "Coca cola", "Botella", 10])
    ws.append(["Extras", "Guacamole", None, 22])
    path = tmp_path / "menu_precios.xlsx"
    wb.save(path)
    return str(path)
