# -*- coding: utf-8 -*-
"""
Pytest configuration for the nanomol tests.

The package is imported as "nanomol." and it lives in src/, so that folder has
to be on the path when the project has not been installed. This file adds it,
so that the tests run with a plain "pytest" from the root of the repository.
"""

import os
import sys

# this file is in <repo>/tests/, the package "nanomol" is <repo>/src/nanomol
TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(TESTS_DIR)
SRC_DIR = os.path.join(REPO_ROOT, "src")

if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)
