# Propuesta de redefinición y ordenación de `nanomol`

> Documento de trabajo para la conversación con Dean. El fork `davidil98/nanomol` es
> el banco de pruebas: aquí se mide, se prueba y se demuestra; el repositorio canónico
> sigue siendo `dean-nanomol/nanomol`.

**Fecha:** 2026-11-19 · **Base:** revisión `4536cc9` de `davidil98/nanomol`
**Alcance:** fases 0 a 3 ejecutadas — auditoría, merge de las ramas de Dean,
corrección del coste de las mediciones largas, entorno reproducible y menú de inicio.

> **Estado:** el fork ya contiene la migración a PyQt6, el trabajo de estabilidad de
> Dean, la corrección del coste cuadrático de las mediciones largas, un menú de inicio
> y 31 tests. Este documento describe lo que se ha hecho y lo que queda.

---

## 1. Punto de partida: qué es hoy este repositorio

La primera decisión es de vocabulario, y condiciona todo lo demás.

`nanomol` **no es un programa**. Es un **banco de scripts de control de instrumentación**
que el grupo ha ido usando como *banco de pruebas compartidos* para caracterización
eléctrica y optoelectrónica de transistores (MOSFET, EGOFET, OFET).

Medido sobre el código:

| Capa | Líneas | Naturaleza |
|---|---:|---|
| `experiments/` | 4.290 | Procedimientos de medición, secuenciador y menú de inicio |
| `instruments/` | 2.199 | Adaptadores de hardware (VISA, serie) |
| `utils/` | 911 | Persistencia HDF5, visor, base de widgets, sesión de instrumentos |
| `analysis/` | 113 | Dos funciones de ajuste — **nadie las importa** |
| `tests/` | 694 | 31 tests, sin hardware |
| firmware `.ino` | 873 | Arduino: relés, obturadores, multiplexor |

**El ~96 % del repositorio es adquisición.** El tratamiento de datos de verdad no está
aquí: está en `egofets-toolkit` y `HDF5-Manager`, en repositorios separados, que ya
reverse-engineeraron el formato HDF5 que este repo produce.

Todo el repositorio está ahora en **PyQt6**, con las tres ramas de Dean mergeadas:
la migración a PyQt6 (`5901d6e`), el trabajo de estabilidad escrito con Claude Code
(`e7f29e9`, `525e0e0`, `fc843c3`, `7f5e829`) y el secuenciador de 1.436 líneas
(`experiment_planner.py`).

Tres hechos que explican la fricción actual:

1. **21 scripts con `if __name__ == '__main__'`.** Cada uno cablea sus propias direcciones
   de instrumento en el código (`GPIB0::27`, `COM7`, `USB0::0x05E6...`). Un compañero
   tiene que abrir Spyder, editar un `__main__` a mano y rezar por el instrumento.
2. **No existe un composition root.** La instrumentación se crea y se cablea *dentro* de
   cada script. No hay un sitio único donde decir "este SMU es esta Keithley".
3. **El dominio vive dentro del widget.** Las clases de `experiments/` heredan de
   `QWidget` y contienen a la vez el bucle de medición, el guardado en HDF5 y el
   repintado de plots. Consecuencia directa: **cero tests posibles** sin hardware real.

![Arquitectura actual](docs/diagrams/nanomol-arquitectura-actual.html)

### La accidentabilidad que ya existe y no está documentada

| Hecho | Consecuencia |
|---|---|
| `experiment_launcher.py` comparte **un** `smu` y **un** `datafile` entre `output_transfer` y `current_vs_time`; ambos tienen un botón `shut down` que hace `self.smu.close()` | Pulsar "shut down" en una ventana **mata** la instrumentación de la otra |
| Los bucles de medición de `main` no tienen `try/finally` | Un error a mitad de barrido deja el SMU con `source.output = 1` |
| `visa_instrument` no tiene lock; las UIs se tocan desde el hilo de medición | *Segfaults* y respuestas VISA cruzadas |
| `current_vs_time` escribe `V_GS`/`I_DS`; `transistor_transfer` escribe `measured_V_GS`; `output_transfer` escribe `measured_V1` | **Tres convenciones conviviendo**; el toolkit tuvo que deducir el esquema |
| `transistor_transfer_laser_ON_OFF.py` llama a `self.configure_XY_grid()` y a `self.MCLS1` | **No funciona**: nadie lo ha ejecutado |

La rama `experiment-planner` (no mergeada) ya arregla el `try/finally`, el `lock` de VISA
y los plots cross-thread. **No reescribamos eso: mergearlo.**

---

## 2. La redefinición propuesta

> **nanomol** es el software de control de instrumentación del grupo Nanomol
> (ICMAB-CSIC): acquisition de caracterización eléctrica y optoelectrónica de
> transistores, con un formato de datos común para el análisis posterior.

La consequence operativa es la **regla de reparto**, que debe quedar escrita en el
README y en la política de contribución:

| Va al repo de **instrumentación** | Va al repo de **análisis** |
|---|---|
| Todo lo que habla con un instrumento | Todo lo que lee datos y produce tablas o figuras |
| Todo lo que **escribe** datos | Todo lo que **interpreta** datos |
| El esquema HDF5 (como contrato versionado) | Los informes, figuras y ajustes |
| El firmware Arduino | Los notebooks y apps de exploración |

**El esquema HDF5 es el contrato.** Es el activo más valioso del repo: los `attrs`
guardan los settings del Keithley, el timestamp, el modo de medición y los canales.
Hoy está implícito en el código; debe pasar a ser un módulo `schema.py` versionado
con sus nombres de dataset como constantes.

### Separación deüe repositorios

Ya existe `git.csic.es/nanomol` (visibilidad `internal`), con `egofets-toolkit` dentro.
La propuesta es:

```
git.csic.es/nanomol/
├── nanomol-instrumentation   ← el repo de Dean, migrado y reordenado
├── egofets-toolkit           ← ya existe
├── hdf5-manager              ← mover desde GitHub personal
└── nanomol-desktop           ← releases .exe para el laboratorio
```

El fork `davidil98/nanomol` es el **banco de pruebas**; `git.csic.es/nanomol` es el
**destino**. La razón de fondo: hoy el estado del repo depende de que Dean tenga ganas
de mergear. Eso no es sostenible para infraestructura compartida.

![Árbol de módulos](docs/diagrams/nanomol-arbol-modulos.html)

---

## 3. Estructura propuesta

```
nanomol/
├── pyproject.toml          # instalable: pip install -e .
├── src/nanomol/
│   ├── session.py          # LabSession: registro, conexión perezosa, config
│   ├── config.py           # direcciones de instrumento (editable por el usuario)
│   ├── instruments/        # base.py + keithley, arduino, óptica (sin cambios de API)
│   ├── services/           # DOMINIO, sin import de PyQt. Testeable.
│   │   ├── transfer.py
│   │   ├── output.py
│   │   └── timeseries.py
│   ├── io/
│   │   ├── schema.py       # nombres de dataset como constantes (CONTRATO)
│   │   └── datafile.py     # h5py, sin tkinter
│   └── ui/
│       ├── launcher.py     # pantalla de inicio (QMainWindow)
│       └── *.ui           # colocalizados con su .py
├── firmware/               # los .ino
└── tests/                  # FakeSMU, sin hardware
```

Tres cambios con consecuencias reales:

**a) `src/` + `pyproject.toml`.** Hoy el prefijo `nanomol.` de los imports solo funciona
si el directorio se llama *exactamente* `nanomol` (namespace package PEP 420, sin
`__init__.py`). Lo verifiqué: clonar con otro nombre rompe todos los imports. Con
`pip install -e .` desaparece el hack del PYTHONPATH del README y se abre la puerta al
`.exe`.

**b) `services/` sin PyQt.** La lógica de medición (`run_measurement`, `configure_measurement`,
`save_sweep_attrs`, `save_data`) sale de las clases `QWidget` a clases sin Qt. Esto:
- hace la lógica **testeable** con un SMU falso,
- permite una **segunda GUI** (web/NiceGUI, como tu `HDF5-Manager`) sobre el mismo
  backend,
- hace que el `.exe` sea un cliente thin en vez de un monolito.

**c) `session.py` y `config.py`.** En lugar de `keithley_2600A('GPIB0::27::INSTR')` en
un `__main__`: un registro de instrumentos con **descubrimiento automático**
(`pyvisa.ResourceManager().list_resources()` — que `visa_instrument.__main__` ya usa),
**conexión perezosa** y **manejo de fallo que no crashea**.

---

## 4. La pantalla de inicio (lo que pediste)

No un *wizard*, sino un **dashboard**: las herramientas del lab son independientes y
opcionales (el LED no siempre se usa, el shutter tampoco). Un wizard obligaría a pasar
por "configurar LED" cuando no hay LED. *Sí* hay un mini-wizard **dentro** de cada
herramienta y un wizard de **configuración inicial** (elegir direcciones) que se guarda.

```
        ┌──────────────────────────────────────────────┐
        │  nanomol            [GPIB0::27 ●] [COM7 ○]   │  ← barra de estado
        ├──────────────────────────────────────────────┤
        │   ┌──────────────┐  ┌──────────────┐         │
        │   │  Transfer │  │  Output │         │  ← QMainWindow
        │   │  (V_GS↔I_DS) │  │  (V_DS↔I_DS) │         │    + QDockWidget
        │   └──────────────┘  └──────────────┘         │    para el visor
        │   ┌──────────────┐  ┌──────────────┐         │
        │   │  I vs t      │  │  Más ▾       │         │
        │   └──────────────┘  └──────────────┘         │
        └──────────────────────────────────────────────┘
```

Reglas de la pantalla de inicio:

- **Nunca crashea.** Si un instrumento no responde, el botón queda deshabilitado y la
  barra de estado lo dice. Nada de tracebacks.
- **Los módulos opcionales aparecen solo si el hardware está presente.** Resuelve tu
  caso de "a veces alguien no usa LED".
- **Una sola fuente de verdad para el `datafile`.** Se crea una vez y se comparte; el
  botón `shut down` deja de ser un arma de destruction masivo.

Y una decisión de flujo que hay que tomar explícitamente:

> **Los scripts planos no se eliminan; se conservan como entry points.**
> `pip install -e .` genera `nanomol-transfer`, `nanomol-output`, … y el `__main__` de
> cada módulo sigue funcionando. Un developer prefierirá el script; un compañero
> prefierirá el `.exe`. Ambos chemins llegan al mismo `services/`.

---

## 4bis. Lo que ya está hecho en el fork

Tres cosas que se pueden enseñar con el código delante, no con capturas.

### 4.1. El coste de las mediciones largas (corregido)

El bucle de `current_vs_time` acumulaba los datos en listas de Python y entregaba
todo el historial a pyqtgraph en cada actualización del plot. pyqtgraph convierte
una lista en un array con `np.array()`, así que **cada actualización convertía el
historial entero otra vez**: una iteración costaba más a medida que avanzaba la
medición, y el coste total crecía de forma cuadrática.

Medido en esta máquina, solo la conversión de las listas, sin lecturas de
instrumento ni dibujo:

| Puntos | Listas + `np.array()` | Buffer preasignado | Factor |
|---:|---:|---:|---:|
| 2.000 | 0,125 s | 0,0031 s | 41× |
| 5.000 | 0,795 s | 0,0078 s | 102× |
| 10.000 | 3,113 s | 0,0159 s | 196× |
| 20.000 | 12,251 s | 0,0316 s | 388× |
| 50.000 | 77,595 s | 0,0790 s | 982× |

**El factor se duplica cada vez que se duplica el número de puntos**: esa es la
firma matemática del comportamiento cuadrático. Extrapolado a una hora de
medición a 100 Hz, las conversiones solas se llevarían el 88 % del tiempo.

El síntoma era el que describía un compañero del laboratorio: *la lectura tardaba
un poco más cada vez y el desfase se acumulaba*. Nada parecía estar mal, la
aplicación funcionaba, pero cada vez iba más lenta.

La corrección:
- `utils/growable_buffer.py`: arrays de numpy que crecen de forma geométrica. Añadir
  un punto es de coste constante amortizado, y entregar los datos a pyqtgraph no
  copia nada.
- La marca de tiempo se toma **antes** de las lecturas, para que se refiera al
  momento en que se pidió el valor, y sale de un reloj **monótono**, al que no le
  afecta un ajuste de reloj del sistema durante una medición larga.
- Los plots **reducen los puntos automáticamente** para el dibujo.

**El HDF5 no cambia**: los mismos datasets, con los mismos nombres y los mismos
valores. El benchmark está en `tests/benchmark_timing.py`.

### 4.2. El menú de inicio

`experiments/start_menu.py` y `experiments/start_menu.ui` son la ventana que abre
un compañero del laboratorio. Muestra qué equipos están disponibles y abre la
herramienta que hace falta, **sin necesidad de tener el Keithley conectado** para
probar la interfaz.

Los tres flujos de trabajo:

| Modo | Para quién | Qué hace |
|---|---|---|
| Script individual | El developer | Abre la herramienta directamente, como los `__main__` de siempre |
| Guía de medición | El compañero del lab | Abre la herramienta desde un cuestionario corto |
| Por lotes | Campañas de caracterización | El secuenciador (`experiment_planner.py`) encadena mediciones |

La interfaz está diseñada en **Qt Designer** y se carga en runtime con
`uic.loadUi()`, siguiendo las convenciones del repositorio: los widgets se
acceden por su `objectName`, así que el nombre del widget en el `.ui` es el
mismo que se usa en el `.py`.

### 4.3. La sesión de instrumentos

`utils/lab_session.py` tiene las direcciones de los equipos en **un solo sitio**, y
conecta de forma perezosa: pedir un instrumento que no está devuelve `None` en vez
de lanzar una excepción, de modo que una ventana se puede abrir con las
herramientas que haya disponibles.

El commit `d3aad78` de Dean, del 16 de noviembre, es la mejor prueba de por qué
esto hace falta:

```diff
-smu = keithley_2600A('GPIB0::27::INSTR')
+smu = keithley_2600A('USB0::0x05E6::0x2612::4651966::INSTR')
-multiplexer = arduino_multiplexer_3_to_12_12_1('COM10')
+multiplexer = arduino_multiplexer_3_to_12_12_1('COM4')
```

Dos líneas, porque el banco de medición se reconfiguró. Con la sesión, eso es un
cambio en un fichero de configuración, no en el código.

### 4.4. Entorno reproducible y tests

- `environment.yml` (conda) y `pyproject.toml` (para `pip install -e .`).
- **31 tests** que corren sin hardware:
  - `tests/test_growable_buffer.py` — el buffer.
  - `tests/test_current_vs_time.py` — el bucle de medición con un **Keithley falso**.
  - `tests/test_ui_widget_names.py` — **los nombres de los widgets de los `.ui`
    frente a los `.py` que los usan**. Con esto, un widget renombrado en Designer
    falla el test en vez de reventar la aplicación en el banco.

---

## 5. Plan por fases

Cada fase es un PR independiente sobre el fork, mergeable y demostrable por separado.

| # | Rama | Contenido | Riesgo | Estado |
|---|---|---|---|---|
| **0** | `chore/groundwork` | `.gitignore` real, `LICENSE`, `requirements.txt`/`environment.yml`, README reescrito por capas, `CODEOWNERS` | **cero** | parcial: falta `LICENSE` y `CODEOWNERS` |
| **1** | `fix/hygiene` | Mover/archivar lo muerto: `transistor_transfer_laser_ON_OFF.py` (roto), `tenma_72_2705.py` (sin uso), `relay_interfQT.py` (PySide6 + `sys.exit()` a nivel de módulo); arreglar `fitting.py`; renombrar `throlabs_MCSL1.ui`; unificar los dos multiplexores; mover `analysis/` | bajo | **pendiente** |
| **2** | `chore/safety` | Merge de `experiment-planner` (trae `try/finally`, lock de VISA, plots cross-thread) | medio | **hecho** (`383a041`, `9d7650f`) |
| **2b** | `fix/timing` | Buffer preasignado, reloj monótono, timestamp antes de la lectura, downsampling | bajo | **hecho** (`4536cc9`) |
| **3** | `refactor/led` | Unificar LED / no-LED con colaborador opcional (ver §6) | medio | **pendiente** |
| **4** | `refactor/src-layout` | `src/nanomol/` + entry points. **Desbloquea el `.exe`** | medio, diff grande pero mecánico | parcial: `pyproject.toml` listo, falta mover a `src/` |
| **5** | `refactor/services` | Extraer el dominio a `services/`, sin PyQt. Empezar por `transistor_transfer` | medio | **pendiente** |
| **6** | `docs/schema` | `io/schema.py` + `docs/data_format.md` + tests | bajo | parcial: el documento existe, falta el módulo |
| **7** | `feat/launcher` | Menú de inicio + `LabSession` | medio | **hecho** (`4536cc9`) |
| **8** | `feat/dist` | `pyinstaller.spec`, `.exe`, releases | bajo | **pendiente** |
| **9** | `chore/migrate` | Migración a `git.csic.es/nanomol/`, alta de miembros, política de releases | organizativo | **pendiente** |

**El orden tiene una razón:** 2 antes de 3 y 5, porque la rama del planner arregla el
`try/finally` y el lock, y refactorizar sobre `main` reintroduce los bugs. 4 antes de 5
porque `services/` solo es testeable si el paquete es importable de forma estándar. 5
antes de 8 porque el `.exe` debe consumir `services/`, no lógica duplicada.

---

## 6. El refactor LED / no-LED (en detalle)

Es el duplicado más visible: **292 vs 304 líneas, solo 56 de diferencia.**

```
transistor_output_transfer.py  (292)  ┐  56 líneas de diferencia
transistor_output_transfer_LED.py (304)┘  = un fork, no una extensión
```

Hallazgo clave al comparar los `.ui`: **el `.ui` LED es casi un superconjunto del
no-LED**, pero perdió un control:

| Solo en el `.ui` no-LED | Solo en el `.ui` LED |
|---|---|
| `reset_plot_widgets_pushbutton` | `use_LED_checkBox`, `groupBox_6` |

Es decir: el LED no es "el original + LED", es una **bifurcación que perdió un botón**.
Por eso `current_vs_time_LED.py` no conecta `reset_plot_widgets_pushbutton` y
`current_vs_time.py` sí. Y el `_LED` de `transistor_output_transfer` además cambió el
eje X del plot de `calculated_V2` a `measured_V2` — un cambio de comportamiento
silencioso entre variantes.

**Diseño propuesto** — patrón *null object* + colaborador:

```python
class transistor_output_transfer(interactive_ui):
    def __init__(self, datafile, smu, illumination=None): ...
```

- `illumination` implementa un protocolo mínimo: `.output` (último estado comandado),
  `.i`, `.v`.
- Lo cumple `keithley_2600_LED_driver_ui` **y** mañana un driver de láser → la
  iluminación deja de ser un caso especial.
- Un solo `.ui` = unión, re-añadiendo `reset_plot_widgets_pushbutton`.
- El checkbox `use_LED` se queda como toggle runtime, deshabilitado si no hay
  `illumination`.
- Los nombres de dataset pasan a `io/schema.py` como constantes.

**Dos advertencias que condicionan el orden:**

1. **No refactorizar sobre `main`.** En `main`, `current_vs_time_LED.py` hace
   `self.LED.smu.get_output('a')` desde el hilo de medición → llamada VISA cruzada a
   *otro* SMU sin lock = race. La rama `experiment-planner` ya lo arregla con
   `self.LED.output` (último estado en memoria). Por eso la fase 2 va antes que la 3.
2. **No tocar los nombres de dataset a ciegas.** `LED_output`, `measured_LED_current`,
   `measured_LED_voltage` son un contrato para cualquier script que los lea.
   Recomendación: **mantenerlos idénticos ahora** (cero rotura), documentarlos en
   `schema.py`, y proponer la unificación a genérico (`illumination_*`) como decisión
   explícita en PR aparte.

---

## 7. Lo que falta en el repo (checklist deniejecución)

- [ ] `.gitignore` real: `*.hdf5`, `*.csv`, `.spyderproject`, `__pycache__/`, `*.pyc`
      (hoy solo `__pycache__`; ya se colaron un `test_01.hdf5` y un `.pyc`)
- [ ] `LICENSE` (hoy el repo no tiene ninguna: sin licencia, sin permiso legal de uso)
- [ ] `requirements.txt` o `environment.yml` con versiones fijadas
- [ ] `CONTRIBUTING.md` con la regla de reparto (§2) y el flujo de PR
- [ ] `CODEOWNERS`
- [ ] Tests: al menos `schema.py` round-trip y un `FakeSMU`
- [ ] CI: un job que importe el paquete y corra los tests
- [ ] `docs/data_format.md`: el esquema HDF5, versionado
- [ ] Eliminar las **tres** convenciones de nombres de dataset → una sola

---

## 8. Decisiones abiertas (necesitan tu criterio, Dean)

1. **¿PyQt6 desde el día uno?** La rama `PyQt6-update` ya existe y es limpia. Arrancar
   en PyQt6 evita rehacer después, pero sube el coste del primer PR. *Mi recomendación:
   PyQt6*, porque el `.exe` que queremos ya debería construirse sobre la versión que
   tendrá soporte largo.
2. **¿El visor HDF5 se integra como dock del launcher o se queda aparte?** Si se integra,
   se puede reusar el `pyqt_gui/` de `HDF5-Manager` (hoy un placeholder de 13 líneas con
   el TODO explícito *"drop-in replacement for nanomol's hdf5_viewer"*).
3. **¿Quién mantiene el repo de instrumentación una vez en el grupo?** Hoy es Dean con
   211 de 214 commits.
4. **¿Se migra `HDF5-Manager` a `git.csic.es`?** Está en tu GitHub personal, con licencia
   MIT y releases — es propiedad individual, no del grupo.
5. **¿El `.exe` cubre solo instrumental, o también análisis?** Si queremos que un
   compañero no-dev mida *y* analice, la GUI web sobre los mismos `services/` es una
   segunda frontal del mismo backend. Eso exige la fase 5 antes de la 7.

---

## 9. Cómo presentar esto

1. **El diagrama de arquitectura** (§1) — lo que hay hoy, sin adjetivos.
2. **La tabla de duplicados y de bugs** (§1) — el `.ui` LED que perdió un botón, las
   tres convenciones de nombres, el `shut down` que mata a la otra ventana.
3. **El árbol de módulos** (§2) — el destino de cada pieza.
4. **Los parches, con números** (§4bis) — el benchmark del coste cuadrático es
   verificable en cinco minutos, y el `try/finally` y el lock de VISA ya están
   mergeados. Decir *"esto ya está hecho"* es mucho más fuerte que *"esto convendría"*.
5. **El menú de inicio, en funcionamiento** (§4.2) — la tangible: un compañero del
   laboratorio abre una ventana y ve qué hay conectado.
6. **La migración, con el argumento del `port updates`** (§4.3) — Dean tuvo que tocar
   dos líneas porque cambió el banco de medición. Con la sesión, es un fichero de
   configuración.
7. **Una pregunta concreta, no una propuesta cerrada**: *¿te parece que el repo pase a
   `git.csic.es/nanomol/` con el grupo de gente, y que yo siga las fases 1, 3, 4 y 5 en
   el fork?*

---

## Anexo A · Cómo reproducir esta auditoría

```bash
git clone https://github.com/davidil98/nanomol.git
cd nanomol
git checkout 827189b4

# estructura y volumen
find . -name '*.py' -not -path './.git/*' | xargs wc -l | sort -n
find . -name '*.ino' | xargs wc -l

# duplicación LED
diff experiments/transistor_output_transfer.py experiments/transistor_output_transfer_LED.py
diff <(grep -o 'name="[^"]*"' experiments/transistor_output_transfer.ui | sort -u) \
     <(grep -o 'name="[^"]*"' experiments/transistor_output_transfer_LED.ui | sort -u)

# convenciones de nombres de dataset coexisting
grep -rho "'measured_[A-Za-z0-9_]*'\|'calculated_[A-Za-z0-9_]*'\|'V_[A-Z]*'\|'I_[A-Z]*'" experiments/

# acoplamiento al nombre del directorio
mkdir /tmp/x && cp -r . /tmp/x/otro_nombre && cd /tmp/x \
  && python3 -c "import nanomol"   # ModuleNotFoundError
```

## Anexo B · Bugs concretos citados, con ubicación

| Bug | Ubicación |
|---|---|
| `shut down` cierra recursos compartidos | `experiments/current_vs_time.py:146-148`, `experiments/transistor_output_transfer.py:273-275` |
| Sin `try/finally` en el bucle de medición | `experiments/transistor_transfer.py:94-151` |
| Llamada VISA desde el hilo de medición | `experiments/current_vs_time_LED.py` (rama `main`) vs. `experiment-planner` |
| `'sinudoid'` vs `'sinusoid'` | `analysis/fitting.py:82` vs `104` |
| `a = params` en vez de `params[0]` | `analysis/fitting.py:101`, `108` |
| `sys.exit()` a nivel de módulo | `utils/relay_interfQT.py:84` |
| `.ui` con nombre mal escrito | `instruments/thorlabs_MCLS1.py:113` → `throlabs_MCSL1.ui` |
| `configure_XY_grid()` inexistente | `experiments/transistor_transfer_laser_ON_OFF.py:45` |
| `self.MCLS1` no definido | `experiments/transistor_transfer_laser_ON_OFF.py:66` |
