# -*- coding: utf-8 -*-
"""
Check that the names of the widgets in the .ui files match what the .py files use.

A widget renamed in Qt Designer leaves the .py pointing to an attribute that no
longer exists. Nothing warns about it: the python file still compiles, and the
program only fails when that line is reached, which for a measurement window
means in front of the user, on the bench.

This test turns that into a failure of the test suite instead.

How it works
------------
The .ui file says which widgets exist. The python file says which attributes it
reads on self. An attribute that is read but is neither a widget of the .ui nor
something the class has (a method, an attribute it sets itself, a method of a
base class) is a name that does not exist any more.

To know what the class has, the module is imported and its classes are
inspected, so that the methods inherited from the base classes and from Qt
itself are taken into account.

Run with:  pytest tests/test_ui_widget_names.py
"""

import ast
import importlib
import inspect
import os
import sys
import xml.etree.ElementTree as ElementTree

import pytest

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(TESTS_DIR)

# the package is imported as "nanomol.", so the folder that contains it has to
# be on the path; conftest.py does the same when the tests run
if os.path.dirname(REPO_ROOT) not in sys.path:
    sys.path.insert(0, os.path.dirname(REPO_ROOT))

# folders that hold the .ui files and the python files that use them
UI_FOLDERS = ['experiments', 'instruments', 'utils']

# Files that are known to be broken and are scheduled to be removed in the
# hygiene phase. They are listed here so that the test suite stays green while
# the problem is still visible, and so that the exclusion is deliberate.
KNOWN_BROKEN = {
    'transistor_transfer_laser_ON_OFF.ui': (
        'the python file is a copy of transistor_laser_scan.py and uses its '
        'members (MCLS1, stage_X, configure_XY_grid), but it comes with a '
        'different .ui file that does not have those widgets. The file does not '
        'run and is to be removed in the hygiene phase.'
    ),
}

# suffixes that the convention of the repository adds to the name of a widget
TYPE_SUFFIXES = ['_doubleSpinBox', '_spinBox', '_lineEdit', '_combobox',
                 '_checkBox', '_pushButton', '_radioButton', '_label',
                 '_groupBox', '_comboBox', '_button']


def ui_files():
    """ Every .ui file of the repository. """
    found = []
    for folder in UI_FOLDERS:
        folder_path = os.path.join(REPO_ROOT, folder)
        if not os.path.isdir(folder_path):
            continue
        for name in sorted(os.listdir(folder_path)):
            if name.endswith('.ui'):
                found.append(os.path.join(folder_path, name))
    return found


def widget_names(ui_path):
    """
    The names of the widgets defined in a .ui file.

    Parameters
    ----------
    ui_path : str
        Path of the .ui file.

    Returns
    -------
    set of str
        The objectName of every widget.
    """
    tree = ElementTree.parse(ui_path)
    names = set()
    # uic turns the widgets and the layouts into attributes of the window
    for element in list(tree.iter('widget')) + list(tree.iter('layout')):
        name = element.get('name')
        if name:
            names.add(name)
    return names


def self_attributes(py_path, assigned_only=False):
    """
    The attributes that a python file uses on self.

    Parameters
    ----------
    py_path : str
        Path of the python file.
    assigned_only : bool, optional
        When True, only the attributes that the file assigns itself are
        returned.

    Returns
    -------
    set of str
        The attribute names.
    """
    with open(py_path, encoding='utf-8') as py_file:
        tree = ast.parse(py_file.read(), filename=py_path)

    read = set()
    assigned = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Attribute):
            continue
        value = node.value
        if not (isinstance(value, ast.Name) and value.id == 'self'):
            continue
        if isinstance(node.ctx, ast.Store):
            assigned.add(node.attr)
        elif isinstance(node.ctx, ast.Load):
            read.add(node.attr)
    return assigned if assigned_only else read


def class_attributes(py_path):
    """
    The names that the classes of a python file have, including inherited ones.

    The module is imported to inspect the real classes, so that the methods of
    the base classes of the project and of Qt are taken into account.

    Parameters
    ----------
    py_path : str
        Path of the python file.

    Returns
    -------
    set of str
        The attribute names available on the classes of the module.
    """
    with open(py_path, encoding='utf-8') as py_file:
        tree = ast.parse(py_file.read(), filename=py_path)

    module_name = 'nanomol.' + os.path.splitext(
        os.path.relpath(py_path, REPO_ROOT))[0].replace(os.sep, '.')

    try:
        module = importlib.import_module(module_name)
    except Exception:
        return set()

    names = set()
    for value in vars(module).values():
        if not isinstance(value, type):
            continue
        # dir() of the class includes the methods it inherits from its base
        # classes, so the methods of the project base classes and of Qt are
        # taken into account
        names.update(dir(value))
        # the attributes that the base classes set on self are instance
        # attributes, they exist whatever the .ui file says
        for base in value.__mro__:
            names.update(instance_attributes(base))
    return names


def instance_attributes(cls):
    """
    The names of the attributes that a class sets on self.

    The source of the class is parsed, so that the attributes set in __init__
    of a base class are found as well.

    Parameters
    ----------
    cls : type
        The class to inspect.

    Returns
    -------
    set of str
        The attribute names.
    """
    try:
        source = inspect.getsource(cls)
    except (OSError, TypeError):
        return set()
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return set()
    names = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Attribute):
            continue
        value = node.value
        if not (isinstance(value, ast.Name) and value.id == 'self'):
            continue
        if isinstance(node.ctx, ast.Store):
            names.add(node.attr)
    return names


def looks_like_a_widget(name, in_ui):
    """
    Whether an attribute looks like a widget of the .ui file.

    An attribute looks like a widget when the .ui file has a widget with that
    name, or when it has one whose name is the attribute plus the suffix of the
    widget type, which is the convention of the repository.

    Parameters
    ----------
    name : str
        Name of the attribute.
    in_ui : set of str
        The widget names of the .ui file.

    Returns
    -------
    bool
    """
    if name in in_ui:
        return True
    # the convention of the repository uses "spinbox" and "spinBox" in different
    # places, so the comparison does not care about the case
    lower_ui = {widget.lower() for widget in in_ui}
    return any((name + suffix).lower() in lower_ui for suffix in TYPE_SUFFIXES)


def corresponding_py(ui_path):
    """
    The python file that goes with a .ui file.

    Parameters
    ----------
    ui_path : str
        Path of the .ui file.

    Returns
    -------
    str or None
        Path of the .py file, or None if there is none with the same name.
    """
    py_path = os.path.splitext(ui_path)[0] + '.py'
    return py_path if os.path.isfile(py_path) else None


@pytest.mark.parametrize('ui_path', ui_files(), ids=lambda p: os.path.basename(p))
def test_ui_widget_names_match_the_python_file(ui_path):
    """
    Every widget that the python file reads has to exist in the .ui file.

    A widget renamed in the designer removes it from the .ui and adds it with
    the new name, so the attribute read by the .py no longer exists.
    """
    name = os.path.basename(ui_path)
    if name in KNOWN_BROKEN:
        pytest.skip('known broken file: {}'.format(KNOWN_BROKEN[name]))

    py_path = corresponding_py(ui_path)
    if py_path is None:
        pytest.skip('no python file with the same name')

    in_ui = widget_names(ui_path)
    read = self_attributes(py_path)
    # the attributes that the file sets on self are instance attributes, they
    # exist whatever the .ui file says
    assigned = self_attributes(py_path, assigned_only=True)
    known = class_attributes(py_path) | assigned

    missing = set()
    for name in read:
        if name in in_ui:
            continue
        if looks_like_a_widget(name, in_ui):
            continue
        if name in known:
            continue
        missing.add(name)

    assert not missing, (
        'the python file reads attributes that are neither widgets of the .ui file '
        'nor members of its classes: {}. Either the widget was renamed in the '
        'designer, or the attribute is set by the code in a way that the test '
        'cannot see.'.format(sorted(missing)))
