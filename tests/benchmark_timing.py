# -*- coding: utf-8 -*-
"""
Benchmark of the cost of accumulating measurement data and updating the plot.

It compares the approach that was used before the fix (python lists, converted
to a numpy array on every plot update) with the current one (numpy arrays that
grow geometrically), and it measures the wall clock time of a simulated
measurement loop that only does the data handling, without an instrument.

Run with:  python tests/benchmark_timing.py
"""

import os
import sys
import time

import numpy as np

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(TESTS_DIR)
sys.path.insert(0, os.path.dirname(REPO_ROOT))

from nanomol.utils.growable_buffer import growable_buffer


def loop_with_lists(n_points):
    """The old approach: python lists, np.array() on every plot update."""
    data = {'time': [], 'V_GS': [], 'I_GS': [], 'V_DS': [], 'I_DS': []}
    t0 = time.perf_counter()
    for i in range(n_points):
        data['time'].append(i * 0.01)
        data['V_GS'].append(1e-9)
        data['I_GS'].append(1e-9)
        data['V_DS'].append(1e-9)
        data['I_DS'].append(1e-9)
        # what pyqtgraph's setData does with a list
        x = np.array(data['time'])
        y = np.array(data['I_GS'])
    return time.perf_counter() - t0


def loop_with_buffer(n_points):
    """The current approach: numpy arrays that grow geometrically."""
    data = growable_buffer(['time', 'V_GS', 'I_GS', 'V_DS', 'I_DS'])
    t0 = time.perf_counter()
    for i in range(n_points):
        data.append('time', i * 0.01)
        data.append('V_GS', 1e-9)
        data.append('I_GS', 1e-9)
        data.append('V_DS', 1e-9)
        data.append('I_DS', 1e-9)
        # what pyqtgraph's setData does with an array: no copy
        x = data['time']
        y = data['I_GS']
    return time.perf_counter() - t0


def main():
    print("Cost of accumulating the data and updating the plot, no instrument involved.")
    print("The old approach converts the whole history to a numpy array on every update,")
    print("so one iteration costs more as the measurement goes on.\n")
    print(f"{'points':>10} | {'lists + np.array':>18} | {'growable buffer':>16} | {'factor':>8}")
    print("-" * 60)

    for n in (2_000, 5_000, 10_000, 20_000, 50_000):
        lento = loop_with_lists(n)
        rapido = loop_with_buffer(n)
        print(f"{n:>10,} | {lento:>17.3f}s | {rapido:>15.4f}s | {lento / rapido:>7.0f}x")

    print("\nExtrapolation of the old approach, quadratic behaviour:")
    reference = {2_000: loop_with_lists(2_000)}
    for target, label in ((360_000, '1 h at 100 Hz'), (2_160_000, '6 h at 100 Hz')):
        estimated = reference[2_000] * (target / 2_000) ** 2
        print(f"  {label:>16}: {estimated:>10.0f} s of pure data handling")


if __name__ == '__main__':
    main()
