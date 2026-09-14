# PROVA - Sistema de Pedidos

Punto de venta para PROVA (comida mexicana): caja en Windows (PyQt6) y toma de
pedidos desde el celular de los meseros por WiFi.

## Instalacion (desarrollo)

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

## Uso diario

| Accion | Donde |
| --- | --- |
| Nuevo pedido | Boton **Nuevo Pedido** o `Ctrl+N` (se elige *En el local* o *Para llevar*) |
| Agregar platillos | Menu (categoria, platillo, variante, cantidad, nota) o busqueda rapida `Ctrl+K` |
| Cobrar | **Cobrar** o `F9`. En el cobro: `F1` efectivo, `F2` QR, `F3` mixto |
| Comanda de cocina | **Imprimir > Comanda para cocina**: solo imprime lo nuevo desde la ultima comanda |
| Cuenta del cliente | **Imprimir > Cuenta** o `Ctrl+P` |
| Cierre de caja | **Resumen del dia**: efectivo y QR netos, cambio, motos, productos vendidos |

En la lista de mesas, la campana (🔔) indica platillos que todavia no salieron en una comanda.

### Platos (emplatado para cocina)

Los tacos se piden por unidad. Si en una mesa dos personas piden tacos, cada
platillo se asigna a un plato para que cocina sepa que va junto:

- **Caja:** elige el plato en el selector **Plato** junto a la cantidad antes de agregar.
  Al cambiar de mesa queda seleccionado el ultimo plato usado. El boton **Platos**
  permite repartir despues (ej. de 5 tacos al pastor, 2 al Plato 2).
- **Celular:** en el menu, la barra *Plato: 1 2 + Nuevo* indica a que plato va lo que
  se toca; en el carrito cada linea tiene su selector de plato.
- **Comanda de cocina:** sale agrupada (`== PLATO 1 ==`, `== PLATO 2 ==`). Si se agregan
  platillos a un plato que cocina ya recibio, el encabezado dice *(agregar)*.
- Las categorias de `categorias_sin_plato` en `config.json` (por defecto *Bebidas* y
  *Jugos*) nunca llevan plato. La cuenta del cliente y el Excel suman las lineas sin
  separarlas por plato.

### Meseros desde el celular

1. El celular debe estar en el mismo WiFi que la PC de caja.
2. En la barra inferior de la caja, **Acceso meseros / PIN** muestra la direccion
   (ej. `http://192.168.0.101:5000`) y el PIN.
3. El mesero abre la direccion, ingresa el PIN una vez y toma pedidos: puede crear
   mesas, buscar platillos, poner cantidades y notas para cocina y ver lo ya pedido.

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
| `config.json` | Nombre del local, PIN y puerto de meseros, hora de corte, tema, categorias sin plato |
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
