import os
import time

from openpyxl import load_workbook

from models.menu import DEFAULT_VARIANT, MenuData


def test_reads_menu_and_defaults_missing_variant(menu_file):
    menu = MenuData(menu_file).get_menu_prices()
    assert list(menu) == ["Platillos", "Bebidas", "Extras"]
    assert menu["Platillos"]["Taco"] == {"Carne": 15.0, "Pastor": 15.0}
    assert menu["Extras"]["Guacamole"] == {DEFAULT_VARIANT: 22.0}


def test_reloads_when_file_changes(menu_file):
    data = MenuData(menu_file)
    assert data.get_price("Platillos", "Taco", "Carne") == 15.0
    wb = load_workbook(menu_file)
    wb.active["D2"] = 18
    wb.save(menu_file)
    future = time.time() + 5
    os.utime(menu_file, (future, future))
    assert data.get_price("Platillos", "Taco", "Carne") == 18.0


def test_missing_file_returns_empty_menu_with_error(tmp_path):
    data = MenuData(str(tmp_path / "no_existe.xlsx"))
    assert data.get_menu_prices() == {}
    assert "No se encontro" in data.last_error


def test_project_menu_loads():
    menu = MenuData().get_menu_prices()
    assert "Platillos" in menu and menu["Platillos"]["Taco"]["Carne"] == 15.0
