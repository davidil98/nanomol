<!--
Borrador del Issue que se publicará en dean-nanomol/nanomol.
No forma parte de la documentación del proyecto: es texto de trabajo.
Revisar y ajustar antes de abrirlo.
-->

# One file, one tool: a small app shell for the lab

## Why I'm writing this

I've been working on a fork of this repo for a few weeks, mostly on the parts
that are hard to change from the outside: how the data file is chosen, how the
measurement windows share instruments, and how the tools are launched. The
first result is already upstream (#2, the quadratic cost of `current_vs_time`).
This issue is the next step, and I'd like to agree on the shape before writing
more code.

The goal is not a rewrite. It's a small shell around the windows you already
have, so that a lab session has a beginning and an end: one file, one tool, and
a clean close. If it works on the bench, I'd be happy to send it as a PR. If it
doesn't, at least we'll have learned where the current design breaks.

The full working document is in Spanish, in the fork's `docs/`; this issue is
the English summary.

## What bites us today, and what I'd do about it

**The file is chosen inside the data file object.** `hdf5_datafile.__init__`
(`utils/hdf5_datafile.py:12-37`) creates a Tk window, hides it, and runs a file
dialog. That means the file doesn't exist until some window asks for it, the
dialog is a separate application window that doesn't belong to the UI, and any
script that wants a datafile has to click through it. Most of the bench
machines are Windows, so the dialog also doesn't look like the rest of the app.
*What I'd do:* make the constructor take a path (`hdf5_datafile(path, mode)`)
and move the choice to a Qt `QFileDialog` in the launcher. The `__main__`
blocks get a small helper so they keep working.

**The file is closed by whoever holds it.** `shutdown()` calls
`self.datafile.close()` in `current_vs_time.py:221`,
`transistor_output_transfer.py:338` and `transistor_transfer.py:472`. Since
`experiment_launcher.py` shares one file between windows, the first "shut down"
leaves the others writing to a closed file.
*What I'd do:* give the file a single owner (the shell). The windows receive it
and never close it. The "shut down" button becomes "stop and release the
instruments", if it stays at all.

**Closing a window doesn't stop the measurement.** Only
`experiment_planner.py` has a `closeEvent`. If you close a measurement window
mid-sweep, the thread keeps running and writes to a file that may already be
gone. It's also the easiest way to leave an output on without noticing.
*What I'd do:* a small contract for the measurement windows (`is_measuring()`,
`stop_and_wait()`) and a close guard: stop, join, turn the outputs off, flush,
close. In that order, and in a `try/finally`.

**Two windows for the same thing.** `transistor_output_transfer` already has
`output` and `transfer` modes (`:251-256`). `transistor_transfer` is a second
implementation of the transfer case, with an extra buffer path that writes a
different set of dataset names. We also have three launchers:
`experiment_launcher`, `experiment_launcher_LED` and the `start_menu` I
prototyped in the fork.
*What I'd do:* keep the two-mode window as "Curves" and leave
`transistor_transfer` only for `transistor_laser_scan` until that one is ported.
The dataset names are a separate decision, because they are the contract with
the analysis repos.

**Imports depend on the folder name.** The `nanomol.` prefix only resolves if
the clone is called `nanomol` and its parent is on `PYTHONPATH`. Clone it as
`nanomol-fork` and every module breaks.
*What I'd do:* `src/nanomol/` and `pip install -e .`. This is already done in
the fork and needs no measurement changes: it's a `git mv`, a `pyproject.toml`
and a few entry points.

## What already works in the fork

The layout and the entry points are in place:

- `pip install -e .` makes `import nanomol` work from any folder and any clone
  name.
- `nanomol` opens the launcher; `nanomol-transfer`, `nanomol-output` and
  `nanomol-timeseries` open the tools directly;
  `python -m nanomol.experiments.<module>` works too.
- The `.ui` and `.ino` files are package data, so the wheel keeps them (19 and
  5). That is what a future `.exe` will need.
- Tests run without hardware: 27 passed, 3 skipped. There were no tests in this
  repo, so the fork adds a fake SMU and a check that the names in the `.ui`
  match the ones the `.py` uses.

The first launcher prototype is also in the fork, and it taught me what not to
do: it keeps every window alive, and its "more tools" menu was never wired
properly. That is why I'd rather replace it than extend it.

Branch: https://github.com/davidil98/nanomol/tree/develop

## What I'd like to build

A single window, with the file in the header and the tools in the central area:

```
no file ──[new / open]──> file open ──[tool]──> tool open ──[start]──> measuring
   ^                          ^                     │                     │
   │                          └────[stop / close]───┴─────────────────────┘
   └──────────────────────[close file]───────────────────────────────────┘
```

The rules are the ones a lab session needs:

- one file at a time, owned by the shell; the tools never close it;
- the file name is always visible; the tool buttons stay disabled until there
  is a file;
- one tool at a time, embedded in a `QStackedWidget`, so the rule is structural
  and not a list of windows to remember;
- to open another file, close the tool first;
- closing stops the thread, joins it, turns the outputs off, flushes and closes;
- a settings dialog for the ports (VISA resources and serial ports) and the
  Keithley channel settings, reusing `keithley_2600A.ui`.

For the first version I'd only include "Curves" (the output/transfer window)
and "I vs t". LED, shutters, multiplexer, planner, laser scan and viewers can
stay as `python -m` entry points until the core is boring and stable.

## How I'd split the work

1. `hdf5_datafile(path, mode)`, without tkinter, with an idempotent close.
2. Qt file dialogs: `.hdf5`, last folder remembered, a sensible default name.
3. A small `ExperimentSession` that owns the file and the instruments and
   enforces the rules above.
4. The shell: header, stacked pages, settings dialog.
5. The close contract for the measurement windows.
6. Tests with the fake SMU and a temporary HDF5 file.

Each one is small enough to review on its own, and none of them touches the
measurement maths.

## The demo

The acceptance test is a session at the bench, without editing source:

1. open `nanomol`, create a file, see the path in the header;
2. run a transfer curve and stop it in the middle of the sweep;
3. check that the outputs are off at the instrument, not just that the thread
   stopped;
4. switch to I vs t on the same file, run for a minute, stop;
5. close the file and the app;
6. open the file in the HDF5 viewer: both measurements are there and readable;
7. with a tool open, try to open a second file: the app refuses and says what
   to close first.

If all seven pass without a traceback, the shell does its job. That's the demo
I'd like to do with you at the lab.

## Questions

1. **Curves.** Can we keep `transistor_output_transfer` as the single
   output/transfer window, and leave `transistor_transfer` only for
   `transistor_laser_scan` until it's ported?
2. **Schema.** Should we freeze the generic names (`measured_V_GS`,
   `measured_I_DS`, ...) and retire the fixed-name buffer path? It's the
   contract with `egofets-toolkit`, so I'd rather decide it explicitly than by
   accident.
3. **Shell.** One window with a stacked central page, or separate windows
   controlled by the session? I lean towards the first, mostly because the
   tools are already `QWidget`s.
