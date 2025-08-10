from PyQt6.QtGui import QColor


class ThemeManager:
    def __init__(self):
        self.themes = {
            "dark": {
                "primary": "#E63946",  # Rojo mexicano
                "secondary": "#457B9D",  # Azul
                "background": "#1D3557",  # Azul oscuro
                "text": "#000000",  # Blanco crema
                "accent": "#A8DADC",  # Turquesa claro
                "panel": "#2A3F5F",
                "success": "#2A9D8F",
                "warning": "#F4A261",
                "danger": "#E76F51"
            },
            "light": {
                "primary": "#D62828",
                "secondary": "#F77F00",
                "background": "#EAE2B7",
                "text": "#003049",
                "accent": "#FCBF49",
                "panel": "#F8EDEB",
                "success": "#588157",
                "warning": "#F4A261",
                "danger": "#E63946"
            }
        }
        self.current_theme = "light"

    def get_current_theme(self) -> dict:
        return self.themes[self.current_theme]

    def toggle_theme(self):
        self.current_theme = "light" if self.current_theme == "dark" else "dark"

    def get_stylesheet(self) -> str:
        theme = self.get_current_theme()
        return f"""
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
                margin-bottom: 20px;
            }}

            #tableList {{
                background-color: {theme['background']};
                color: {theme['text']};
                border: 2px solid {theme['accent']};
                border-radius: 10px;
                padding: 10px;
            }}

            #tableList::item {{
                padding: 10px;
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

            QComboBox {{
                background-color: {theme['panel']};
                color: {theme['text']};
                border: 1px solid {theme['accent']};
                border-radius: 5px;
                padding: 8px;
                min-width: 150px;
            }}

            QComboBox::drop-down {{
                border: none;
            }}

            #orderDisplay {{
                background-color: {theme['panel']};
                color: {theme['text']};
                border: 2px solid {theme['accent']};
                border-radius: 10px;
                padding: 15px;
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
                color: {theme['background']};
                border-radius: 8px;
                padding: 10px 15px;
                border: none;
            }}
        """