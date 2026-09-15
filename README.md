# PRÖVA México · Sistema de pedidos

Punto de venta de PRÖVA México (comida mexicana, Santa Cruz de la Sierra): caja en
Windows (PyQt6) y toma de pedidos desde el celular de los meseros por WiFi.

## Instalación (desarrollo)

```bash
pip install -r requirements.txt
python main.py
```

Para abrir la caja **sin ventana de consola**, doble clic en `PROVA.vbs` (puedes crear
un acceso directo en el escritorio). También sirve desde la terminal:

```bash
.venv\Scripts\pythonw.exe main.py
```

Si algo falla con `pythonw`, los errores quedan en `data/errores.log` y la app avisa en pantalla.

## Llevar la caja a la PC del restaurante

La PC del restaurante **no necesita Python**: se lleva un solo ejecutable.

1. Compilar (en la PC de desarrollo, con el `.venv` listo):

   ```bash
   .venv\Scripts\python.exe -m PyInstaller main.spec --noconfirm
   ```

   Genera `dist\PROVA.exe` (un solo archivo, sin consola y con el logo). Usar
   `main.spec` en vez de `pyinstaller --onefile --windowed ...`: el `.spec` ya incluye
   la pantalla de meseros (`templates/`) y el icono; sin eso el celular da error.
2. Copiar a una carpeta de la PC del restaurante, por ejemplo `C:\PROVA\`:
   - `PROVA.exe`
   - `menu_precios.xlsx` (el dueño lo edita para cambiar precios)
   - `prova.png` (logo del encabezado y del celular)

   No copiar la carpeta `data/` de desarrollo: tiene ventas de prueba. La app crea una
   nueva con su propio PIN de meseros. No usar `C:\Program Files`, porque ahí Windows
   no deja escribir las ventas.
3. Clic derecho en `PROVA.exe` → *Enviar a* → *Escritorio (crear acceso directo)*.
4. La primera vez:
   - Windows SmartScreen puede decir «Windows protegió su PC» (el `.exe` no está
     firmado): *Más información* → *Ejecutar de todas formas*.
   - El Firewall pregunta por la red: permitir en **redes privadas** para que entren
     los celulares.
   - Configurar la impresora de comandas como predeterminada.
5. Recomendado: reservar una IP fija para esa PC en el router del local, así la
   dirección que usan los meseros (`http://192.168.x.x:5000`) no cambia.

Para actualizar, se reemplaza solo `PROVA.exe`; la carpeta `data/` (ventas, PIN,
pedidos abiertos) se conserva.

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
| Nuevo pedido | **＋ Nuevo pedido** o `Ctrl+N`; botones rápidos *Mesa 1…13* (ajustable con `numero_mesas`) |
| Agregar | Tocar la variante en el menú. Si no hay pedido abierto, pide crearlo. «Cantidad» multiplica el toque |
| Buscar | `Ctrl+K`, escribir y `Enter` agrega si queda un solo resultado; `Esc` limpia |
| Cobrar | **Cobrar** o `F9`. `F1` efectivo, `F2` QR, `F3` mixto; montos rápidos y cambio en grande |
| Comanda de cocina | **🔔 Comanda** o `F8`: imprime solo lo nuevo. ⋯ → reimprimir completa |
| Cuenta del cliente | **🧾 Cuenta** o `Ctrl+P` |
| Cierre de caja | **Resumen del día**: total, efectivo y QR netos, cambio, motos, productos |

Los avisos (agregado, cobrado, mesero envió algo) aparecen abajo sin interrumpir; solo
se pide confirmación para acciones que no se pueden deshacer.

### Platos (emplatado para cocina)

Los tacos se piden por unidad. Si en una mesa dos personas piden tacos, cada taco
se asigna a un plato para que cocina sepa qué va junto. **Solo *Taco* y *Taco con
queso* llevan plato**; todo lo demás (quesadillas, burritos, bebidas…) va en «Otros».
La lista se cambia con `productos_con_plato` en `config.json`.

- **Caja:** la barra **PLATO 1 · 2 · ＋ · Sin plato** del ticket indica a qué plato van
  los tacos que se tocan en el menú. Cada línea de tacos tiene su botón
  **🍽 Plato N ▾** con dos opciones:
  - *Separar 1 de los N a…*: por ejemplo, de 3 tacos con queso, 1 va al Plato 2 y
    quedan 2 en el Plato 1.
  - *Mover los N a…*: cambia toda la línea de plato.

  ⋯ → *Repartir en platos* permite separar varias unidades a la vez.
- **Celular:** la misma barra está en el menú. En el carrito cada línea de tacos tiene
  su selector de plato y, si hay más de una unidad, el botón **✂ Separar 1**, que manda
  una al siguiente plato.
- **Comanda de cocina:** sale agrupada (`== PLATO 1 ==`, `== PLATO 2 ==`, `== SIN PLATO ==`).
  Si se agregan tacos a un plato que cocina ya recibió, el encabezado dice *(agregar)*.
- La cuenta del cliente y el Excel suman las líneas sin separarlas por plato.

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
| `config.json` | Nombre del local, PIN y puerto de meseros, hora de corte, tema visual, número de mesas, productos que llevan plato |
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
