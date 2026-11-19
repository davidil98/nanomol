# -*- coding: utf-8 -*-
"""
Pytest configuration for the nanomol tests.

The package is imported as "nanomol." and, until the project is laid out with
src/ and a pyproject.toml, the folder that contains it has to be on the path.
This file adds it, so that the tests run with a plain "pytest" from the root of
the repository.
"""

import os
import sys

# this file is in <repo>/tests/, the package "nanomol" is <repo>/nanomol
TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(TESTS_DIR)
PACKAGE_PARENT = os.path.dirname(REPO_ROOT)

if PACKAGE_PARENT not in sys.path:
    sys.path.insert(0, PACKAGE_PARENT)
