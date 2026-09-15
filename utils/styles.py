# utils/styles.py
"""
Identidad visual de PRÖVA México para la app de caja.

La paleta sale del logo (negro, rojo de los labios, rosa de la firma "México",
verde del chile) y del local (techo carbon, concreto, mesas de madera clara y
sombreros rosa y turquesa). Todos los pares texto/fondo cumplen WCAG AA.
"""

TITLE_FONT = "Bahnschrift SemiBold Condensed"  # parecida a la tipografia de PRÖVA
SCRIPT_FONT = "Segoe Script"                    # para la firma "México"
BODY_FONT = "Segoe UI"

THEME_NAMES = {"noche": "Noche", "dia": "Día"}

THEMES = {
    # Negro del logo y carbon del techo del local
    "noche": {
        "bg": "#0A0A0A",
        "surface": "#141414",
        "surface2": "#1C1C1C",
        "surface3": "#262626",
        "border": "#2E2E2E",
        "border_strong": "#444444",
        "text": "#F6F2EC",
        "muted": "#A39E97",
        "primary": "#D7262E",
        "primary_hover": "#E53A42",
        "primary_pressed": "#B01C23",
        "on_primary": "#FFFFFF",
        "accent": "#FF5A6E",
        "success": "#2E7D3E",
        "success_hover": "#37914A",
        "success_soft": "#132A19",
        "qr": "#0F7C6C",
        "qr_hover": "#12927F",
        "wood": "#C9A27A",
        "wood_text": "#D8B48C",
        "wood_soft": "#2A221A",
        "on_wood": "#1B140C",
        "pink": "#F0579E",
        "pink_soft": "#34162A",
        "warning": "#F2A33A",
        "warning_soft": "#33240F",
        "danger": "#EF4B52",
        "danger_soft": "#3A1517",
        "shadow": "#000000",
    },
    # Paredes de concreto claro y platos blancos
    "dia": {
        "bg": "#E9E6E1",
        "surface": "#FFFFFF",
        "surface2": "#F7F5F1",
        "surface3": "#EFEBE5",
        "border": "#DDD7CF",
        "border_strong": "#C2BBB1",
        "text": "#141414",
        "muted": "#6B655E",
        "primary": "#C8102E",
        "primary_hover": "#A80D26",
        "primary_pressed": "#8E0B20",
        "on_primary": "#FFFFFF",
        "accent": "#C8102E",
        "success": "#2E7D3E",
        "success_hover": "#276B35",
        "success_soft": "#E3F2E6",
        "qr": "#0F7C6C",
        "qr_hover": "#0B6457",
        "wood": "#C9A27A",
        "wood_text": "#7A5230",
        "wood_soft": "#F3E8DC",
        "on_wood": "#1B140C",
        "pink": "#B0145A",
        "pink_soft": "#FBE3EE",
        "warning": "#9A5B00",
        "warning_soft": "#FFF1DB",
        "danger": "#C62828",
        "danger_soft": "#FDE4E4",
        "shadow": "#9E978D",
    },
}


class ThemeManager:
    def __init__(self, theme: str = "noche"):
        self.themes = THEMES
        self.current_theme = theme if theme in THEMES else "noche"

    def get_current_theme(self) -> dict:
        return self.themes[self.current_theme]

    @property
    def is_dark(self) -> bool:
        return self.current_theme == "noche"

    def toggle_theme(self):
        self.current_theme = "dia" if self.current_theme == "noche" else "noche"

    def get_stylesheet(self) -> str:
        t = self.get_current_theme()
        return f"""
        QWidget {{
            font-family: "{BODY_FONT}";
            font-size: 10pt;
            color: {t['text']};
        }}
        QMainWindow, QDialog, #central {{
            background-color: {t['bg']};
        }}
        QToolTip {{
            background-color: {t['surface3']};
            color: {t['text']};
            border: 1px solid {t['border_strong']};
            padding: 6px;
        }}
        QLabel {{ background: transparent; }}

        /* ---------- Encabezado ---------- */
        #header {{
            background-color: {t['surface']};
            border-bottom: 1px solid {t['border']};
        }}
        #brandTitle {{
            font-family: "{TITLE_FONT}";
            font-size: 22pt;
            color: {t['text']};
        }}
        #brandScript {{
            font-family: "{SCRIPT_FONT}";
            font-size: 11pt;
            color: {t['accent']};
        }}
        #logoBadge {{
            background-color: #000000;
            border-radius: 12px;
        }}
        #headerInfo {{
            color: {t['muted']};
            font-size: 10pt;
        }}
        #headerChip {{
            background-color: {t['surface2']};
            border: 1px solid {t['border']};
            border-radius: 18px;
            padding: 8px 14px;
            font-weight: 600;
        }}
        #headerChip:hover {{ border-color: {t['primary']}; }}
        #headerChip[status="ok"] {{ border-color: {t['success']}; }}
        #headerChip[status="error"] {{ border-color: {t['danger']}; color: {t['danger']}; }}

        /* ---------- Paneles ---------- */
        #panel {{
            background-color: {t['surface']};
            border: 1px solid {t['border']};
            border-radius: 18px;
        }}
        #panelTitle {{
            font-family: "{TITLE_FONT}";
            font-size: 15pt;
            color: {t['text']};
        }}
        #muted, #cardMeta, #lineSub {{
            color: {t['muted']};
        }}
        #hint {{
            color: {t['muted']};
            font-size: 9pt;
        }}
        #emptyState {{
            color: {t['muted']};
            font-size: 11pt;
        }}
        #emptyIcon {{ font-size: 40pt; }}
        #menuWarning {{
            background-color: {t['danger_soft']};
            color: {t['danger']};
            border: 1px solid {t['danger']};
            border-radius: 10px;
            padding: 8px 12px;
            font-weight: 600;
        }}

        QScrollArea, QScrollArea > QWidget > QWidget {{
            background: transparent;
            border: none;
        }}
        QScrollBar:vertical {{
            background: transparent;
            width: 10px;
            margin: 2px;
        }}
        QScrollBar::handle:vertical {{
            background: {t['border_strong']};
            border-radius: 4px;
            min-height: 30px;
        }}
        QScrollBar::handle:vertical:hover {{ background: {t['muted']}; }}
        QScrollBar::add-line, QScrollBar::sub-line,
        QScrollBar::add-page, QScrollBar::sub-page {{
            background: none;
            height: 0;
        }}
        QScrollBar:horizontal {{ height: 0; }}

        /* ---------- Campos ---------- */
        QLineEdit, QSpinBox, QComboBox, QDateEdit {{
            background-color: {t['surface3']};
            color: {t['text']};
            border: 1px solid {t['border']};
            border-radius: 10px;
            padding: 8px 10px;
            selection-background-color: {t['primary']};
            selection-color: {t['on_primary']};
        }}
        QLineEdit:focus, QSpinBox:focus, QComboBox:focus, QDateEdit:focus {{
            border: 1px solid {t['primary']};
        }}
        QLineEdit:disabled, QComboBox:disabled {{ color: {t['muted']}; }}
        #searchInput {{
            font-size: 12pt;
            padding: 10px 14px;
            border-radius: 14px;
        }}
        #bigInput {{
            font-family: "{TITLE_FONT}";
            font-size: 24pt;
            padding: 6px 12px;
        }}
        QSpinBox::up-button, QSpinBox::down-button {{ width: 22px; border: none; }}
        QComboBox::drop-down {{ border: none; width: 26px; }}
        QComboBox QAbstractItemView, QMenu {{
            background-color: {t['surface2']};
            color: {t['text']};
            border: 1px solid {t['border_strong']};
            selection-background-color: {t['primary']};
            selection-color: {t['on_primary']};
            padding: 4px;
        }}
        QMenu::item {{ padding: 8px 22px 8px 14px; border-radius: 6px; }}
        QMenu::item:selected {{ background-color: {t['primary']}; color: {t['on_primary']}; }}
        QMenu::item:disabled {{ color: {t['muted']}; }}
        QMenu::separator {{ height: 1px; background: {t['border']}; margin: 4px 8px; }}

        QListWidget, QTextBrowser {{
            background-color: {t['surface2']};
            color: {t['text']};
            border: 1px solid {t['border']};
            border-radius: 12px;
            padding: 6px;
        }}
        QListWidget::item {{ padding: 6px; border-radius: 6px; }}
        QListWidget::item:selected {{
            background-color: {t['primary']};
            color: {t['on_primary']};
        }}
        QRadioButton, QCheckBox, QGroupBox {{ color: {t['text']}; }}

        /* ---------- Botones ---------- */
        QPushButton {{
            background-color: {t['surface3']};
            color: {t['text']};
            border: 1px solid {t['border']};
            border-radius: 12px;
            padding: 9px 14px;
            font-weight: 600;
        }}
        QPushButton:hover {{ border-color: {t['border_strong']}; background-color: {t['surface2']}; }}
        QPushButton:pressed {{ background-color: {t['border']}; }}
        QPushButton:disabled {{
            color: {t['muted']};
            background-color: {t['surface2']};
            border-color: {t['border']};
        }}
        QPushButton::menu-indicator {{ width: 0; image: none; }}

        #primaryButton {{
            background-color: {t['primary']};
            color: {t['on_primary']};
            border: none;
            font-weight: 700;
        }}
        #primaryButton:hover {{ background-color: {t['primary_hover']}; }}
        #primaryButton:pressed {{ background-color: {t['primary_pressed']}; }}
        #primaryButton:disabled {{ background-color: {t['surface3']}; color: {t['muted']}; }}

        #successButton, #payButton {{
            background-color: {t['success']};
            color: #FFFFFF;
            border: none;
            font-weight: 700;
        }}
        #successButton:hover, #payButton:hover {{ background-color: {t['success_hover']}; }}
        #successButton:disabled, #payButton:disabled {{ background-color: {t['surface3']}; color: {t['muted']}; }}
        #payButton {{
            font-family: "{TITLE_FONT}";
            font-size: 17pt;
            padding: 12px;
            border-radius: 14px;
        }}
        #bigPrimary {{
            background-color: {t['primary']};
            color: {t['on_primary']};
            border: none;
            font-family: "{TITLE_FONT}";
            font-size: 14pt;
            padding: 11px;
            border-radius: 14px;
        }}
        #bigPrimary:hover {{ background-color: {t['primary_hover']}; }}

        #dangerButton {{
            background-color: transparent;
            color: {t['danger']};
            border: 1px solid {t['danger']};
        }}
        #dangerButton:hover {{ background-color: {t['danger_soft']}; }}
        #ghostButton {{
            background-color: transparent;
            color: {t['muted']};
            border: 1px dashed {t['border_strong']};
        }}
        #ghostButton:hover {{ color: {t['text']}; border-color: {t['muted']}; }}
        #iconButton {{
            background-color: transparent;
            border: 1px solid transparent;
            border-radius: 10px;
            padding: 4px 8px;
            font-size: 13pt;
            color: {t['muted']};
        }}
        #iconButton:hover {{ background-color: {t['surface3']}; color: {t['text']}; }}
        #secondaryButton {{
            background-color: {t['surface2']};
            border: 1px solid {t['border_strong']};
        }}
        #secondaryButton:hover {{ border-color: {t['primary']}; }}
        #secondaryButton[attention="true"] {{
            border: 2px solid {t['warning']};
            color: {t['warning']};
        }}

        /* Chips de categoria y segmentos */
        #chip, #segment {{
            background-color: {t['surface2']};
            border: 1px solid {t['border']};
            border-radius: 16px;
            padding: 7px 14px;
        }}
        #chip:hover, #segment:hover {{ border-color: {t['primary']}; }}
        #chip:checked, #segment:checked {{
            background-color: {t['primary']};
            border-color: {t['primary']};
            color: {t['on_primary']};
        }}
        #segment:disabled:checked {{ background-color: {t['surface3']}; color: {t['text']}; }}
        #segment[method="cash"]:checked {{ background-color: {t['success']}; border-color: {t['success']}; color: #FFFFFF; }}
        #segment[method="qr"]:checked {{ background-color: {t['qr']}; border-color: {t['qr']}; color: #FFFFFF; }}

        /* Platos: el color de las mesas de madera */
        #plateChip {{
            background-color: transparent;
            border: 1px solid {t['wood']};
            color: {t['wood_text']};
            border-radius: 15px;
            padding: 5px 12px;
            min-width: 18px;
        }}
        #plateChip:hover {{ background-color: {t['wood_soft']}; }}
        #plateChip:checked {{
            background-color: {t['wood']};
            color: {t['on_wood']};
            font-weight: 700;
        }}
        #plateChip[newPlate="true"] {{ border-style: dashed; }}
        #plateHeader {{
            background-color: {t['wood_soft']};
            color: {t['wood_text']};
            border-radius: 8px;
            padding: 5px 10px;
            font-weight: 700;
        }}

        /* Metodos de pago */
        #methodButton {{
            background-color: {t['surface2']};
            border: 2px solid {t['border']};
            border-radius: 14px;
            padding: 14px 8px;
            font-size: 12pt;
            font-weight: 700;
        }}
        #methodButton:hover {{ border-color: {t['border_strong']}; }}
        #methodButton[method="cash"]:checked {{ background-color: {t['success']}; border-color: {t['success']}; color: #FFFFFF; }}
        #methodButton[method="qr"]:checked {{ background-color: {t['qr']}; border-color: {t['qr']}; color: #FFFFFF; }}
        #methodButton[method="mixed"]:checked {{ background-color: {t['wood']}; border-color: {t['wood']}; color: {t['on_wood']}; }}
        #quickAmount {{
            background-color: {t['surface2']};
            border: 1px solid {t['border_strong']};
            border-radius: 12px;
            padding: 10px 6px;
            font-family: "{TITLE_FONT}";
            font-size: 13pt;
        }}
        #quickAmount:hover {{ border-color: {t['success']}; }}
        #resultBox {{
            border-radius: 12px;
            padding: 12px;
            font-family: "{TITLE_FONT}";
            font-size: 18pt;
            background-color: {t['surface2']};
            color: {t['muted']};
        }}
        #resultBox[state="ok"] {{ background-color: {t['success_soft']}; color: {t['success_hover'] if self.is_dark else t['success']}; }}
        #resultBox[state="change"] {{ background-color: {t['success']}; color: #FFFFFF; }}
        #resultBox[state="missing"] {{ background-color: {t['danger_soft']}; color: {t['danger']}; }}

        /* ---------- Menu ---------- */
        #productCard {{
            background-color: {t['surface2']};
            border: 1px solid {t['border']};
            border-radius: 14px;
        }}
        #productCard:hover {{ border-color: {t['border_strong']}; }}
        #productName {{
            font-size: 11pt;
            font-weight: 700;
        }}
        #productIcon {{ font-size: 16pt; }}
        #variantChip {{
            background-color: {t['surface3']};
            border: 1px solid {t['border']};
            border-radius: 10px;
            padding: 7px 10px;
            font-weight: 600;
            text-align: left;
        }}
        #variantChip:hover {{
            border-color: {t['primary']};
            background-color: {t['surface']};
        }}
        #variantChip:pressed {{ background-color: {t['primary']}; color: {t['on_primary']}; }}
        #variantChip[flash="true"] {{
            background-color: {t['success']};
            border-color: {t['success']};
            color: #FFFFFF;
        }}

        /* ---------- Pedidos ---------- */
        #orderCard {{
            background-color: {t['surface2']};
            border: 1px solid {t['border']};
            border-radius: 14px;
        }}
        #orderCard:hover {{ border-color: {t['border_strong']}; }}
        #orderCard[selected="true"] {{
            border: 2px solid {t['primary']};
            background-color: {t['surface3']};
        }}
        #orderCard[paid="true"] {{ background-color: {t['surface']}; }}
        #cardNumber {{
            font-family: "{TITLE_FONT}";
            font-size: 12pt;
            color: {t['accent']};
        }}
        #cardTitle {{ font-size: 11pt; font-weight: 700; }}
        #cardTotal {{
            font-family: "{TITLE_FONT}";
            font-size: 13pt;
        }}
        #badge {{
            border-radius: 9px;
            padding: 2px 8px;
            font-size: 8.5pt;
            font-weight: 700;
            background-color: {t['surface3']};
            color: {t['muted']};
        }}
        #badge[kind="takeaway"] {{ background-color: {t['pink_soft']}; color: {t['pink']}; }}
        #badge[kind="kitchen"] {{ background-color: {t['warning_soft']}; color: {t['warning']}; }}
        #badge[kind="paid"] {{ background-color: {t['success_soft']}; color: {t['success_hover'] if self.is_dark else t['success']}; }}
        #badge[kind="warn"] {{ background-color: {t['warning_soft']}; color: {t['warning']}; }}
        #badge[kind="late"] {{ background-color: {t['danger_soft']}; color: {t['danger']}; }}
        #badge[kind="waiter"] {{ background-color: {t['surface3']}; color: {t['text']}; }}

        /* ---------- Ticket ---------- */
        #ticketNumber {{
            font-family: "{TITLE_FONT}";
            font-size: 15pt;
            color: {t['accent']};
        }}
        #ticketTitle {{
            font-family: "{TITLE_FONT}";
            font-size: 17pt;
        }}
        #ticketLine {{
            border-bottom: 1px solid {t['border']};
        }}
        #lineName {{ font-weight: 700; font-size: 10.5pt; }}
        #lineNote {{ color: {t['warning']}; font-style: italic; }}
        #linePrice {{ font-family: "{TITLE_FONT}"; font-size: 12.5pt; }}
        #qtyLabel {{ font-family: "{TITLE_FONT}"; font-size: 13pt; min-width: 22px; }}
        #qtyButton {{
            background-color: {t['surface3']};
            border: 1px solid {t['border']};
            border-radius: 14px;
            min-width: 28px;
            max-width: 28px;
            min-height: 28px;
            max-height: 28px;
            padding: 0;
            font-size: 12pt;
            font-weight: 700;
        }}
        #qtyButton:hover {{ border-color: {t['primary']}; color: {t['accent']}; }}
        #kitchenDot {{ color: {t['warning']}; font-size: 9pt; }}
        #lineMenuButton {{
            background-color: transparent;
            border: 1px solid {t['border_strong']};
            border-radius: 14px;
            min-width: 28px;
            max-width: 28px;
            min-height: 28px;
            max-height: 28px;
            padding: 0;
            font-size: 12pt;
            font-weight: 700;
            color: {t['text']};
        }}
        #lineMenuButton:hover {{ border-color: {t['primary']}; color: {t['accent']}; }}
        #totalAmount {{
            font-family: "{TITLE_FONT}";
            font-size: 26pt;
        }}
        #paidBanner {{
            background-color: {t['success_soft']};
            border: 1px solid {t['success']};
            border-radius: 12px;
            padding: 10px;
            font-weight: 600;
        }}

        /* ---------- Avisos ---------- */
        #toast {{
            background-color: {t['surface3']};
            color: {t['text']};
            border: 1px solid {t['border_strong']};
            border-radius: 14px;
            padding: 12px 20px;
            font-size: 11pt;
            font-weight: 600;
        }}
        #toast[kind="success"] {{ background-color: {t['success']}; border-color: {t['success']}; color: #FFFFFF; }}
        #toast[kind="error"] {{ background-color: {t['danger_soft']}; border-color: {t['danger']}; color: {t['danger']}; }}
        #toast[kind="warning"] {{ background-color: {t['warning_soft']}; border-color: {t['warning']}; color: {t['warning']}; }}

        QStatusBar {{ background-color: {t['surface']}; color: {t['muted']}; }}
        """
