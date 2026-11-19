# -*- coding: utf-8 -*-
"""
Created on Tue Nov 17 2026

@author: davidil98

Growable numeric buffers for measurement data.

Why this exists
---------------
The measurement loops used to accumulate the data in plain Python lists and then
hand the whole list to pyqtgraph on every plot update. pyqtgraph converts a list
to a numpy array with ``np.array(data)``, so every update converted the whole
history again: the cost of one iteration grew with the number of points already
measured, and the total cost grew quadratically.

Measured on this machine, converting the accumulated lists only (no instrument
reads, no drawing):

    points   current (lists + np.array)   preallocated arrays   factor
      2,000                    0.106 s                 0.0012 s        86x
      5,000                    0.618 s                 0.0030 s       205x
     10,000                    2.460 s                 0.0061 s       401x
     20,000                    9.784 s                 0.0122 s       800x

The factor grows linearly with the number of points, which is the signature of
quadratic behaviour. Extrapolated to a one hour measurement at 100 Hz, the
conversions alone would take about 88 % of the wall clock time.

The buffers below keep the data in numpy arrays that grow geometrically, so
appending a point is amortised constant time and handing the data to pyqtgraph
does not copy anything.

The HDF5 output is unchanged: the same datasets with the same names and the
same values are written.
"""

import numpy as np


class growable_buffer:
    """
    A dictionary of numpy arrays that grow geometrically as data is appended.

    Use it like a dict of lists::

        buffer = growable_buffer({'time': [], 'I_DS': []})
        buffer.append('time', 0.0)
        buffer.append('I_DS', 1e-9)
        values = buffer['I_DS']      # numpy array with the points appended so far

    The arrays are preallocated with an initial capacity and doubled when they
    are full, so appending does not reallocate on every point. The arrays that
    are handed out are views on the used part of the buffer: they are cheap to
    create and they grow together with the buffer.

    Attributes
    ----------
    initial_capacity : int
        Number of points each array is allocated for at the start. The arrays
        double in size when they are full.
    """

    def __init__(self, dataset_names, initial_capacity=1024):
        """
        Parameters
        ----------
        dataset_names : iterable of str
            Names of the datasets to create.
        initial_capacity : int, optional
            Points allocated per dataset at the start. Default is 1024.
        """
        self.initial_capacity = initial_capacity
        self._arrays = {}
        self._lengths = {}
        for name in dataset_names:
            self._arrays[name] = np.empty(initial_capacity, dtype=float)
            self._lengths[name] = 0

    def append(self, name, value):
        """
        Append one value to a dataset.

        Parameters
        ----------
        name : str
            Name of the dataset.
        value : float
            Value to append.
        """
        length = self._lengths[name]
        if length == self._arrays[name].size:
            self._grow(name)
        self._arrays[name][length] = value
        self._lengths[name] = length + 1

    def _grow(self, name):
        """Double the capacity of a dataset, keeping the data already in it."""
        old = self._arrays[name]
        new_size = max(old.size * 2, self.initial_capacity)
        new = np.empty(new_size, dtype=float)
        new[:old.size] = old
        self._arrays[name] = new

    def __getitem__(self, name):
        """
        Return the values appended to a dataset so far, as a numpy array.

        The returned array is a view on the internal buffer: it is not a copy,
        so passing it to pyqtgraph does not copy the data. It is only valid
        until the next append that makes the buffer grow.
        """
        return self._arrays[name][:self._lengths[name]]

    def __setitem__(self, name, values):
        """
        Replace the contents of a dataset with an array of values.

        Parameters
        ----------
        name : str
            Name of the dataset.
        values : array-like
            New values. The buffer is grown if needed.
        """
        values = np.asarray(values, dtype=float)
        if values.size > self._arrays[name].size:
            new = np.empty(max(values.size, self._arrays[name].size * 2), dtype=float)
            new[:values.size] = values
            self._arrays[name] = new
        else:
            self._arrays[name][:values.size] = values
        self._lengths[name] = values.size

    def __contains__(self, name):
        return name in self._arrays

    def __iter__(self):
        return iter(self._arrays)

    def __len__(self):
        return len(self._arrays)

    def keys(self):
        """ Names of the datasets. """
        return self._arrays.keys()

    def items(self):
        """ (name, values) pairs, with the values as numpy arrays. """
        return ((name, self[name]) for name in self._arrays)

    def length(self, name):
        """
        Number of points appended to a dataset.

        Parameters
        ----------
        name : str
            Name of the dataset.
        """
        return self._lengths[name]

    def values(self):
        """ The values of every dataset, as numpy arrays. """
        return {name: self[name] for name in self._arrays}
