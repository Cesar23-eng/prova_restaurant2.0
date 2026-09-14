# utils/config.py
"""
Rutas de la aplicacion, configuracion persistente y jornada de trabajo.

- app_dir(): carpeta junto al .exe (o raiz del proyecto en desarrollo).
  Ahi viven los archivos que el dueño edita: menu_precios.xlsx, prova.png.
- resource_dir(): recursos empaquetados dentro del .exe (templates/).
- data_root(): carpeta data/ donde se guardan ventas, auditoria y estado.
"""
import datetime
import json
import os
import secrets
import sys
import threading
import time

DEFAULT_CONFIG = {
    "nombre_local": "PROVA - Comida Mexicana",
    "puerto_meseros": 5000,
    # Los pedidos entre medianoche y esta hora cuentan para el dia anterior
    # (un local que cierra a la 1am no parte sus ventas en dos archivos).
    "hora_corte_jornada": 4,
    "tema": "light",
}

_config_lock = threading.Lock()


def app_dir() -> str:
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def resource_dir() -> str:
    return getattr(sys, "_MEIPASS", app_dir())


def data_root() -> str:
    path = os.environ.get("PROVA_DATA_DIR") or os.path.join(app_dir(), "data")
    os.makedirs(path, exist_ok=True)
    return path


def business_date(now: datetime.datetime = None, cutoff_hour: int = None) -> datetime.date:
    """Fecha de la jornada: antes de la hora de corte cuenta como el dia anterior."""
    now = now or datetime.datetime.now()
    if cutoff_hour is None:
        cutoff_hour = int(load_config().get("hora_corte_jornada", 4))
    return (now - datetime.timedelta(hours=cutoff_hour)).date()


def day_dir(root: str, date: datetime.date) -> str:
    path = os.path.join(root, date.strftime("%Y-%m-%d"))
    os.makedirs(path, exist_ok=True)
    return path


def atomic_write_text(path: str, text: str, retries: int = 5):
    """
    Escribe a un temporal y lo reemplaza de golpe: si la PC se apaga a mitad
    de escritura el archivo anterior queda intacto. Reintenta porque OneDrive
    y los antivirus bloquean archivos por instantes en Windows.
    """
    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(text)
        f.flush()
        os.fsync(f.fileno())
    for attempt in range(retries):
        try:
            os.replace(tmp, path)
            return
        except PermissionError:
            if attempt == retries - 1:
                raise
            time.sleep(0.1 * (attempt + 1))


def _config_path(root: str = None) -> str:
    return os.path.join(root or data_root(), "config.json")


def load_config(root: str = None) -> dict:
    """Lee data/config.json; lo crea con un PIN aleatorio la primera vez."""
    path = _config_path(root)
    with _config_lock:
        config = dict(DEFAULT_CONFIG)
        stored = {}
        if os.path.exists(path):
            try:
                with open(path, encoding="utf-8") as f:
                    stored = json.load(f)
            except (OSError, ValueError):
                stored = {}
        config.update(stored)
        if not str(config.get("pin_meseros", "")).strip():
            config["pin_meseros"] = f"{secrets.randbelow(10000):04d}"
        if config != stored:
            try:
                atomic_write_text(path, json.dumps(config, indent=2, ensure_ascii=False))
            except OSError:
                pass
        return config


def save_config_value(key: str, value, root: str = None):
    config = load_config(root)
    config[key] = value
    with _config_lock:
        atomic_write_text(_config_path(root), json.dumps(config, indent=2, ensure_ascii=False))
