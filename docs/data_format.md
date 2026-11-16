# Formato de datos de nanomol

Las mediciones se guardan en HDF5. Este documento describe el esquema: es el **contrato**
entre el repositorio de instrumentación (que escribe) y los repos de análisis (que leen).

> **Estado:** en construcción. Describe el esquema tal como existe hoy en `main`
> (revisión `827189b4`). La sección 4 documenta las inconsistencias conocidas, que se
> resolverán al extraer `io/schema.py`.

## 1. Principios

Dos principios gobiernan el formato:

1. **Autodescriptivo.** Cada medición lleva en sus `attrs` suficiente información para
   saber cómo se obtuvo: qué instrumento, con qué settings, en qué canal, cuándo.
2. **Estable.** Los nombres de dataset y de atributo son un contrato. Renombrarlos
   rompe el análisis aguas abajo de forma silenciosa: el código que lee simplemente no
   encuentra la clave y devuelve un array vacío o falla más tarde.

## 2. Estructura general

```
/                       raíz del fichero: una medición por grupo de nivel superior
├── description         (attr) texto libre dado en la interfaz
├── measurement_mode    (attr) "transfer" | "output" | ...
├── timestamp           (attr) "%Y-%m-%d %H:%M:%S" en UTC
├── GS_channel          (attr) canal del gate-source
├── DS_channel          (attr) canal del drain-source
├── smu_interaction_mode (attr) "real_time" | "scripted"
├── keithley_*          (attr) uno por setting del SMU (ver §3)
├── curve_000           (grupo) una curva del barrido
│   ├── <datasets>      ver §4
│   ├── V_DS            (attr) valor del setpoint en esta curva
│   └── measurement_counter (attr) índice del ciclo
├── curve_001
└── ...
```

El grupo de nivel superior se nombra con `description` como basename, y si ya existe se
añade un sufijo numérico (`get_unique_group_name`). Lo mismo para `curve_NNN` dentro de
cada barrido (`get_unique_group_name` con basename `curve`).

## 3. Atributos de provenance

Los atributos se escriben con `attrs.create()`. Los del SMU se generan en
`keithley_2600A.get_settings()`:

| Atributo | Origen | Significado |
|---|---|---|
| `description` | interfaz | etiqueta libre de la medición |
| `measurement_mode` | clase de medición | `transfer`, `output`, … |
| `GS_channel` / `DS_channel` | interfaz | canal del Keithley asignado |
| `smu_interaction_mode` | interfaz | `real_time` o `scripted` |
| `keithley_a_function` | SMU | función de fuente del canal a (0 = corriente, 1 = tensión) |
| `keithley_b_function` | SMU | ídem para el canal b |
| `keithley_a_V_source_limit` | SMU | límite de tensión en fuente, canal a (V) |
| `keithley_b_V_source_limit` | SMU | ídem canal b |
| `keithley_a_I_source_limit` | SMU | límite de corriente en fuente, canal a (A) |
| `keithley_b_I_source_limit` | SMU | ídem canal b |
| `keithley_a_V_source_range` | SMU | rango de tensión en fuente, canal a |
| `keithley_b_V_source_range` | SMU | ídem canal b |
| `keithley_a_I_source_range` | SMU | rango de corriente en fuente, canal a |
| `keithley_b_I_source_range` | SMU | ídem canal b |
| `keithley_a_V_measure_range` | SMU | rango de medida de tensión, canal a |
| `keithley_b_V_measure_range` | SMU | ídem canal b |
| `keithley_a_I_measure_range` | SMU | rango de medida de corriente, canal a |
| `keithley_b_I_measure_range` | SMU | ídem canal b |
| `keithley_a_nplc` | SMU | tiempo de integración, canal a (ciclos de red) |
| `keithley_b_nplc` | SMU | ídem canal b |
| `timestamp` | reloj | marca temporal de la curva |

> Estos atributos son el **activo más valioso** del repositorio: permiten reconstruir
> cómo se midió una muestra mucho después, y son la razón por la que el análisis se
> puede automatizar.

## 4. Datasets

### 4.1 Nombres canónicos

| Nombre | Contenido |
|---|---|
| `time` | tiempo relativo al inicio de la curva (s), desplazado a cero |
| `measured_V_GS` | tensión gate-source medida (V) |
| `measured_I_GS` | corriente gate-source medida (A) |
| `measured_V_DS` | tensión drain-source medida (V) |
| `measured_I_DS` | corriente drain-source medida (A) |
| `calculated_V_GS` | tensión gate-source *setpoint* (V) |
| `calculated_V_DS` | tensión drain-source *setpoint* (V) |

La distinción `measured_*` frente a `calculated_*` es el eje del esquema: lo que el
instrumento leyó frente a lo que se le pidió. En un barrido con histéresis no coinciden.

### 4.2 Convenciones que conviven hoy (deuda)

`main` tiene **tres** convenciones de nombres conviviendo. No añadas una cuarta;
unifícalas al extraer `io/schema.py`:

| Convención | Datasets | Aparece en |
|---|---|---|
| Genérica `V1`/`V2` | `measured_V1`, `measured_I1`, `measured_V2`, `measured_I2`, `calculated_V1`, `calculated_V2` | `transistor_output_transfer.py` |
| Canónica `GS`/`DS` | `measured_V_GS`, `measured_I_GS`, `measured_V_DS`, `measured_I_DS`, `calculated_V_GS`, `calculated_V_DS` | `transistor_transfer.py` (modo scripted) |
| Abreviada | `V_GS`, `I_GS`, `V_DS`, `I_DS` | `current_vs_time.py` |

**Recomendación:** la convención canónica `GS`/`DS` es la que ya consume
`egofets-toolkit`. Migrar hacia ella y dejar las otras dos como alias deprecated durante
una transición.

### 4.3 Datasets específicos de LED

Presentes solo si la iluminación está activa:

| Nombre | Contenido |
|---|---|
| `LED_output` | último estado de salida del driver de LED (0/1) |
| `measured_LED_current` | corriente medida en el LED (A) |
| `measured_LED_voltage` | tensión medida en el LED (V) |

> Estos nombres son contrato. Al unificar LED y no-LED, **mantenerlos idénticos** y
> documentarlos en `io/schema.py` antes de considerar un nombre genérico.

### 4.4 Datasets de compliance

`transistor_output_transfer_LED.py` registra además `compliance_V1`/`compliance_V2`
(1 si la fuente está en compliance). En la variante no-LED están comentados. Deben
quedar siempre activos: un punto en compliance indica que el valor medido no es el
setpoint, y es información crítica para interpretar una curva.

## 5. Modo scripted

Cuando `smu_interaction_mode == "scripted"`, el barrido lo ejecuta el propio Keithley
mediante un script TSP, y los datos se leen de sus buffers:

| Nombre | Origen |
|---|---|
| `measured_I_DS` | `smu{n}.nvbuffer1` → readings |
| `measured_V_DS` | `smu{n}.nvbuffer2` → readings |
| `calculated_V_DS` | `smu{n}.nvbuffer1` → sourcevalues |
| `time` | `smu{n}.nvbuffer1` → timestamps |

El modo scripted es más rápido y más preciso, pero no registra `compliance`.

## 6. Lectura

Desde Python:

```python
import h5py

with h5py.File("medicion.hdf5", "r") as f:
    for medicion in f.keys():
        grupo = f[medicion]
        print(medicion, grupo.attrs["measurement_mode"], grupo.attrs["timestamp"])
        for curva in sorted(grupo.keys()):
            c = grupo[curva]
            v_gs = c["measured_V_GS"][:]
            i_ds = c["measured_I_DS"][:]
```

Los visores existentes son `utils/hdf5_viewer.py` (árbol + plots, con modificadores
`log10`, `sqrt`, `abs`) y `utils/hdf5_extractor.py` (exporta a CSV).

En el toolkit de análisis, el lector equivalente es
`readers/keithley_dean.py` en `egofets-toolkit`.

## 7. Reglas para cambios

1. **Renombrar algo es un breaking change.** Actualiza en el mismo commit:
   - `io/schema.py` (constantes de nombres),
   - este documento,
   - el lector de `egofets-toolkit`,
   - los tests de round-trip.
2. **Añadir un dataset es compatible.** No requiere tocar nada más.
3. **No elimines un `attr` de provenance** sin otra fuente para ese dato.
4. **El `timestamp` va en UTC**, no en hora local: los ficheros se comparten entre
   puestos y las zonas horarias del laboratorio son distintas.
