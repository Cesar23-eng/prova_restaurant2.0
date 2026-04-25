import pandas as pd
from typing import Dict, Any
import sys
import os


class MenuData:
    @staticmethod
    def resource_path(relative_path: str) -> str:
        """
        Obtiene la ruta correcta del recurso.
        Busca JUNTO AL EXE, no dentro del bundle.
        """
        # Obtener directorio donde está el ejecutable
        if getattr(sys, 'frozen', False):
            # Si es ejecutable, usar directorio del .exe
            base_path = os.path.dirname(sys.executable)
        else:
            # Si es script Python, usar directorio del script
            base_path = os.path.dirname(os.path.abspath(__file__))

        return os.path.join(base_path, relative_path)

    @staticmethod
    def get_menu_prices() -> Dict[str, Any]:
        try:
            excel_path = MenuData.resource_path("menu_precios.xlsx")

            if not os.path.exists(excel_path):
                print(f"❌ Falta el archivo Excel: {excel_path}")
                print(f"📁 Coloca menu_precios.xlsx junto al ejecutable")
                return {}

            df = pd.read_excel(excel_path, engine="openpyxl")

            menu = {}
            for _, row in df.iterrows():
                categoria = str(row.get("categoria", "")).strip()
                producto = str(row.get("producto", "")).strip()
                variante = str(row.get("variante", "")).strip()

                try:
                    precio = float(row.get("precio", 0))
                except (ValueError, TypeError):
                    precio = 0.0

                if not categoria or not producto or not variante:
                    continue

                menu.setdefault(categoria, {})
                menu[categoria].setdefault(producto, {})
                menu[categoria][producto][variante] = precio

            return menu

        except Exception as e:
            print(f"❌ Error leyendo Excel: {e}")
            return {}
