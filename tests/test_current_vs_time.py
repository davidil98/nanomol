# -*- coding: utf-8 -*-
"""
Tests of the measurement loop of current_vs_time, with a fake instrument.

The loop is run without any instrument: a fake SMU answers the reads. This
checks that the data is collected, that the timestamps increase, and that the
data ends up in the HDF5 file with the same names as before.

Run with:  pytest tests/test_current_vs_time.py
"""

import os
import sys

import numpy as np
import pytest

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(TESTS_DIR)
if os.path.dirname(REPO_ROOT) not in sys.path:
    sys.path.insert(0, os.path.dirname(REPO_ROOT))

h5py = pytest.importorskip('h5py')
QtWidgets = pytest.importorskip('PyQt6.QtWidgets')

from nanomol.experiments.current_vs_time import current_vs_time


class FakeSMU:
    """
    A Keithley that answers without any hardware.

    It implements the part of the interface of keithley_2600A that the
    measurement loop uses.
    """

    def __init__(self, value=1e-9):
        self.value = value
        self.outputs = {}
        self.levels = {}
        self.measurements = 0

    def set_source_function(self, ch, function):
        pass

    def set_source_level(self, ch, kind, level):
        self.levels[(ch, kind)] = level

    def set_output(self, ch, state):
        self.outputs[ch] = state

    def measure(self, ch, kind):
        self.measurements += 1
        return self.value, self.value

    def get_compliance(self, ch):
        return 0

    def get_settings(self):
        return {'a_nplc': 1.0, 'b_nplc': 1.0}

    def close(self):
        pass


class FakeDatafile:
    """ A data file that keeps the groups in memory. """

    def __init__(self):
        self.groups = {}

    def get_unique_group_name(self, parent, basename='group', max_N=100):
        name = basename
        counter = 0
        while name in self.groups:
            counter += 1
            name = '{}_{:03d}'.format(basename, counter)
        return name

    def create_group(self, name):
        group = FakeGroup(name)
        self.groups[name] = group
        return group

    def flush(self):
        pass

    def close(self):
        pass


class FakeAttrs:
    """ The attributes of a group, with the interface of the h5py one. """

    def __init__(self):
        self.values = {}

    def create(self, name, value=None):
        self.values[name] = value

    def __contains__(self, name):
        return name in self.values

    def __getitem__(self, name):
        return self.values[name]


class FakeGroup:
    """ A group that keeps the datasets in memory. """

    def __init__(self, name):
        self.name = name
        self.datasets = {}
        self.attrs = FakeAttrs()

    def create_dataset(self, name, data=None):
        self.datasets[name] = np.array(data)
        return self.datasets[name]


@pytest.fixture
def app():
    """ A Qt application for the widgets. """
    application = QtWidgets.QApplication.instance()
    if application is None:
        application = QtWidgets.QApplication([])
    return application


def test_measurement_collects_the_data_and_saves_it(app):
    """ The loop reads the instrument and writes the data with the expected names. """
    smu = FakeSMU()
    datafile = FakeDatafile()

    experiment = current_vs_time(datafile, smu)
    experiment.t_limit_doubleSpinBox.setValue(0.2)   # a short measurement
    experiment.description_lineEdit.setText('test')

    experiment.start_measurement()
    experiment.measurement_thread.join(timeout=30)

    assert not experiment.measurement_is_running
    assert smu.measurements > 0

    # the data was saved in a group of the datafile
    assert len(datafile.groups) == 1
    group = list(datafile.groups.values())[0]
    assert set(group.datasets) == {'time', 'V_GS', 'I_GS', 'V_DS', 'I_DS'}
    assert group.attrs['description'] == 'test'

    # the timestamps increase and are not all the same
    times = group.datasets['time']
    # the loop reads both channels, so there is one point per pair of reads
    assert times.size == smu.measurements // 2
    assert np.all(np.diff(times) >= 0)
    # the timestamps are not all the same: the loop does not measure them at once
    assert len(set(times.tolist())) > 1


def test_the_outputs_are_turned_off_at_the_end(app):
    """ The SMU outputs are off when the measurement ends. """
    smu = FakeSMU()
    datafile = FakeDatafile()

    experiment = current_vs_time(datafile, smu)
    experiment.t_limit_doubleSpinBox.setValue(0.1)

    experiment.start_measurement()
    experiment.measurement_thread.join(timeout=30)

    assert all(state == 0 for state in smu.outputs.values())


def test_the_data_is_not_a_python_list(app):
    """
    The data is kept in numpy arrays, so that passing it to the plot does not
    copy the whole history on every update.
    """
    smu = FakeSMU()
    datafile = FakeDatafile()

    experiment = current_vs_time(datafile, smu)
    experiment.t_limit_doubleSpinBox.setValue(0.1)

    experiment.start_measurement()
    experiment.measurement_thread.join(timeout=30)

    assert isinstance(experiment.data['time'], np.ndarray)
    assert isinstance(experiment.data['I_DS'], np.ndarray)
