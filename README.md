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

| Carpeta | Contenido |
|---|---|
| `instruments/` | Adaptadores de hardware. Bases: `visa_instrument.py` (Keithley) y `serial_instrument.py` (Arduino, láser, etapas). |
| `experiments/` | Procedimientos de medición: transfer, output, I vs tiempo, y sus variantes con LED. |
| `utils/` | `hdf5_datafile.py` (subclase de `h5py.File`), `hdf5_viewer.py` (visor con árbol y plots), `interactive_ui.py` (auto-enlace de widgets). |
| `analysis/` | Helpers de ajuste de curvas. |
| `instruments/arduino/` | Firmware (`.ino`) para relés, obturadores y multiplexor. |
| `docs/` | Propuesta de ordenación y formato de datos. |

## Instalación

Requiere Python 3.10+ y las dependencias de [`requirements.txt`](requirements.txt):

```bash
pip install -r requirements.txt
```

**`pyvisa` necesita un runtime VISA externo.** En Windows instala
[NI-VISA Runtime](https://www.ni.com/support/download/downloads-item.x?fileid=460417);
sin él, `pyvisa-py` sirve para USB pero no habla GPIB. El Keithley de caracterización
está en GPIB, así que el runtime es obligatorio en ese puesto.

## Dos formas de trabajar

### Si vienes del laboratorio y solo quieres medir

Cada módulo se puede ejecutar por separado. Elige el script según el equipo que
tengas conectado y abre las ventanas que necesites:

```bash
python experiments/experiment_launcher.py      # SMU + visor + output/transfer + I vs t
python experiments/experiment_launcher_LED.py   # añade el LED (2ª Keithley)
python instruments/keithley_2600_LED_driver.py # solo el driver de LED
python instruments/arduino_shutter_controller.py # solo los obturadores
```

La instrumentación (GPIB, puertos serie) va cableada en cada script. Si tu equipo
tiene otras direcciones, edita las constantes al final del fichero.

### Si vienes a desarrollar

El código se importa con el prefijo `nanomol.`, así que el directorio debe llamarse
exactamente `nanomol` y su carpeta padre debe estar en el `PYTHONPATH`:

```bash
export PYTHONPATH=$PWD/..
python -c "from nanomol.instruments.keithley_2600A import keithley_2600A"
```

En Spyder: **Tools → PYTHONPATH manager**, y añade la carpeta *padre* de `nanomol`.
(Esta fragilidad —el nombre de la carpeta importa— se resuelve en la fase
`refactor/src-layout` del plan.)

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

Para abrir un fichero: `python utils/hdf5_viewer.py` (árbol de grupos + plots) o
`python utils/hdf5_extractor.py` (exporta a CSV).

## Análisis

El tratamiento de datos **no vive aquí**. Esta parte está en repositorios separados:

- [`egofets-toolkit`](https://git.csic.es/nanomol/egofets-toolkit) — extracción de
  parámetros de transfer/output, curvas de calibración, informes.
- [`HDF5-Manager`](https://github.com/davidil98/HDF5-Manager) — visor y editor de
  ficheros HDF5.

Aquí solo queda `analysis/fitting.py`, con dos funciones de ajuste.

## Recursos para aprender

- [Programming scientific instruments in Python — Part 1](https://www.youtube.com/watch?v=XhUGKqORBGM)
- [Part 2](https://www.youtube.com/watch?v=XR8fJh21wLs)
- [Tutorial de h5py](https://docs.h5py.org/en/latest/quick.html)
- [HDF5 para el laboratorio](https://pythonforthelab.com/blog/how-to-use-hdf5-files-in-python/)
