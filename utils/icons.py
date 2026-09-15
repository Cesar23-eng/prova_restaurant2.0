# utils/icons.py
"""
Iconos (emoji) para reconocer los productos de un vistazo, en la caja y en el
celular. Solo se usan emoji disponibles en Windows 10 y Android/iOS de hace
varios anos para que no aparezcan cuadros vacios.
"""
import unicodedata

CATEGORY_ICONS = {
    "platillos": "\U0001F32E",  # taco
    "extras": "\U0001F951",     # palta
    "bebidas": "\U0001F964",    # vaso con sorbete
    "jugos": "\U0001F379",      # trago tropical
}

# Se busca la primera palabra clave contenida en el nombre del producto
PRODUCT_KEYWORDS = (
    ("birriamen", "\U0001F35C"),
    ("quesabirria", "\U0001F32E"),
    ("taco", "\U0001F32E"),
    ("burrito", "\U0001F32F"),
    ("quesadilla", "\U0001F9C0"),
    ("nacho", "\U0001F336"),
    ("chilaquil", "\U0001F336"),
    ("torta", "\U0001F96A"),
    ("sopa", "\U0001F372"),
    ("consom", "\U0001F372"),
    ("guacamole", "\U0001F951"),
    ("pico de gallo", "\U0001F345"),
    ("frejol", "\U0001F958"),
    ("totopo", "\U0001F33D"),
    ("tortilla", "\U0001F33D"),
    ("agua", "\U0001F4A7"),
    ("corona", "\U0001F37A"),
    ("cerveza", "\U0001F37A"),
    ("tequila", "\U0001F943"),
    ("jarra", "\U0001F379"),
    ("horchata", "\U0001F95B"),
    ("jamaica", "\U0001F379"),
    ("tamarindo", "\U0001F379"),
    ("coca", "\U0001F964"),
    ("sprite", "\U0001F964"),
    ("fanta", "\U0001F964"),
    ("aquarius", "\U0001F964"),
    ("del valle", "\U0001F964"),
)

DEFAULT_ICON = "\U0001F37D"  # plato con cubiertos


def normalize_text(text: str) -> str:
    """Minusculas y sin tildes, para buscar "consome" y encontrar "Consomé"."""
    text = unicodedata.normalize("NFD", str(text or ""))
    return "".join(ch for ch in text if unicodedata.category(ch) != "Mn").lower().strip()


def category_icon(category: str) -> str:
    return CATEGORY_ICONS.get(normalize_text(category), DEFAULT_ICON)


def product_icon(product: str, category: str = "") -> str:
    name = normalize_text(product)
    for keyword, icon in PRODUCT_KEYWORDS:
        if keyword in name:
            return icon
    return category_icon(category)


def menu_icons(menu: dict) -> dict:
    """{'categorias': {cat: icono}, 'productos': {producto: icono}} para el celular."""
    return {
        "categorias": {category: category_icon(category) for category in menu},
        "productos": {
            product: product_icon(product, category)
            for category, products in menu.items()
            for product in products
        },
    }
