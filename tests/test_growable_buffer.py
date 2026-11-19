# -*- coding: utf-8 -*-
"""
Tests for the growable buffer used by the measurement loops.

Run with:  pytest tests/test_growable_buffer.py
"""

import numpy as np
import pytest

from nanomol.utils.growable_buffer import growable_buffer


def test_starts_empty():
    buffer = growable_buffer(['a', 'b'], initial_capacity=4)
    assert len(buffer) == 2
    assert buffer.length('a') == 0
    assert buffer['a'].size == 0


def test_append_and_read():
    buffer = growable_buffer(['a'], initial_capacity=4)
    for i in range(3):
        buffer.append('a', i * 1.5)
    assert buffer.length('a') == 3
    assert np.array_equal(buffer['a'], np.array([0.0, 1.5, 3.0]))
    assert buffer['a'].dtype == float


def test_grows_past_initial_capacity():
    buffer = growable_buffer(['a'], initial_capacity=4)
    for i in range(100):
        buffer.append('a', i)
    assert buffer.length('a') == 100
    assert np.array_equal(buffer['a'], np.arange(100, dtype=float))


def test_growth_preserves_the_data():
    buffer = growable_buffer(['a'], initial_capacity=2)
    for i in range(10):
        buffer.append('a', i)
        # the values already stored must stay intact at every step
        assert np.array_equal(buffer['a'], np.arange(i + 1, dtype=float))


def test_several_datasets_grow_independently():
    buffer = growable_buffer(['x', 'y'], initial_capacity=2)
    for i in range(10):
        buffer.append('x', i)
        buffer.append('y', i * 2)
    assert np.array_equal(buffer['x'], np.arange(10, dtype=float))
    assert np.array_equal(buffer['y'], np.arange(10, dtype=float) * 2)


def test_items_and_keys():
    buffer = growable_buffer(['x', 'y'])
    buffer.append('x', 1.0)
    items = dict(buffer.items())
    assert set(items) == {'x', 'y'}
    assert items['x'].tolist() == [1.0]
    assert items['y'].size == 0
    assert set(buffer.keys()) == {'x', 'y'}


def test_contains():
    buffer = growable_buffer(['x'])
    assert 'x' in buffer
    assert 'z' not in buffer


def test_setitem_replaces_the_contents():
    buffer = growable_buffer(['x'], initial_capacity=4)
    buffer.append('x', 1.0)
    buffer['x'] = [7.0, 8.0, 9.0]
    assert np.array_equal(buffer['x'], np.array([7.0, 8.0, 9.0]))
    assert buffer.length('x') == 3


def test_setitem_grows_the_buffer():
    buffer = growable_buffer(['x'], initial_capacity=2)
    buffer['x'] = np.arange(50, dtype=float)
    assert np.array_equal(buffer['x'], np.arange(50, dtype=float))
    assert buffer.length('x') == 50


def test_appending_after_setitem_continues():
    buffer = growable_buffer(['x'], initial_capacity=4)
    buffer['x'] = [1.0, 2.0]
    buffer.append('x', 3.0)
    assert np.array_equal(buffer['x'], np.array([1.0, 2.0, 3.0]))


def test_values_returns_a_dict_of_arrays():
    buffer = growable_buffer(['x', 'y'])
    buffer.append('x', 1.0)
    values = buffer.values()
    assert isinstance(values, dict)
    assert values['x'].tolist() == [1.0]


def test_append_is_cheap_for_long_measurements():
    """The whole point of the buffer: appending must not cost more as the data grows."""
    buffer = growable_buffer(['x'], initial_capacity=1024)
    # append 200k points: with a python list plus np.array() on every update this
    # took minutes, with the buffer it takes well under a second
    for i in range(200_000):
        buffer.append('x', i)
    assert buffer.length('x') == 200_000
    assert buffer['x'][-1] == 199_999
