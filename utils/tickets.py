# utils/tickets.py
"""
Tickets de impresora termica (comanda de cocina, cuenta y cierre de caja).

Un ticket es una lista de lineas con estilo (negrita, alto doble, centrado).
Se arma una sola vez y se convierte a:
- ESC/POS: el lenguaje nativo de las Epson TM (TM-T20III y similares). Usa la
  letra de la impresora a tamaño fijo, corta el papel y no depende del driver.
- Texto plano: para pruebas y vista previa.
- HTML monoespaciado: respaldo para impresoras comunes de Windows.

Tamaños en una TM-T20III con papel de 80 mm (203 ppp, 48 columnas):
- normal: Font A, 12x24 puntos = letra de 1,5 x 3 mm (la de un ticket comun).
- tall:   alto doble, 1,5 x 6 mm. Numero de pedido y encabezados de plato.
- big:    alto y ancho doble, 3 x 6 mm, 24 columnas. Solo el TOTAL de la cuenta.
"""
import datetime
import html
import textwrap
from dataclasses import dataclass, field
from typing import List

from models.order import group_lines_by_plate, plate_label

COLUMNS_BY_PAPER = {80: 48, 58: 32}

ESC = b"\x1b"
GS = b"\x1d"
SIZE_CODES = {"normal": 0x00, "tall": 0x01, "big": 0x11}
ALIGN_CODES = {"left": 0, "center": 1, "right": 2}
CODEPAGE_WPC1252 = 16  # tildes, ñ, ¡ y ¿ en Epson TM


def money(value: float) -> str:
    return f"Bs {value:,.2f}"


@dataclass
class Line:
    text: str = ""
    bold: bool = False
    size: str = "normal"
    align: str = "left"


@dataclass
class Ticket:
    columns: int = 48
    lines: List[Line] = field(default_factory=list)

    def width_for(self, size: str) -> int:
        return self.columns // 2 if size == "big" else self.columns

    def add(self, text: str = "", bold: bool = False, size: str = "normal", align: str = "left",
            indent: int = 0):
        """Agrega texto partiendo en varias lineas si no entra en el ancho del papel."""
        width = self.width_for(size)
        if not text:
            self.lines.append(Line("", bold, size, align))
            return
        wrapped = textwrap.wrap(text, width=width, subsequent_indent=" " * indent,
                                break_long_words=True, break_on_hyphens=False) or [""]
        for part in wrapped:
            self.lines.append(Line(part, bold, size, align))

    def row(self, left: str, right: str, bold: bool = False, size: str = "normal"):
        """Texto a la izquierda y monto a la derecha en la misma linea."""
        width = self.width_for(size)
        room = width - len(right) - 1
        if len(left) > room:
            parts = textwrap.wrap(left, width=room, subsequent_indent="  ") or [""]
            for part in parts[:-1]:
                self.lines.append(Line(part, bold, size))
            left = parts[-1]
        self.lines.append(Line(left + " " * (width - len(left) - len(right)) + right, bold, size))

    def separator(self, char: str = "-"):
        self.lines.append(Line(char * self.columns))

    def blank(self):
        self.lines.append(Line(""))


def columns_for_paper(paper_mm: int) -> int:
    return COLUMNS_BY_PAPER.get(int(paper_mm), 48)


def _stamp(now: datetime.datetime = None) -> str:
    return (now or datetime.datetime.now()).strftime("%d/%m/%Y %H:%M")


# ---------------------------------------------------------------------------
#  Contenido
# ---------------------------------------------------------------------------
def kitchen_ticket(local_name: str, order: dict, table: str, lines: List[dict], reprint: bool,
                   columns: int = 48, now: datetime.datetime = None, large_items: bool = False) -> Ticket:
    """
    Comanda para cocina: sin precios, agrupada por plato y con las notas visibles.
    `large_items` imprime los platillos en alto doble si en cocina se lee de lejos.
    """
    ticket = Ticket(columns)
    ticket.add(local_name, bold=True, align="center")
    ticket.add("COMANDA COCINA" + (" - REIMPRESION" if reprint else ""), align="center")
    ticket.separator()
    ticket.add(f"{order['number']}  {table}", bold=True, size="tall")
    ticket.row(order["order_type"], _stamp(now))
    ticket.separator()

    sent_plates = {i.get("plate", 0) for i in order.get("items", []) if i.get("kitchen_sent")}
    with_plates = any(line.get("plate") for line in lines)
    groups = group_lines_by_plate(lines)
    for position, (plate, plate_lines) in enumerate(groups):
        if with_plates:
            if position:
                ticket.blank()
            heading = plate_label(plate).upper() if plate else "SIN PLATO"
            if plate and plate in sent_plates and not reprint:
                heading += " (agregar)"
            ticket.add(f"== {heading} ==", bold=True, size="tall")
        for line in plate_lines:
            ticket.add(f"{line['qty']:>2} x {line['dish']} ({line['variant']})", bold=True, indent=5,
                       size="tall" if large_items else "normal")
            if line.get("note"):
                ticket.add(f"     >> {line['note']}", indent=8)
    ticket.separator()
    units = sum(line["qty"] for line in lines)
    ticket.add(f"{units} {'item' if units == 1 else 'items'}", align="right")
    return ticket


def customer_bill(local_name: str, city: str, order: dict, table: str, lines: List[dict],
                  columns: int = 48, now: datetime.datetime = None) -> Ticket:
    """Cuenta del cliente: suma las lineas iguales sin importar plato ni nota."""
    ticket = Ticket(columns)
    ticket.add(local_name, bold=True, size="tall", align="center")
    if city:
        ticket.add(city, align="center")
    ticket.add("CUENTA", align="center")
    ticket.separator()
    ticket.row(f"{order['number']}  {table}", _stamp(now), bold=True)
    ticket.add(order["order_type"])
    ticket.separator()

    merged = {}
    for line in lines:
        key = (line["dish"], line["variant"], line["unit_price"])
        entry = merged.setdefault(key, [0, 0.0])
        entry[0] += line["qty"]
        entry[1] += line["subtotal"]
    for (dish, variant, _price), (qty, subtotal) in merged.items():
        ticket.row(f"{qty} x {dish} ({variant})", f"{subtotal:,.2f}")
    ticket.separator()
    total = sum(line["subtotal"] for line in lines)
    ticket.row("TOTAL", money(total), bold=True, size="big")

    delivery = order.get("delivery")
    if delivery and order.get("order_type") == "Para llevar" and delivery.get("moto_cost"):
        ticket.row("Moto", f"{money(delivery['moto_cost'])} ({delivery['moto_payment_method']})")
    payment = order.get("payment")
    if payment:
        ticket.row("Pagado", payment["method"])
        if payment.get("change"):
            ticket.row("Recibido", money(payment["amount_paid"]))
            ticket.row("Cambio", money(payment["change"]))
    ticket.separator()
    ticket.add("¡Gracias por tu visita!", align="center")
    ticket.add("No la mires mucho, se te va a antojar", align="center")
    return ticket


def day_summary_ticket(local_name: str, summary: dict, date_label: str, columns: int = 48,
                       now: datetime.datetime = None) -> Ticket:
    ticket = Ticket(columns)
    ticket.add(local_name, bold=True, size="tall", align="center")
    ticket.add(f"CIERRE DE CAJA - {date_label}", bold=True, align="center")
    ticket.add(f"Impreso {_stamp(now)}", align="center")
    ticket.separator()
    if not summary["orders"]:
        ticket.add("No hay ventas cobradas en esta jornada.")
        return ticket

    ticket.row("Pedidos cobrados", str(summary["orders"]))
    ticket.row("TOTAL VENDIDO", money(summary["total"]), bold=True, size="tall")
    ticket.row("Ticket promedio", money(summary["average_ticket"]))
    ticket.row("Horario", f"{summary['first_time'][:5]} a {summary['last_time'][:5]}")
    ticket.separator()
    ticket.add("CAJA", bold=True)
    ticket.row("Efectivo neto en caja", money(summary["cash_net"]), bold=True)
    ticket.row("QR neto", money(summary["qr_net"]), bold=True)
    ticket.row("Cambio dado en efectivo", money(summary["change_cash"]))
    ticket.row("Cambio dado por QR", money(summary["change_qr"]))
    if summary["moto_orders"]:
        ticket.row(f"Motos ({summary['moto_orders']}) efectivo", money(summary["moto_cash"]))
        ticket.row("Motos QR", money(summary["moto_qr"]))
    ticket.separator()
    ticket.add("POR METODO DE PAGO", bold=True)
    for method, data in summary["by_method"].items():
        ticket.row(f"{method} ({data['orders']})", money(data["total"]))
    ticket.add("POR TIPO DE CONSUMO", bold=True)
    for order_type, data in summary["by_type"].items():
        ticket.row(f"{order_type} ({data['orders']})", money(data["total"]))
    ticket.separator()
    ticket.add("PRODUCTOS VENDIDOS", bold=True)
    for product in summary["products"]:
        ticket.row(f"{product['qty']} x {product['product']}", money(product["amount"]))
    return ticket


def test_ticket(local_name: str, printer_name: str, columns: int = 48,
                now: datetime.datetime = None) -> Ticket:
    ticket = Ticket(columns)
    ticket.add(local_name, bold=True, size="tall", align="center")
    ticket.add("PRUEBA DE IMPRESORA", align="center")
    ticket.separator()
    ticket.add(printer_name)
    ticket.add(_stamp(now))
    ticket.separator()
    ticket.add("Normal: 3 x Taco (Pastor)")
    ticket.add("Negrita: 3 x Taco (Pastor)", bold=True)
    ticket.add("== PLATO 1 ==", bold=True, size="tall")
    ticket.row("TOTAL", "Bs 45.00", bold=True, size="big")
    ticket.add("Tildes: á é í ó ú ñ Ñ ¡ ¿", align="center")
    ticket.add("1234567890" * (columns // 10) + "12345678"[: columns % 10])
    return ticket


# ---------------------------------------------------------------------------
#  Conversion
# ---------------------------------------------------------------------------
def to_text(ticket: Ticket) -> str:
    out = []
    for line in ticket.lines:
        width = ticket.width_for(line.size)
        if line.align == "center":
            text = line.text.center(width).rstrip()
        elif line.align == "right":
            text = line.text.rjust(width)
        else:
            text = line.text
        out.append(text)
    return "\n".join(out)


def to_escpos(ticket: Ticket, cut: bool = True, feed_lines: int = 4) -> bytes:
    data = bytearray()
    data += ESC + b"@"                                  # reiniciar la impresora
    data += ESC + b"t" + bytes([CODEPAGE_WPC1252])      # pagina de codigos con tildes
    data += ESC + b"M" + b"\x00"                        # Font A (12x24)
    current = (None, None, None)
    for line in ticket.lines:
        style = (line.bold, line.size, line.align)
        if style != current:
            data += ESC + b"E" + bytes([1 if line.bold else 0])
            data += GS + b"!" + bytes([SIZE_CODES[line.size]])
            data += ESC + b"a" + bytes([ALIGN_CODES[line.align]])
            current = style
        data += line.text.encode("cp1252", errors="replace") + b"\n"
    data += ESC + b"E\x00" + GS + b"!\x00" + ESC + b"a\x00"
    data += ESC + b"d" + bytes([feed_lines])            # avanzar papel hasta la cuchilla
    if cut:
        data += GS + b"V" + b"\x42" + b"\x00"           # corte parcial
    return bytes(data)


def to_html(ticket: Ticket) -> str:
    """Respaldo para impresoras que no son termicas: monoespaciado y en puntos."""
    sizes = {"normal": "9pt", "tall": "13pt", "big": "15pt"}
    parts = ["<div style='font-family: Consolas, \"Courier New\", monospace;'>"]
    for line in ticket.lines:
        style = f"font-size:{sizes[line.size]}; text-align:{line.align}; margin:0;"
        if line.bold:
            style += " font-weight:bold;"
        text = html.escape(line.text).replace(" ", "&nbsp;") or "&nbsp;"
        parts.append(f"<p style='{style}'>{text}</p>")
    parts.append("</div>")
    return "".join(parts)
