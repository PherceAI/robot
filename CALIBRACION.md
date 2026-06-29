# Calibracion en la computadora del sistema TINI

Los `handle` de Windows son utiles para diagnostico, pero normalmente cambian cuando se cierra y abre la aplicacion. Para dejar la automatizacion estable, captura y usa esta combinacion:

- `title` o `title_re` de la ventana.
- `class_name` del control.
- `control_id` si existe.
- Texto visible del control.
- Orden del control dentro de la ventana cuando no haya identificadores mejores.

## 1. Capturar toda la ventana

Con TINI abierto:

```powershell
python -m tini_reports.inspect --output artifacts\inspect
```

Esto genera un JSON con ventanas, botones, edits, combos, trees y otros controles detectables.

## 2. Capturar el control bajo el mouse

Coloca el mouse encima de un campo o boton y ejecuta:

```powershell
python -m tini_reports.probe_cursor
```

Tambien puedes hacer una cuenta regresiva para mover el mouse:

```powershell
python -m tini_reports.probe_cursor --delay 5
```

## 3. Primeros reportes identificados por las fotos

### Pendientes de Entrega

Ruta probable:

```text
Control de Inventarios > Reportes > Reportes de Movimientos > Reporte de Pendientes de Entrega
```

Campos:

- `Fecha desde`
- `Fecha hasta`
- Radio: `Ventas Pendientes de Entrega`
- Radio: `Por Comprobante`
- Boton: `Procesar Reporte`

### Movimientos por Producto / Articulo

Ruta probable:

```text
Control de Inventarios > Reportes > Reportes de Movimientos > Movimiento por Articulo
```

Campos:

- `Desde`
- `Hasta`
- Combos en `Todos`: transaccion, equipo, cuenta, proveedor, grupos.
- Bodegas: seleccionar todas.
- Nivel de detalle: `Detalle de Articulos`.
- Boton: `Procesar`.

## 4. Exportacion

El visor de reporte de la foto muestra botones:

- `Excel`
- `Acrobat`
- `PrintDos`

La configuracion actual intenta exportar con `Excel`. Si ese boton abre un dialogo de guardar, el script escribe el archivo en `artifacts/exports`. Si el sistema guarda automaticamente en otra ruta, ajustamos el detector con el nombre real que aparezca en la prueba.
