# AGENTS.md

Instrucciones para agentes de IA que trabajen en este repositorio.

## Contexto

`nanomol` es el software de **control de instrumentación** del grupo Nanomol
(ICMAB-CSIC): adquisición de caracterización eléctrica y optoelectrónica de
transistores (MOSFET, EGOFET, OFET) sobre Keithley 2600A, con instrumentación auxiliar
(Arduino, láser, plataformas) y un formato de datos HDF5 común.

**No es una app de escritorio todavía.** Es un banco de scripts y drivers. El objetivo
en curso es convertirlo en un producto distribuible (`.exe` con releases) sin romper
el hardware ni el formato de datos.

Contexto completo y plan de trabajo: [`docs/PROPUESTA-ORDENACION.md`](docs/PROPUESTA-ORDENACION.md).

## Mapa del repositorio

| Ruta | Contenido |
|---|---|
| `instruments/` | Adaptadores de hardware. `visa_instrument.py` y `serial_instrument.py` son las bases. |
| `experiments/` | Procedimientos de medición. Hoy heredan de `QWidget`. |
| `utils/` | `hdf5_datafile.py` (subclase de `h5py.File`), `hdf5_viewer.py`, `interactive_ui.py`. |
| `analysis/` | Helpers de ajuste. Huérfanos: nadie los importa. |
| `instruments/arduino/` | Firmware `.ino`. Se despliega en las placas, no se importa. |
| `docs/` | Propuesta de ordenación. |
| `.archify/` | Artefactos de diagrama (HTML autocontenido). |

## Reglas del dominio

**El esquema HDF5 es el contrato.** Es el activo más valioso del repo y lo consumen
repositorios externos (`egofets-toolkit`, `HDF5-Manager`).

- Estructura: grupo raíz → `curve_NNN` por curva → datasets + `attrs`.
- Los `attrs` guardan provenance: `description`, `measurement_mode`, `timestamp`,
  `GS_channel`, `DS_channel`, `smu_interaction_mode` y `keithley_*` (settings del SMU).
- **No renombres datasets ni `attrs` sin actualizar `io/schema.py` y
  `docs/data_format.md` en el mismo PR.** Un cambio de nombre rompe el análisis
  aguas abajo de forma silenciosa.
- Hoy conviven **tres** convenciones de nombres (`V_GS`/`I_GS` en `current_vs_time`,
  `measured_V_GS` en `transistor_transfer`, `measured_V1` en `output_transfer`).
  No añadas una cuarta.

**El hardware no es simulable por suposición.** Para tests, usa un doble
(`FakeSMU`) que implemente la interfaz de `keithley_2600A`. Nunca hables con un
instrumento real durante un test.

**La instrumentación se comparte, no se duplica.** En `main`, `experiment_launcher.py`
comparte un único `smu` y un único `datafile` entre varias ventanas. Por eso:

- **No añadas un `close()` o `shutdown()` que cierre recursos compartidos.** Ese bug ya
  existe (`current_vs_time.shutdown()` mata el SMU de `output_transfer`): un `shut down`
  en una ventana deja la otra sin instrumentación.
- **Nunca cables direcciones de instrumento dentro de un widget o un `__main__`.** Las
  direcciones van en `config.py` / `session.py`.
- **Conecta de forma perezosa y no crashees.** Si un instrumento no responde, deshabilita
  el módulo y reporta el estado; nada de tracebacks.

**La seguridad del instrumento importa físicamente.** Un error a mitad de un barrido no
debe dejar la salida del SMU encendida. Todo bucle de medición va en `try/finally` y
apaga las salidas en el `finally`. La rama `experiment-planner` ya trae este patrón:
aplícalo, no lo reescribas.

**Los hilos.** En Qt, los widgets solo se tocan desde el hilo principal. Para
actualizar una UI desde un hilo de medición, emite una señal (`pyqtSignal`) y conecta
el slot en el hilo principal. La rama `experiment-planner` ya lo hace así. Además,
`visa_instrument` necesita un lock: dos hilos no deben leer la respuesta de la consulta
del otro.

## Convenciones de código

**El `.ui` se carga en runtime, no se compila a `.py`.** `uic.loadUi(path, self)`. Se
mantiene el `.ui` como fuente de verdad del layout y el `.py` como fuente de verdad del
comportamiento. No generes `.py` con `pyuic5` y no lo comitees.

**El nombre del widget es la API.** `interactive_ui.connect_widgets_by_name()` recorre
los widgets y, por convención, crea un atributo Python con el nombre sin el sufijo de
tipo:

| Nombre en el `.ui` | Atributo Python |
|---|---|
| `V_DS_min_transfer_doubleSpinBox` | `self.V_DS_min_transfer` |
| `description_lineEdit` | `self.description` |
| `ch_GS_comboBox` | `self.ch_GS` |

Si renuncias un widget en Qt Designer, **rompes el código en silencio**. Si añades uno,
usa el sufijo correcto (`_doubleSpinBox`, `_spinBox`, `_lineEdit`, `_combobox`).
Solo se auto-enlazan esos cuatro tipos.

**Los `.ui` van junto a su `.py`.** Es intencionado: el layout y el comportamiento se
editan en el mismo sitio.

**El prefijo de import es `nanomol.`** y el directorio debe llamarse `nanomol`
(namespace package PEP 420, sin `__init__.py`). Esto es frágil y se arregla en la fase
`refactor/src-layout`; hasta entonces, no lo rompas.

**Comentarios y docstrings en inglés**, siguiendo lo que ya hay. Comentarios que
expliquen *por qué*, no *qué*.

## Antes de abrir un PR

1. `git log --oneline -10` para ver el estilo de mensajes en curso.
2. Lee `docs/PROPUESTA-ORDENACION.md` y comprueba a qué fase pertenece tu cambio.
3. Un PR = un cambio. Los de refactor mechanical (mover código, renombrar) y los de
   comportamiento (cambiar la lógica de medición) **no se mezclan**.
4. Si tocas el esquema HDF5, actualiza `io/schema.py` y `docs/data_format.md` en el
   mismo PR.
5. Si añades un driver de instrumento, hereda de `visa_instrument` o `serial_instrument`
   y no abras el puerto en el `__init__` de la clase de UI.

## Errores conocidos en `main`

No los reintroduzcas. La rama `experiment-planner` (sin mergear) corrige varios.

| Error | Dónde |
|---|---|
| `shutdown()` cierra `smu`/`datafile` compartidos | `experiments/current_vs_time.py`, `experiments/transistor_output_transfer.py` |
| Sin `try/finally` en el bucle de medición | `experiments/transistor_transfer.py` |
| Llamada VISA cruzada entre hilos | `experiments/current_vs_time_LED.py` |
| `'sinudoid'` vs `'sinusoid'` | `analysis/fitting.py` |
| `a = params` en vez de `params[0]` | `analysis/fitting.py` |
| `sys.exit()` a nivel de módulo | `utils/relay_interfQT.py` |
| `.ui` con nombre mal escrito | `thorlabs_MCLS1.py` → `throlabs_MCSL1.ui` |
| `configure_XY_grid()` y `self.MCLS1` inexistentes | `experiments/transistor_transfer_laser_ON_OFF.py` |

## Fuera de alcance

- **No añadas dependencias sin fijarlas** en `requirements.txt` / `environment.yml`.
- **No migres nada a `git.csic.es` sin acuerdo explícito.** El grupo de destino existe
  (`nanomol`, visibilidad `internal`) y es la propuesta a largo plazo, pero la
  migración es una fase acordada, no un efecto secundario de un PR.
- **No borres `instruments/arduino/*.ino`.** Son firmware que se despliega en placas
  reales; no son código Python muerto aunque no se importen.
