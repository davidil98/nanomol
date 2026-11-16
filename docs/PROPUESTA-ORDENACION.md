# Propuesta de redefinición y ordenación de `nanomol`

> Documento de trabajo para la conversación con Dean. El fork `davidil98/nanomol` es
> el banco de pruebas: aquí se mide, se prueba y se demuestra; el repositorio canónico
> sigue siendo `dean-nanomol/nanomol`.

**Fecha:** 2026-11-16 · **Base:** revisión `827189b4` de `davidil98/nanomol`
**Alcance:** fase 1 — auditoría de la estructura actual y propuesta de ordenación.

---

## 1. Punto de partida: qué es hoy este repositorio

La primera decisión es de vocabulario, y condiciona todo lo demás.

`nanomol` **no es un programa**. Es un **banco de scripts de control de instrumentación**
que el grupo ha ido usando como *banco de pruebas compartidos* para caracterización
eléctrica y optoelectrónica de transistores (MOSFET, EGOFET, OFET).

Medido sobre el código:

| Capa | Líneas | Naturaleza |
|---|---:|---|
| `instruments/` | 2.107 | Adaptadores de hardware (VISA, serie) |
| `experiments/` | 2.119 | Procedimientos de medición sobre Keithley |
| `utils/` | 462 | Persistencia HDF5, visor, base de widgets |
| `analysis/` | 113 | Dos funciones de ajuste — **nadie las importa** |
| firmware `.ino` | 873 | Arduino: relés, obturadores, multiplexor |

**El ~96 % del repositorio es adquisición.** El tratamiento de datos de verdad no está
aquí: está en `egofets-toolkit` y `HDF5-Manager`, en repositorios separados, que ya
reverse-engineeraron el formato HDF5 que este repo produce.

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

## 5. Plan por fases

Cada fase es un PR independiente sobre el fork, mergeable y demostrable por separado.

| # | Rama | Contenido | Riesgo |
|---|---|---|---|
| **0** | `chore/groundwork` | `.gitignore` real, `LICENSE`, `requirements.txt`/`environment.yml`, README reescrito por capas ("si soy EGOFET" / "si hago fotónica"), `CODEOWNERS` | **cero** |
| **1** | `fix/hygiene` | Mover/archivar lo muerto: `transistor_transfer_laser_ON_OFF.py` (roto), `transistor_output.py` (huérfano), `tenma_72_2705.py` (sin uso), `relay_interfQT.py` (PySide6 + `sys.exit()` a nivel de módulo); arreglar `fitting.py` (`'sinudoid'` vs `'sinusoid'`, `params` vs `params[0]`); renombrar `throlabs_MCSL1.ui`; unificar los dos multiplexores; mover `analysis/` | bajo |
| **2** | `chore/safety` | Merge de `experiment-planner` (trae `try/finally`, lock de VISA, plots cross-thread). **Base obligatoria del resto** | medio |
| **3** | `refactor/led` | Unificar LED / no-LED con colaborador opcional (ver §6) | medio |
| **4** | `refactor/src-layout` | `pyproject.toml` + `src/nanomol/` + entry points. **Desbloquea el `.exe`** | medio, diff grande pero mecánico |
| **5** | `refactor/services` | Extraer el dominio a `services/`, sin PyQt. Empezar por `transistor_transfer` | medio |
| **6** | `docs/schema` | `io/schema.py` + `docs/data_format.md` + tests pytest (round-trip HDF5, parseo del nombre de measurement) | bajo |
| **7** | `feat/launcher` | `LabSession` + pantalla de inicio (QMainWindow + docks) | medio |
| **8** | `feat/dist` | `pyinstaller.spec`, `.exe`, GitHub Releases en el fork | bajo |
| **9** | `chore/migrate` | Migración a `git.csic.es/nanomol/`, alta de miembros, política de releases | organizativo |

**El orden tiene una razón:** 2 antes de 3 y 5, porque la rama del planner arregla el
`try/finally` y el lock, y refactorizar sobre `main` reintroduce los bugs. 4 antes de 5
porque `services/` solo es testeable si el paquete es importable de forma estándar. 5
antes de 7 porque el launcher debe consumir `services/`, no lógica duplicada.

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
4. **La fase 0 primero** — un PR de higiene que se mergea en 5 minutos y demuestra que
   esto va en serio.
5. **Una pregunta concreta, no una propuesta cerrada**: *¿te parece que el repo pase a
   `git.csic.es/nanomol/` con el grupo de gente, y que yo siga las fases 1–3 en el fork?*

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
