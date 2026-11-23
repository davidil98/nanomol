# -*- coding: utf-8 -*-
"""
Created on Tue Nov 17 2026

@author: davidil98

Registry of the instruments of the lab, with lazy connection.

Why this exists
---------------
Every script of the repository created the instruments it needed and hardcoded
their addresses in the __main__ block:

    smu = keithley_2600A('GPIB0::27::INSTR')

That means that the same instrument is described in many places, and that
changing the address of an instrument means editing as many files. It also means
that a script cannot be started without the instrument being there: opening the
VISA resource raises, and the program dies with a traceback instead of a window.

The session holds the addresses in one place, connects to an instrument only when
it is used, and reports which instruments are reachable without raising.
"""

import os

import pyvisa


DEFAULT_CONFIG = {
    # address of the Keithley used to characterise the devices
    'smu_address': 'GPIB0::27::INSTR',
    # address of the second Keithley, the one used to drive the LED
    'led_smu_address': 'GPIB0::26::INSTR',
    # serial port of the Arduino that controls the shutters
    'shutter_port': 'COM7',
    # serial port of the Arduino that controls the relay multiplexer
    'mux_port': 'COM10',
}


class LabSession:
    """
    The instruments of the lab, with lazy connection.

    The session does not open anything on creation. Each instrument is opened
    the first time it is asked for, and the connection is kept for the next
    call. Asking for an instrument that is not there returns None instead of
    raising, so that a window can be opened with the tools that are available.

    Parameters
    ----------
    config : dict, optional
        Addresses of the instruments. The keys are the ones of DEFAULT_CONFIG.
        Missing keys fall back to the default.
    """

    def __init__(self, config=None):
        """
        Parameters
        ----------
        config : dict, optional
            Addresses of the instruments. See the class docstring.
        """
        self.config = dict(DEFAULT_CONFIG)
        if config:
            self.config.update(config)
        self._instruments = {}

    # ---------------------------------------------------------------- settings

    def setting(self, name):
        """
        Value of a setting of the session.

        Parameters
        ----------
        name : str
            Name of the setting, e.g. "shutter_port".

        Returns
        -------
        value or None
            The value, or None if there is no setting with that name.
        """
        return self.config.get(name)

    def set_setting(self, name, value):
        """
        Change a setting of the session.

        Parameters
        ----------
        name : str
            Name of the setting.
        value
            New value.
        """
        self.config[name] = value

    @classmethod
    def from_file(cls, path=None):
        """
        Read the settings from a file.

        The file is a plain "key = value" text file, one setting per line, with
        the lines starting with # as comments.

        Parameters
        ----------
        path : str, optional
            Path of the file. The default is "nanomol_config.txt" next to the
            repository, or in the current folder.

        Returns
        -------
        session : LabSession
        """
        if path is None:
            path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                'nanomol_config.txt')
        config = {}
        if os.path.isfile(path):
            with open(path, encoding='utf-8') as config_file:
                for line in config_file:
                    line = line.strip()
                    if not line or line.startswith('#') or '=' not in line:
                        continue
                    name, _, value = line.partition('=')
                    config[name.strip()] = value.strip()
        return cls(config)

    # ------------------------------------------------------------- instruments

    def _open(self, key, factory):
        """
        Return an instrument, opening it the first time it is asked for.

        Parameters
        ----------
        key : str
            Key under which the instrument is kept.
        factory : callable
            Called with the address of the instrument, returns the instrument.

        Returns
        -------
        instrument or None
            The instrument, or None if it could not be opened.
        """
        if key in self._instruments:
            return self._instruments[key]
        try:
            instrument = factory()
        except Exception:
            # an instrument that does not answer must not stop the rest
            self._instruments[key] = None
            return None
        self._instruments[key] = instrument
        return instrument

    def smu(self):
        """
        The Keithley used to characterise the devices.

        Returns
        -------
        keithley_2600A or None
            The instrument, or None if it could not be opened.
        """
        from nanomol.instruments.keithley_2600A import keithley_2600A
        address = self.config['smu_address']
        return self._open('smu', lambda: keithley_2600A(address))

    def led_smu(self):
        """
        The second Keithley, the one used to drive the LED.

        Returns
        -------
        keithley_2600A or None
            The instrument, or None if it could not be opened.
        """
        from nanomol.instruments.keithley_2600A import keithley_2600A
        address = self.config['led_smu_address']
        return self._open('led_smu', lambda: keithley_2600A(address))

    def shutter_controller(self):
        """
        The Arduino that controls the shutters.

        Returns
        -------
        arduino_shutter_controller or None
            The instrument, or None if it could not be opened.
        """
        from nanomol.instruments.arduino_shutter_controller import arduino_shutter_controller
        port = self.config['shutter_port']
        return self._open('shutter', lambda: arduino_shutter_controller(port))

    def multiplexer(self):
        """
        The Arduino that controls the relay multiplexer.

        Returns
        -------
        arduino_multiplexer_3_to_12_12_1 or None
            The instrument, or None if it could not be opened.
        """
        from nanomol.instruments.arduino_multiplexer_3_to_12_12_1 import arduino_multiplexer_3_to_12_12_1
        port = self.config['mux_port']
        return self._open('mux', lambda: arduino_multiplexer_3_to_12_12_1(port))

    # ------------------------------------------------------------------ status

    def available(self, key):
        """
        Whether an instrument is reachable.

        Parameters
        ----------
        key : str
            Name of the instrument: "smu", "led" or "mux".

        Returns
        -------
        bool
            True if the instrument answered.
        """
        if key == 'smu':
            return self.smu() is not None
        if key == 'led':
            return self.led_smu() is not None
        if key == 'mux':
            return self.multiplexer() is not None
        return False

    # ------------------------------------------------------------------- data

    def datafile(self):
        """
        The data file of the session.

        Returns
        -------
        hdf5_datafile or None
            The file, or None if it could not be opened.
        """
        from nanomol.utils.hdf5_datafile import hdf5_datafile
        return self._open('datafile', lambda: hdf5_datafile(mode='x'))

    # ----------------------------------------------------------------- closing

    def close(self):
        """
        Close every instrument of the session.

        Each one is closed even if closing the previous one failed.
        """
        for key, instrument in self._instruments.items():
            if instrument is None:
                continue
            try:
                instrument.close()
            except Exception:
                pass
        self._instruments = {}

    def list_resources(self):
        """
        The VISA resources that pyvisa can see.

        It is a helper to find out the address of an instrument that is not
        configured yet.

        Returns
        -------
        list of str
            The addresses that pyvisa reports.
        """
        try:
            return pyvisa.ResourceManager().list_resources()
        except Exception:
            return []
