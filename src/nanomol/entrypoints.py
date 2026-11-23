# -*- coding: utf-8 -*-
"""Console entry points for the measurement tools.

The phase that moves the package into ``src/`` does not split the measurement
windows yet: each one keeps its bootstrap in the ``if __name__ == '__main__'``
block of its module. Running that module with ``runpy`` gives the console
script the same behaviour as ``python -m nanomol.experiments.<module>`` and
avoids a second copy of the bootstrap here.

When the domain is extracted into ``services/``, these functions are replaced
by real ``main()`` functions with no Qt dependency.
"""

import runpy


def transfer():
    """Open the transfer curve measurement."""
    runpy.run_module('nanomol.experiments.transistor_transfer', run_name='__main__')


def output():
    """Open the output curve measurement."""
    runpy.run_module('nanomol.experiments.transistor_output_transfer', run_name='__main__')


def timeseries():
    """Open the measurement of current over time."""
    runpy.run_module('nanomol.experiments.current_vs_time', run_name='__main__')
