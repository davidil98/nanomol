# -*- coding: utf-8 -*-
"""
Start menu: single entry point for the nanomol lab instruments.

Created on Tue Nov 17 2026

@author: davidil98

The start menu is the window that a lab member opens. It shows which equipment
is reachable, and opens the tool that is needed. It does not do any measurement
itself: every tool keeps its own window, with its own settings.

Two ways of working are offered:

- script individual: the tools are opened directly, as the __main__ blocks do
- guia de medicion: the tools are opened from a short questionnaire
- por lotes: the sequencer (experiments/experiment_planner.py) runs a sequence

The window follows the conventions of the rest of the repository: the interface
is in start_menu.ui, designed in Qt Designer, and loaded at runtime with
uic.loadUi(). Widgets are accessed by their objectName, so the name of a widget
in the .ui is the name used here.
"""

import os
import sys

from PyQt6 import QtWidgets, uic

# import pyqtgraph AFTER PyQt6: pyqtgraph binds to the Qt library that was
# imported first, and another Qt binding may be installed in the same environment
import pyqtgraph as pg


class start_menu(QtWidgets.QMainWindow):
    """
    Landing window: pick a tool, see what is connected, launch it.

    The window can be used without any instrument connected, so that the
    interface can be tried out without a Keithley on the bench.
    """

    def __init__(self, session=None):
        """
        Parameters
        ----------
        session : LabSession or None, optional
            Registry of the instruments, used to show which ones are reachable.
            None means that no instrument is used and the tools are opened
            without one.
        """
        super().__init__()
        self.session = session
        # windows opened from here have to be kept alive: python would otherwise
        # collect them and they would disappear from the screen
        self._keep = []

        ui_path = os.path.join(os.path.dirname(__file__), 'start_menu.ui')
        uic.loadUi(ui_path, self)

        self.setWindowTitle("nanomol")

        self.transfer_button.clicked.connect(self.open_transfer)
        self.output_button.clicked.connect(self.open_output)
        self.current_vs_time_button.clicked.connect(self.open_timeseries)
        self.more_tools_button.clicked.connect(self.open_more_tools)

        self.mode_script_radioButton.toggled.connect(self.apply_mode)

        self.refresh_status()
        self.apply_mode()

    # ------------------------------------------------------------------ status

    def refresh_status(self):
        """
        Show which instruments are reachable.

        Every instrument is checked on its own: one that does not answer leaves
        its own line saying so, and does not stop the others.
        """
        if self.session is None:
            self.connection_status.setText("Sin conexion: solo interfaz")
            self._set_status(self.status_smu_label, "no configurado")
            self._set_status(self.status_led_label, "no configurado")
            self._set_status(self.status_mux_label, "no configurado")
            return
        for key, label in (('smu', self.status_smu_label),
                            ('led', self.status_led_label),
                            ('mux', self.status_mux_label)):
            try:
                if self.session.available(key):
                    self._set_status(label, "conectado")
                else:
                    self._set_status(label, "no disponible")
            except Exception:
                self._set_status(label, "error al comprobar")

    def _set_status(self, label, state):
        """
        Set the state of an equipment line, keeping the name of the equipment.

        Parameters
        ----------
        label : QLabel
            The label to update.
        state : str
            The state to show: "conectado", "no disponible", ...
        """
        name = label.text().split(':')[0].strip()
        label.setText("{}: {}".format(name, state))

    # -------------------------------------------------------------------- mode

    def apply_mode(self):
        """
        The chosen way of working decides which tools are offered.

        The batch mode does not open the single tools: it runs the sequencer,
        which does the measurements itself.
        """
        if self.mode_batch_radioButton.isChecked():
            self.transfer_button.setEnabled(False)
            self.output_button.setEnabled(False)
            self.current_vs_time_button.setEnabled(False)
        else:
            self.transfer_button.setEnabled(True)
            self.output_button.setEnabled(True)
            self.current_vs_time_button.setEnabled(True)

    # ------------------------------------------------------------------- tools

    def _open(self, window):
        """
        Show a window and keep a reference to it.

        Without the reference python would collect the window and it would
        close as soon as this function returns.
        """
        window.show()
        self._keep.append(window)

    def _smu(self):
        """ The Keithley of the session, or None if there is no session. """
        return self.session.smu() if self.session is not None else None

    def _datafile(self):
        """ The data file of the session, or None if there is no session. """
        return self.session.datafile() if self.session is not None else None

    def open_transfer(self):
        """ Open the transfer curve measurement. """
        from nanomol.experiments.transistor_transfer import transistor_transfer
        self._open(transistor_transfer(self._smu(), datafile=self._datafile()))

    def open_output(self):
        """ Open the output curve measurement. """
        from nanomol.experiments.transistor_output_transfer import transistor_output_transfer
        self._open(transistor_output_transfer(self._datafile(), self._smu()))

    def open_timeseries(self):
        """ Open the measurement of current over time. """
        from nanomol.experiments.current_vs_time import current_vs_time
        self._open(current_vs_time(self._datafile(), self._smu()))

    def open_more_tools(self):
        """
        Show the tools that are not on the main window.

        The LED driver, the shutters and the multiplexer are opened as separate
        windows, because they are used with the measurement windows and not
        instead of them.
        """
        menu = QtWidgets.QMenu(self)
        actions = {}
        for label, name in (('Driver de LED', 'led'),
                            ('Obturadores', 'shutter'),
                            ('Multiplexor', 'mux'),
                            ('Visor de datos HDF5', 'viewer')):
            action = menu.addAction(label)
            action.setEnabled(True)
            actions[action] = name
        chosen = menu.exec(self.cursor().pos())
        if chosen is None:
            return
        name = actions[chosen]
        if name == 'led':
            from nanomol.instruments.keithley_2600_LED_driver import keithley_2600_LED_driver_ui
            smu = self._led_smu()
            if smu is None:
                self.statusBar().showMessage("No hay SMU configurado para el LED")
                return
            self._open(keithley_2600_LED_driver_ui(smu))
        elif name == 'shutter':
            from nanomol.instruments.arduino_shutter_controller import arduino_shutter_controller_ui
            port = self._session_setting('shutter_port')
            if port is None:
                self.statusBar().showMessage("Puerto del obturador no configurado")
                return
            self._open(arduino_shutter_controller_ui(arduino_shutter_controller(port)))
        elif name == 'mux':
            from nanomol.instruments.arduino_multiplexer_3_to_12_12_1 import arduino_multiplexer_3_to_12_12_1_ui
            port = self._session_setting('mux_port')
            if port is None:
                self.statusBar().showMessage("Puerto del multiplexor no configurado")
                return
            self._open(arduino_multiplexer_3_to_12_12_1_ui(arduino_multiplexer_3_to_12_12_1(port)))
        elif name == 'viewer':
            from nanomol.utils.hdf5_viewer import hdf5_viewer
            datafile = self._datafile()
            if datafile is None:
                self.statusBar().showMessage("No hay fichero de datos abierto")
                return
            self._open(hdf5_viewer(datafile))

    def _led_smu(self):
        """ The second Keithley, the one used to drive the LED. """
        if self.session is None:
            return None
        return self.session.led_smu()

    def _session_setting(self, name):
        """ A setting of the session, or None if there is no session. """
        if self.session is None:
            return None
        return self.session.setting(name)


def main():
    """ Entry point of the "nanomol" command. """
    from nanomol.utils.lab_session import LabSession
    app = QtWidgets.QApplication(sys.argv)
    session = LabSession.from_file()
    window = start_menu(session)
    window.show()
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
