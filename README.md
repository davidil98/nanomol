# nanomol

Software de control de instrumentación del grupo **Nanomol** (ICMAB-CSIC):
adquisición de caracterización eléctrica y optoelectrónica de transistores
(MOSFET, EGOFET, OFET) sobre Keithley 2600A, con instrumentación auxiliar
(Arduino, láser, plataformas) y un formato de datos HDF5 común.

Este repositorio es un **fork de trabajo** de
[`dean-nanomol/nanomol`](https://github.com/dean-nanomol/nanomol). El código es
el original; lo nuestro vive en `develop`.

## Ramas

| Rama | Contenido |
|---|---|
| `main` | El código original, más este README y la licencia. Sin cambios de código |
| `develop` | Nuestro trabajo: menú de inicio, estructura `src/`, tests y distribución |

> Para usar el software en el laboratorio, clona el repositorio original: las
> instrucciones de instalación y uso están en
> [su README](https://github.com/dean-nanomol/nanomol#readme). `main` es un
> espejo y no las repite.

## Punto de partida

| | |
|---|---|
| Repositorio | `dean-nanomol/nanomol` |
| Rama | `experiment-planner` |
| Commit | `bfd1141` (2026-11-19) |
| Sincronizado | 2026-11-23 |

Para traer los cambios del original:

```bash
git remote add upstream https://github.com/dean-nanomol/nanomol.git   # una vez
git fetch upstream
git merge upstream/experiment-planner
```

## Qué proponemos

Reorganizar el repositorio para que se pueda instalar y distribuir sin depender
de un `PYTHONPATH` configurado a mano:

- `src/nanomol/` como paquete instalable, **sin cambiar los imports actuales**
- un menú de inicio que reúna las herramientas en un solo sitio
- tests que corren sin hardware
- un `.exe` con releases para los puestos del laboratorio

La propuesta completa, con las fases y su estado, está en
[`develop:docs/PROPUESTA-ORDENACION.md`](https://github.com/davidil98/nanomol/blob/develop/docs/PROPUESTA-ORDENACION.md).

## Licencia

MIT — ver [`LICENSE`](LICENSE). Es una propuesta, pendiente de confirmación del
grupo.
