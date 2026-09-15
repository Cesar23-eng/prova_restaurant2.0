# PRÖVA México · Sistema de pedidos

Punto de venta de PRÖVA México (comida mexicana, Santa Cruz de la Sierra): caja en
Windows (PyQt6) y toma de pedidos desde el celular de los meseros por WiFi.

## Instalación (desarrollo)

```bash
pip install -r requirements.txt
python main.py
```

Para compilar el ejecutable:

```bash
pip install -r requirements-dev.txt
pyinstaller main.spec
```

Copia `menu_precios.xlsx` y `prova.png` junto a `dist/main.exe`.

## Diseño

La interfaz usa la identidad de la marca: el negro del logo y del techo del local,
el rojo de los labios para las acciones principales, el rosa de la firma «México»,
el verde del chile para cobrar, la madera de las mesas para los platos y el turquesa
y rosa de los sombreros para QR y pedidos para llevar. Todos los colores de texto
cumplen contraste WCAG AA.

- **Tema Noche** (predeterminado) y **Tema Día** (concreto claro), con el botón del
  encabezado. Se guarda en `tema_visual` de `config.json`.
- Tipografías de Windows: *Bahnschrift Condensed* para títulos y montos (parecida a la
  letra de PRÖVA) y *Segoe Script* para la firma «México».

## Caja (PC)

La pantalla se divide en tres columnas, como un POS de restaurante:

| Columna | Qué hace |
| --- | --- |
| **Pedidos** | Tarjetas con número, total, minutos de espera (ámbar desde 20 min, rojo desde 40), platillos sin comanda y si lo abrió un mesero |
| **Menú** | Categorías, buscador sin tildes (`Ctrl+K`) y tarjetas de productos: **un toque en la variante agrega** al pedido |
| **Ticket** | Tipo de consumo, plato activo, líneas con − / + y menú ⋯ (nota, mover de plato, quitar), comanda, cuenta y **Cobrar** |

| Acción | Cómo |
| --- | --- |
| Nuevo pedido | **＋ Nuevo pedido** o `Ctrl+N`; botones rápidos *Mesa 1…8* (ajustable con `numero_mesas`) |
| Agregar | Tocar la variante en el menú. Si no hay pedido abierto, pide crearlo. «Cantidad» multiplica el toque |
| Buscar | `Ctrl+K`, escribir y `Enter` agrega si queda un solo resultado; `Esc` limpia |
| Cobrar | **Cobrar** o `F9`. `F1` efectivo, `F2` QR, `F3` mixto; montos rápidos y cambio en grande |
| Comanda de cocina | **🔔 Comanda** o `F8`: imprime solo lo nuevo. ⋯ → reimprimir completa |
| Cuenta del cliente | **🧾 Cuenta** o `Ctrl+P` |
| Cierre de caja | **Resumen del día**: total, efectivo y QR netos, cambio, motos, productos |

Los avisos (agregado, cobrado, mesero envió algo) aparecen abajo sin interrumpir; solo
se pide confirmación para acciones que no se pueden deshacer.

### Platos (emplatado para cocina)

Los tacos se piden por unidad. Si en una mesa dos personas piden tacos, cada
platillo se asigna a un plato para que cocina sepa qué va junto:

- **Caja:** la barra **PLATO 1 · 2 · ＋ · Sin plato** del ticket indica a qué plato va
  lo que se toca en el menú. Cada línea se puede mover de plato con ⋯, y
  ⋯ → *Repartir en platos* permite dividir (ej. de 5 tacos al pastor, 2 al Plato 2).
- **Celular:** la misma barra está en el menú; en el carrito cada línea tiene su
  selector de plato.
- **Comanda de cocina:** sale agrupada (`== PLATO 1 ==`, `== PLATO 2 ==`). Si se agregan
  platillos a un plato que cocina ya recibió, el encabezado dice *(agregar)*.
- Las categorías de `categorias_sin_plato` en `config.json` (por defecto *Bebidas* y
  *Jugos*) nunca llevan plato. La cuenta del cliente y el Excel suman las líneas sin
  separarlas por plato.

## Meseros desde el celular

1. El celular debe estar en el mismo WiFi que la PC de caja.
2. En el encabezado de la caja, **📱 Meseros** muestra la dirección
   (ej. `http://192.168.0.101:5000`) y el PIN.
3. El mesero abre la dirección, ingresa el PIN una vez y toma pedidos: abre mesas con
   un toque, busca platillos, elige el plato, agrega notas para cocina, ve lo ya
   pedido y envía con el botón inferior. El pedido no se pierde si se recarga la
   página y no se duplica si el WiFi falla al enviar.

La primera vez Windows puede preguntar por el Firewall: permite el acceso en
**redes privadas**. El PIN se genera solo y se puede cambiar desde la caja.

## Datos

Todo se guarda en la carpeta `data/` junto al programa:

| Archivo | Contenido |
| --- | --- |
| `estado_pedidos.json` | Pedidos abiertos. Si se corta la luz o se cierra la app, se recuperan al abrir |
| `AAAA-MM-DD/ventas_AAAA-MM-DD.jsonl` | Registro de cada cobro (fuente de verdad) |
| `AAAA-MM-DD/pedidos_AAAA-MM-DD.xlsx` | Excel del dia: hojas *En el local*, *Para llevar* y *Resumen* |
| `AAAA-MM-DD/audit_log_AAAA-MM-DD.txt` | Auditoria: quien agrego, quito, cobro o elimino |
| `config.json` | Nombre del local, PIN y puerto de meseros, hora de corte, tema visual, número de mesas, categorías sin plato |
| `errores.log` | Errores inesperados (la app no se cierra, avisa y registra) |

- Si el Excel del dia esta abierto al cobrar, la venta igual queda registrada y la
  app avisa; el Excel se actualiza en el siguiente cobro o con **Exportar respaldo**.
- **Jornada:** las ventas antes de `hora_corte_jornada` (4 am por defecto) cuentan
  para el dia anterior, para que un turno que pasa la medianoche no quede partido.
- La numeracion de pedidos reinicia en cada jornada y continua si la app se reinicia
  el mismo dia.
- El menu se lee de `menu_precios.xlsx` (columnas `categoria`, `producto`, `variante`,
  `precio`) y se recarga solo si se edita con la app abierta.

## Tests

```bash
pip install -r requirements-dev.txt
python -m pytest
```
