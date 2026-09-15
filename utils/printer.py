# utils/printer.py
"""
Envio de tickets a la impresora.

- Modo "escpos": manda los comandos ESC/POS en crudo (RAW) al spooler de Windows.
  Es lo recomendado para la Epson TM-T20III: letra nativa, sin dialogos, corte
  automatico. No requiere librerias extra (usa winspool.drv con ctypes).
- Modo "windows": dibuja el ticket con Qt, para impresoras que no son termicas.
- Modo "auto": ESC/POS si el nombre parece de una impresora de tickets.
"""
import re
import sys
from typing import List, Optional

from utils import tickets

THERMAL_PATTERN = re.compile(r"TM-|EPSON|RECEIPT|\bPOS\b|T[EÉ]RMIC|THERMAL|\b(80|58)\s?MM", re.IGNORECASE)
PRINT_MODES = ("auto", "escpos", "windows")


class PrinterError(Exception):
    pass


def looks_thermal(name: str) -> bool:
    return bool(name and THERMAL_PATTERN.search(name))


def choose_printer(available: List[str], configured: str = "", default: str = "") -> Optional[str]:
    """La configurada si existe; si no, la primera que parece de tickets; si no, la predeterminada."""
    if configured and configured in available:
        return configured
    for name in available:
        if looks_thermal(name):
            return name
    if default and default in available:
        return default
    return None


def resolve_mode(mode: str, printer_name: str) -> str:
    if mode in ("escpos", "windows"):
        return mode
    return "escpos" if looks_thermal(printer_name) else "windows"


def available_printers() -> List[str]:
    from PyQt6.QtPrintSupport import QPrinterInfo

    return list(QPrinterInfo.availablePrinterNames())


def default_printer() -> str:
    from PyQt6.QtPrintSupport import QPrinterInfo

    return QPrinterInfo.defaultPrinterName()


def send_raw(printer_name: str, data: bytes, job_name: str = "PROVA ticket"):
    """Envia bytes sin procesar al spooler de Windows (tipo de dato RAW)."""
    if sys.platform != "win32":
        raise PrinterError("La impresion ESC/POS directa solo esta disponible en Windows.")
    import ctypes
    from ctypes import wintypes

    class DOC_INFO_1(ctypes.Structure):
        _fields_ = [("pDocName", wintypes.LPWSTR),
                    ("pOutputFile", wintypes.LPWSTR),
                    ("pDatatype", wintypes.LPWSTR)]

    winspool = ctypes.WinDLL("winspool.drv", use_last_error=True)
    winspool.OpenPrinterW.argtypes = [wintypes.LPWSTR, ctypes.POINTER(wintypes.HANDLE), ctypes.c_void_p]
    winspool.OpenPrinterW.restype = wintypes.BOOL
    winspool.StartDocPrinterW.argtypes = [wintypes.HANDLE, wintypes.DWORD, ctypes.POINTER(DOC_INFO_1)]
    winspool.StartDocPrinterW.restype = wintypes.DWORD
    winspool.StartPagePrinter.argtypes = [wintypes.HANDLE]
    winspool.StartPagePrinter.restype = wintypes.BOOL
    winspool.WritePrinter.argtypes = [wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD,
                                      ctypes.POINTER(wintypes.DWORD)]
    winspool.WritePrinter.restype = wintypes.BOOL
    for name in ("EndPagePrinter", "EndDocPrinter", "ClosePrinter"):
        getattr(winspool, name).argtypes = [wintypes.HANDLE]
        getattr(winspool, name).restype = wintypes.BOOL

    def fail(step: str):
        code = ctypes.get_last_error()
        raise PrinterError(f"{step} fallo en '{printer_name}' ({ctypes.FormatError(code).strip()})")

    handle = wintypes.HANDLE()
    if not winspool.OpenPrinterW(printer_name, ctypes.byref(handle), None):
        fail("Abrir la impresora")
    try:
        doc = DOC_INFO_1(job_name, None, "RAW")
        if not winspool.StartDocPrinterW(handle, 1, ctypes.byref(doc)):
            fail("Iniciar el trabajo")
        try:
            if not winspool.StartPagePrinter(handle):
                fail("Iniciar la pagina")
            buffer = ctypes.create_string_buffer(data, len(data))
            written = wintypes.DWORD(0)
            ok = winspool.WritePrinter(handle, buffer, len(data), ctypes.byref(written))
            winspool.EndPagePrinter(handle)
            if not ok or written.value != len(data):
                fail("Enviar los datos")
        finally:
            winspool.EndDocPrinter(handle)
    finally:
        winspool.ClosePrinter(handle)


def print_with_windows_driver(printer_name: str, ticket: "tickets.Ticket", paper_mm: int, job_name: str):
    """Respaldo: dibuja el ticket con Qt en una hoja del ancho del papel, sin margenes grandes."""
    from PyQt6.QtCore import QMarginsF, QSizeF
    from PyQt6.QtGui import QPageLayout, QPageSize, QTextDocument
    from PyQt6.QtPrintSupport import QPrinter

    printer = QPrinter(QPrinter.PrinterMode.HighResolution)
    printer.setPrinterName(printer_name)
    if not printer.isValid():
        raise PrinterError(f"La impresora '{printer_name}' no esta disponible.")
    printer.setDocName(job_name)
    doc = QTextDocument()
    doc.setDocumentMargin(0)
    doc.setHtml(tickets.to_html(ticket))
    if looks_thermal(printer_name):
        page = QPageSize(QSizeF(paper_mm, 297), QPageSize.Unit.Millimeter, "Ticket")
        printer.setPageLayout(QPageLayout(page, QPageLayout.Orientation.Portrait,
                                          QMarginsF(2, 2, 2, 2), QPageLayout.Unit.Millimeter))
    doc.print(printer)


class TicketPrinter:
    """Imprime tickets segun la configuracion de la caja."""

    def __init__(self, config: dict, printers: Optional[List[str]] = None, default: Optional[str] = None):
        self.config = config
        self._printers = printers
        self._default = default

    @property
    def paper_mm(self) -> int:
        return int(self.config.get("ancho_papel_mm", 80))

    @property
    def large_kitchen_items(self) -> bool:
        return self.config.get("letra_comanda", "normal") == "grande"

    @property
    def columns(self) -> int:
        return tickets.columns_for_paper(self.paper_mm)

    def printer_name(self) -> Optional[str]:
        printers = available_printers() if self._printers is None else self._printers
        default = default_printer() if self._default is None else self._default
        return choose_printer(printers, self.config.get("impresora_tickets", ""), default)

    def mode_for(self, printer_name: str) -> str:
        return resolve_mode(self.config.get("modo_impresion", "auto"), printer_name)

    def print_ticket(self, ticket: "tickets.Ticket", job_name: str = "PROVA ticket") -> str:
        name = self.printer_name()
        if not name:
            raise PrinterError("No hay impresoras instaladas en esta computadora.")
        if self.mode_for(name) == "escpos":
            send_raw(name, tickets.to_escpos(ticket), job_name)
        else:
            print_with_windows_driver(name, ticket, self.paper_mm, job_name)
        return name
