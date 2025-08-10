from typing import Dict, Any

class MenuData:
    @staticmethod
    def get_menu_prices() -> Dict[str, Any]:
        return {
            "Platillos": {
                "Quesadilla": {"Carne": 32, "Pollo": 32, "Mixto": 32, "Gringa": 40, "Birria": 32, "Lengua": 45,
                               "Campechana": 45, "Rarita": 30, "Pizadilla": 60},
                "Taco": {"Carne": 13, "Pollo": 13, "Mixto": 13, "Pastor": 13, "Tripa": 13, "Birria": 13, "Lengua": 16,
                         "Campechano": 16},
                "Taco con queso": {"Carne": 16, "Pollo": 16, "Mixto": 16, "Tripa": 16, "Birria": 16, "Pastor": 16,
                                   "Lengua": 20, "Campechano": 20},
                "Burrito": {"Carne": 35, "Pollo": 35, "Mixto": 35, "Tripa": 35, "Birria": 35, "Pastor": 35,
                            "De huevo": 35, "Lengua": 45, "Campechano": 45},
                "Nachos": {"Carne": 48, "Pollo": 48, "Mixto": 48, "Tripa": 48, "Birria": 48, "Pastor": 48, "Lengua": 60,
                           "Campechano": 60},
                "Nacho chingon": {"Carne": 60, "Pollo": 60, "Mixto": 60, "Tripa": 60, "Birria": 60, "Pastor": 60,
                                  "Lengua": 70, "Campechano": 70},
                "Chilaquil tradicional": {"Carne": 45, "Pollo": 45, "Mixto": 45, "Tripa": 45, "Birria": 45,
                                          "Pastor": 45, "Lengua": 55, "Campechano": 55},
                "Chilaquil cremoso": {"Carne": 55, "Pollo": 55, "Mixto": 55, "Tripa": 55, "Birria": 55, "Pastor": 55,
                                      "Lengua": 65, "Campechano": 65},
                "Birriamen": {"Con queso": 35, "Sin queso": 35},
                "Torta prova": {"Normal": 45},
                "Quesabirria": {"Normal": 50},
                "Sopa de tortilla": {"Normal": 35}
            },
            "Extras": {
                "Porc totopos": {"Normal": 20},
                "Porc pico de gallo": {"Normal": 10},
                "Porc frejoles": {"Normal": 10},
                "Consomé": {"Normal": 8},
                "Bolsa totopo grande": {"Normal": 50},
                "Guacamole": {"Normal": 15},
                "Tortillas extras": {"Normal": 2}
            },
            "Bebidas": {
                "Agua": {"Botella": 10},
                "Agua con gas": {"Botella": 10},
                "Coca cola": {"Botella": 10},
                "Coca cola zero": {"Botella": 10},
                "Sprite": {"Botella": 10},
                "Sprite zero": {"Botella": 10},
                "Fanta naranja": {"Botella": 10},
                "Fanta guaraná": {"Botella": 10},
                "Fanta limón": {"Botella": 10},
                "Fanta mandarina": {"Botella": 10},
                "Fanta papaya": {"Botella": 10},
                "Aquarius pera": {"Botella": 10},
                "Aquarius manzana": {"Botella": 10},
                "Del Valle": {"Botella": 10},
                "Corona": {"Botella": 25},
                "Shot tequila": {"Shot": 22}
            },
            "Jugos": {
                "Horchata": {"Vaso": 15},
                "Jamaica": {"Vaso": 15},
                "Tamarindo": {"Vaso": 15},
                "Horchata llevar": {"Botella": 16},
                "Jamaica llevar": {"Botella": 16},
                "Tamarindo llevar": {"Botella": 16},
                "Horchata llevar 1 litro": {"Botella": 30},
                "Jamaica llevar 1 litro": {"Botella": 30},
                "Tamarindo llevar 1 litro": {"Botella": 30},
                "Jarra mediana horchata": {"Jarra": 30},
                "Jarra grande horchata": {"Jarra": 45},
                "Jarra mediana jamaica": {"Jarra": 30},
                "Jarra grande jamaica": {"Jarra": 45},
                "Jarra mediana tamarindo": {"Jarra": 30},
                "Jarra grande tamarindo": {"Jarra": 45}
            }
        }