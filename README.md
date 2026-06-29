# Automatizador de reportes TINI

Base para automatizar reportes diarios en un sistema Win32 antiguo usando `pywinauto`, exportar los archivos y enviarlos por webhook.

## Flujo recomendado

1. Instalar dependencias:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

2. Copiar la configuracion:

```powershell
Copy-Item config.example.yaml config.yaml
```

3. Abrir el sistema TINI manualmente en la computadora que tiene acceso.

4. Inspeccionar ventanas y controles:

```powershell
python -m tini_reports.inspect --output artifacts\inspect
```

5. Completar `config.yaml` con los textos, `control_id`, `class_name` o rutas del arbol reales.

6. Probar un solo reporte:

```powershell
python -m tini_reports.run --config config.yaml --only movimientos_producto --dry-run
```

7. Ejecutar todo:

```powershell
python -m tini_reports.run --config config.yaml
```

## Que trae esta base

- Conexion a ventana existente del sistema por titulo.
- Seleccion de modulos/reportes por arbol Win32 cuando los controles son visibles para UI Automation.
- Fallbacks por texto y por teclado para sistemas PowerBuilder/VB6 con controles dificiles.
- Llenado de fechas diario: por defecto usa ayer como rango cerrado.
- Espera de visor de reporte y exportacion por boton/menu.
- Envio de archivos exportados a un webhook con metadatos.
- Logs y evidencias en `artifacts/`.

## Tarea programada diaria

Editar la ruta de `scripts\run_daily.ps1` si se mueve el proyecto y crear una tarea en el Programador de tareas de Windows que ejecute:

```powershell
powershell.exe -ExecutionPolicy Bypass -File C:\Users\Keybe\Documents\botsacareportes\scripts\run_daily.ps1
```

Conviene programarlo cuando el sistema este abierto o agregar login/apertura del sistema en una etapa posterior.
