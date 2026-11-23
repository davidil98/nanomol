# -*- coding: utf-8 -*-
"""Start the nanomol window with ``python -m nanomol``.

The same function backs the ``nanomol`` console script, so both launchers open
exactly the same window.
"""

from nanomol.experiments.start_menu import main

if __name__ == '__main__':
    main()
