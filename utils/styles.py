class ThemeManager:
    def __init__(self, theme: str = "light"):
        self.themes = {
            "dark": {
                "primary": "#E63946",  # Rojo mexicano
                "secondary": "#457B9D",  # Azul
                "background": "#1D3557",  # Azul oscuro
                "text": "#F1FAEE",  # Blanco crema
                "muted": "#A8B8C8",
                "accent": "#A8DADC",  # Turquesa claro
                "accent_text": "#1D3557",
                "panel": "#2A3F5F",
                "input": "#223A5E",
                "note": "#F4A261",
                "success": "#2A9D8F",
                "warning": "#F4A261",
                "danger": "#E76F51",
            },
            "light": {
                "primary": "#D62828",
                "secondary": "#F77F00",
                "background": "#EAE2B7",
                "text": "#003049",
                "muted": "#5C6F7B",
                "accent": "#FCBF49",
                "accent_text": "#003049",
                "panel": "#F8EDEB",
                "input": "#FFFFFF",
                "note": "#B34700",
                "success": "#588157",
                "warning": "#F4A261",
                "danger": "#E63946",
            },
        }
        self.current_theme = theme if theme in self.themes else "light"

    def get_current_theme(self) -> dict:
        return self.themes[self.current_theme]

    def toggle_theme(self):
        self.current_theme = "light" if self.current_theme == "dark" else "dark"

    def get_stylesheet(self) -> str:
        theme = self.get_current_theme()
        return f"""
            QMainWindow, QDialog {{
                background-color: {theme['background']};
            }}

            QLabel {{
                color: {theme['text']};
            }}

            #leftPanel {{
                background-color: {theme['panel']};
                border-radius: 15px;
                padding: 15px;
            }}

            #rightPanel {{
                background-color: {theme['background']};
                border-radius: 15px;
            }}

            #appTitle {{
                color: {theme['primary']};
                margin-bottom: 5px;
            }}

            #appSubtitle {{
                color: {theme['text']};
                margin-bottom: 10px;
            }}

            #tableList {{
                background-color: {theme['background']};
                color: {theme['text']};
                border: 2px solid {theme['accent']};
                border-radius: 10px;
                padding: 6px;
            }}

            #tableList::item {{
                padding: 8px;
                border-bottom: 1px solid {theme['accent']};
            }}

            #tableList::item:selected {{
                background-color: {theme['primary']};
                color: white;
                border-radius: 5px;
            }}

            #orderHeader {{
                color: {theme['primary']};
                border-bottom: 2px solid {theme['accent']};
                padding-bottom: 10px;
            }}

            #tableInfo {{
                color: {theme['text']};
                background-color: {theme['panel']};
                padding: 10px;
                border-radius: 8px;
            }}

            #menuWarning {{
                color: white;
                background-color: {theme['danger']};
                padding: 8px;
                border-radius: 8px;
            }}

            QComboBox, QLineEdit, QSpinBox, QDoubleSpinBox, QDateEdit {{
                background-color: {theme['input']};
                color: {theme['text']};
                border: 1px solid {theme['accent']};
                border-radius: 5px;
                padding: 7px;
            }}

            QComboBox {{
                min-width: 150px;
            }}

            QSpinBox::up-button, QSpinBox::down-button {{
                width: 22px;
            }}

            QComboBox::drop-down {{
                border: none;
            }}

            QComboBox QAbstractItemView {{
                background-color: {theme['input']};
                color: {theme['text']};
                selection-background-color: {theme['primary']};
                selection-color: white;
            }}

            QListWidget, QTextBrowser {{
                background-color: {theme['panel']};
                color: {theme['text']};
                border: 1px solid {theme['accent']};
                border-radius: 8px;
            }}

            QRadioButton, QCheckBox, QGroupBox {{
                color: {theme['text']};
            }}

            #orderDisplay {{
                background-color: {theme['panel']};
                color: {theme['text']};
                border: 2px solid {theme['accent']};
                border-radius: 10px;
                padding: 10px;
            }}

            QStatusBar {{
                background-color: {theme['panel']};
                color: {theme['text']};
            }}

            QStatusBar QLabel {{
                padding: 2px 8px;
            }}

            /* Botones */
            #primaryButton {{
                background-color: {theme['primary']};
                color: white;
                border-radius: 8px;
                padding: 10px 15px;
                border: none;
            }}

            #primaryButton:hover {{
                background-color: {theme['secondary']};
            }}

            #secondaryButton {{
                background-color: {theme['secondary']};
                color: white;
                border-radius: 8px;
                padding: 10px 15px;
                border: none;
            }}

            #secondaryButton:hover {{
                background-color: {theme['primary']};
            }}

            #successButton {{
                background-color: {theme['success']};
                color: white;
                border-radius: 8px;
                padding: 10px 15px;
                border: none;
            }}

            #successButton:hover {{
                background-color: {theme['accent']};
                color: {theme['accent_text']};
            }}

            #warningButton {{
                background-color: {theme['warning']};
                color: black;
                border-radius: 8px;
                padding: 10px 15px;
                border: none;
            }}

            #dangerButton {{
                background-color: {theme['danger']};
                color: white;
                border-radius: 8px;
                padding: 10px 15px;
                border: none;
            }}

            #accentButton {{
                background-color: {theme['accent']};
                color: {theme['accent_text']};
                border-radius: 8px;
                padding: 10px 15px;
                border: none;
            }}

            QPushButton:disabled {{
                background-color: {theme['muted']};
                color: {theme['panel']};
            }}

            QPushButton::menu-indicator {{
                subcontrol-position: right center;
                right: 8px;
            }}
        """
