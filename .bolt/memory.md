# Project memory

## Product intent & audience

- **AutoSemilla**: motor/automatizador escrito en Python (solo biblioteca estándar) para generar y evaluar candidatos sobre benchmarks.
- El usuario quiere ejecutar el motor localmente mediante una interfaz de Jupyter Notebook sin depender de clones externos (p. ej. Kaggle).
- Audiencia: desarrollador/usuario técnico que usa Jupyter localmente para experimentar con el motor.

## Brand personality & voice

- Comunicación técnica y directa en español.
- Explicaciones concisas; se informa claramente cuando algo es una aproximación (p. ej. puntuaciones proxy vs. oficiales).

## Visual design & UX direction

- Interfaz basada en Jupyter Notebook tradicional (celdas Markdown + código).
- Flujo guiado por celdas: selección de benchmark → configuración (candidatos, exploración) → ejecución → visualización de mejores resultados e historial.
- Ingesta de resultados de Kickmix y exportación de punto de control disponibles desde el notebook.
- Resultados/persistencia en carpeta local `state/`.

## Decisions, constraints & rationale

- Motor en Python con **solo stdlib**; no se introducen dependencias externas en el núcleo.
- Notebook creado en `notebooks/AutoSemilla_Local.ipynb`; ejecuta contra el código real del proyecto, no clona repositorios.
- Requisitos: Python 3.10+ y Jupyter (`pip install notebook`), lanzar con `jupyter notebook` desde la raíz del proyecto.
- Las puntuaciones mostradas son **proxy**, no la puntuación oficial de la competición.
- Se validó el notebook como JSON válido y se probó con simulación de IPython.

## Open questions & assumptions

- Se asume que el código del motor ya existe en el proyecto y es importable desde el notebook.
- Se asume que los resultados de Kickmix pueden existir opcionalmente en el entorno local.
- Pendiente: confirmar si se necesita integración real con Jupyter/IPython (kernel) frente a la simulación usada para pruebas.
- Pendiente: definir si se quieren visualizaciones más ricas (gráficas) además del historial textual/tabular.