# Ejecución Segura de Python (NaviBot)

NaviBot puede ejecutar scripts de Python dentro del workspace de cada sesión para resolver tareas numéricas, analizar datos y generar visualizaciones como archivos (PNG/CSV).

## Instalación de dependencias

Para habilitar la ejecución de código con librerías de ciencia de datos, es necesario instalar las dependencias opcionales:

```bash
pip install -r requirements-code-exec.txt
```

Estas librerías (pandas, numpy, matplotlib, seaborn, etc.) deben estar disponibles en el entorno donde se ejecuta NaviBot.

## Cuándo usarlo

- Cálculos matemáticos o científicos que requieran iteración numérica.
- Análisis de datos a partir de CSVs subidos al workspace.
- Generación de gráficos (matplotlib/seaborn) y exportación de imágenes.

## Dónde se ejecuta

- Cada ejecución corre en `workspace/{session_id}/code_exec/{run_id}/`.
- Dentro del código puedes acceder a la raíz del workspace de la sesión con el prefijo `session/`:
  - Ejemplo: `session/uploads/datos.csv`

## API

- `POST /api/execute-code` body:
  - `session_id` (string)
  - `code` (string)
  - `timeout_seconds` (int, default 30)
  - `auto_correct` (bool, default true)
  - `max_attempts` (int, default 3)
- `GET /api/code-results/{session_id}` lista ejecuciones previas.
- `DELETE /api/code-cleanup/{session_id}` limpia `code_exec/` de esa sesión.

## Ejemplos

### Fibonacci (cálculo rápido)
Código:
```python
def fib(n):
    a, b = 0, 1
    out = []
    for _ in range(n):
        out.append(a)
        a, b = b, a + b
    return out

print(fib(15))
```

### Análisis de CSV y gráfico
Supón que subiste `uploads/data.csv`.

```python
import pandas as pd
import matplotlib.pyplot as plt

df = pd.read_csv("session/uploads/data.csv")
df["value"].plot(kind="line")
plt.tight_layout()
plt.savefig("serie.png")
print(df.describe())
```

## Limitaciones y seguridad

- Se aplican controles best-effort (validación por AST/denylist, límites de recursos, timeouts). No equivale a un sandbox a nivel contenedor/VM.
- Se bloquean imports y primitivas peligrosas (p.ej. `os`, `subprocess`, `socket`, `eval/exec`).
- Para máxima seguridad en producción, ejecutar este componente en un contenedor sin red y con un usuario sin privilegios.

