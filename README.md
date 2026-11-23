# nanomol

Software de control de instrumentación del grupo Nanomol (ICMAB-CSIC): adquisición de
caracterización eléctrica y optoelectrónica de transistores (MOSFET, EGOFET, OFET) sobre
Keithley 2600A, con instrumentación auxiliar (Arduino, láser, plataformas) y un formato
de datos HDF5 común para el análisis posterior.

> **Estado:** en transición. Hoy es un banco de scripts y drivers; el objetivo en curso es
> convertirlo en un producto distribuible (`.exe` con releases) sin romper el hardware ni
> el formato de datos. El plan de trabajo y la auditoría completa están en
> **[`docs/PROPUESTA-ORDENACION.md`](docs/PROPUESTA-ORDENACION.md)**.
> Las instrucciones para agentes de IA están en [`AGENTS.md`](AGENTS.md).

---

## Qué hay aquí

| Ruta | Contenido |
|---|---|
| `src/nanomol/instruments/` | Adaptadores de hardware. Bases: `visa_instrument.py` (Keithley) y `serial_instrument.py` (Arduino, láser, etapas). |
| `src/nanomol/experiments/` | Procedimientos de medición: transfer, output, I vs tiempo, sus variantes con LED, el secuenciador y el menú de inicio. |
| `src/nanomol/utils/` | `hdf5_datafile.py` (subclase de `h5py.File`), `hdf5_viewer.py` (visor con árbol y plots), `interactive_ui.py` (auto-enlace de widgets), `lab_session.py` (direcciones y conexión perezosa), `growable_buffer.py`. |
| `src/nanomol/analysis/` | Helpers de ajuste de curvas. |
| `src/nanomol/instruments/arduino/` | Firmware (`.ino`) para relés, obturadores y multiplexor. |
| `tests/` | Tests que corren sin hardware: SMU falso, nombres de los `.ui` y buffer. |
| `docs/` | Propuesta de ordenación y formato de datos. |

## Instalación

Requiere Python 3.10+. Las dependencias están en [`pyproject.toml`](pyproject.toml),
que es la única fuente de verdad: `environment.yml` solo crea el intérprete e
instala el proyecto.

```bash
pip install -e .[dev]
```

**`pyvisa` necesita un runtime VISA externo.** En Windows instala
[NI-VISA Runtime](https://www.ni.com/support/download/downloads-item.x?fileid=460417);
sin él, `pyvisa-py` sirve para USB pero no habla GPIB. El Keithley de caracterización
está en GPIB, así que el runtime es obligatorio en ese puesto.

### Con conda (recomendado en el laboratorio)

Desde la raíz del repositorio:

```bash
conda env create -f environment.yml
conda activate nanomol
```

El `environment.yml` fija Python y ejecuta `pip install -e .[dev]` dentro del
entorno, de modo que las dependencias se resuelven una sola vez, desde
`pyproject.toml`. No repitas paquetes en los dos ficheros: si `conda` y `pip`
discrepan en la versión de un paquete, `pip` puede sustituir el de conda.

### Con uv

```bash
uv sync
```

`uv` lee `pyproject.toml` y `uv.lock`. Elige uno de los dos caminos (conda o uv)
por entorno; no apliques los dos resolutores al mismo `site-packages`.

## Dos formas de trabajar

### Si vienes del laboratorio y solo quieres medir

**La puerta de entrada es el menú de inicio.** Muestra qué equipos están disponibles
y abre la herramienta que necesites, sin que haya que editar código:

```bash
nanomol                 # el comando que instala pip install -e .
python -m nanomol       # lo mismo, sin depender del PATH
```

Cada módulo se puede ejecutar por separado. Elige el script según el equipo que
tengas conectado y abre las ventanas que necesites:

```bash
nanomol-transfer                                # curvas de transferencia
nanomol-output                                  # curvas de salida
nanomol-timeseries                              # corriente frente al tiempo

python -m nanomol.experiments.experiment_launcher       # SMU + visor + output/transfer + I vs t
python -m nanomol.experiments.experiment_launcher_LED   # añade el LED (2ª Keithley)
python -m nanomol.instruments.keithley_2600_LED_driver  # solo el driver de LED
python -m nanomol.instruments.arduino_shutter_controller # solo los obturadores
```

Las direcciones de los equipos se configuran en un solo sitio,
[`src/nanomol/utils/lab_session.py`](src/nanomol/utils/lab_session.py), o en un fichero
`nanomol_config.txt` junto al repositorio:

```
# nanomol_config.txt
smu_address = GPIB0::27::INSTR
led_smu_address = GPIB0::26::INSTR
shutter_port = COM7
mux_port = COM10
```

### Si vienes a desarrollar

El paquete se instala en modo editable y se importa con el prefijo `nanomol.`.
No hace falta `PYTHONPATH` ni que la carpeta se llame de una forma concreta:

```bash
pip install -e .[dev]
python -c "from nanomol.instruments.keithley_2600A import keithley_2600A"
```

En Spyder: abre el proyecto en la raíz del repositorio con el entorno `nanomol`
seleccionado. El intérprete del entorno ya tiene el paquete instalado, así que los
imports funcionan sin configurar rutas a mano.

Los puntos de entrada están declarados en `pyproject.toml`: `python -m
nanomol.experiments.<modulo>` funciona desde cualquier carpeta, y el nombre del clon
es indiferente.

### Tests

```bash
pytest tests/ -q
```

No necesitan instrumentación: un Keithley falso (`tests/test_current_vs_time.py`)
corre el bucle de medición completo. Uno de los tests comprueba que los nombres de
los widgets de los `.ui` coinciden con los que usan los `.py`, para que un widget
renombrado en el Designer falle el test en vez de fallar en el banco.

### Editar la interfaz

Las ventanas se diseñan en **Qt Designer** sobre los ficheros `.ui`, que se cargan en
runtime con `uic.loadUi()`. El `.ui` es la fuente de verdad del layout; el `.py`, la del
comportamiento.

**El nombre del widget es la API.** `interactive_ui.connect_widgets_by_name()` crea un
atributo Python por widget, quitando el sufijo de tipo:

| Nombre en el `.ui` | Atributo Python |
|---|---|
| `V_DS_min_transfer_doubleSpinBox` | `self.V_DS_min_transfer` |
| `ch_GS_comboBox` | `self.ch_GS` |

Si renuncias un widget en Designer, rompes el código en silencio. Si añades uno, usa
el sufijo correcto: `_doubleSpinBox`, `_spinBox`, `_lineEdit` o `_combobox`.

## Formato de datos

Las mediciones se guardan en HDF5. Este formato **es el contrato** con el análisis
posterior: los repos de análisis (`egofets-toolkit`, `HDF5-Manager`) lo leen.

```
/                       grupo raíz: una medición
├── description         (attr) texto libre
├── measurement_mode    (attr) "transfer" | "output" | ...
├── timestamp           (attr) ISO-8601 UTC
├── GS_channel          (attr) canal del gate
├── DS_channel          (attr) canal del drain
└── keithley_*          (attr) settings del SMU en el momento de medir
    curve_000           grupo: una curva
    ├── measured_V_GS   dataset
    ├── measured_I_DS   dataset
    └── ...
```

Detalle completo: [`docs/data_format.md`](docs/data_format.md) (en construcción).

Para abrir un fichero: `python -m nanomol.utils.hdf5_viewer` (árbol de grupos + plots) o
`python -m nanomol.utils.hdf5_extractor` (exporta a CSV).

## Análisis

El tratamiento de datos **no vive aquí**. Esta parte está en repositorios separados:

- [`egofets-toolkit`](https://git.csic.es/nanomol/egofets-toolkit) — extracción de
  parámetros de transfer/output, curvas de calibración, informes.
- [`HDF5-Manager`](https://github.com/davidil98/HDF5-Manager) — visor y editor de
  ficheros HDF5.

Aquí solo queda `src/nanomol/analysis/fitting.py`, con dos funciones de ajuste.

## Recursos para aprender

- [Programming scientific instruments in Python — Part 1](https://www.youtube.com/watch?v=XhUGKqORBGM)
- [Part 2](https://www.youtube.com/watch?v=XR8fJh21wLs)
- [Tutorial de h5py](https://docs.h5py.org/en/latest/quick.html)
- [HDF5 para el laboratorio](https://pythonforthelab.com/blog/how-to-use-hdf5-files-in-python/)
