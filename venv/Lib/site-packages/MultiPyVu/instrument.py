"""
instrument.py is used to hold information about MultiVu.  It has
the various flavors, and can determine which version of MultiVu is installed
on a machine.

Created on Tue May 18 13:14:28 2021

@author: djackson
"""

import logging
import time
from enum import Enum, auto
from os import path
from sys import platform
from typing import Tuple

from .__version import __version__ as mpv_version
from .exceptions import MultiPyVuError, PythoncomImportError
from .project_vars import MIN_PYWIN32_VERSION, PYWIN32_VERSION, SERVER_NAME

if platform == 'win32':
    try:
        import pythoncom
        import win32api
        import win32com.client as win32
        import win32process
    except ImportError:
        raise PythoncomImportError


class InstrumentList(Enum):
    DYNACOOL = auto()
    PPMS = auto()
    VERSALAB = auto()
    MPMS3 = auto()
    OPTICOOL = auto()
    na = auto()


class Instrument():
    """
    This class is used to detect which flavor of MultiVu is installed
    on the computer.  It is also used to return the name of the .exe
    and the class ID, which can be used by win32com.client.

    Parameters
    ----------
    flavor : string, optional
        This is the common name of the MultiVu flavor being used.  If
        it is left blank, then the class finds the installed version
        of MultiVu to know which flavor to use.  The default is ''.
    scaffolding_mode : bool, optional
        This flag puts the class in scaffolding mode, which simulates
        MultiVu.  The default is False.
    run_with_threading : bool, optional
        This flag is used to configure win32com.client to be used in
        a separate thread.  The default is True.
    verbose : bool, optional
        When set to True, the flavor of MultiVu is displayed
        on the command line. The default is False.
    """
    def __init__(self,
                 flavor: str = '',
                 scaffolding_mode: bool = False,
                 run_with_threading: bool = False,
                 verbose: bool = True
                 ):
        # keep track of the number of times Instrument is instantiated
        self.logger = logging.getLogger(SERVER_NAME)
        self.scaffolding_mode = scaffolding_mode
        self.run_with_threading = run_with_threading
        self.verbose = verbose

        if (not self.scaffolding_mode) and (platform == 'win32'):
            if PYWIN32_VERSION < MIN_PYWIN32_VERSION:
                err_msg = f'Must use pywincom version {MIN_PYWIN32_VERSION} '
                err_msg += f'or higher (found version {PYWIN32_VERSION})'
                raise MultiPyVuError(err_msg)

        self.name = ''
        if flavor == '':
            if self.scaffolding_mode:
                err_msg = 'Must choose a MultiVu flavor to run in '
                err_msg += 'scaffolding mode.'
                for f in InstrumentList:
                    err_msg += f'\n\t{f.name}' if f != f.na else ''
                raise MultiPyVuError(err_msg)
        else:
            # If specified, check that it's a allowed flavor; if not,
            # print an error
            found = False
            for instrument in InstrumentList:
                if instrument.name.upper() == flavor.upper():
                    self.name = flavor.upper()
                    found = True
                    break
            if not found:
                err_msg = f'The specified MultiVu flavor, {flavor}, is not '
                err_msg += 'recognized. Please use one of the following:'
                for f in InstrumentList:
                    if f == 'na':
                        continue
                    err_msg += f'\n\t{f}'
                raise MultiPyVuError(err_msg)

        self._got_threaded_win32 = False
        self.exe_name = ''
        self.class_id = ''
        self.mv_id = None
        self.multi_vu = None
        self._connect_to_MultiVu(self.name)

    def _exe_to_common_name(self, exe_name: str) -> str:
        """
        Returns the common name of the MultiVu flavor.

        Parameters:
        -----------
        exe_name : str
            The name of the MultiVu flavor executable.

        Returns:
        --------
        str
            A string of the specific MultiVu flavor .exe
        """
        if exe_name.capitalize() == 'PpmsMvu.exe'.capitalize():
            name = InstrumentList.PPMS.name
        elif exe_name.capitalize() == 'SquidVsm.exe'.capitalize():
            name = InstrumentList.MPMS3.name
        elif exe_name.capitalize() == 'VersaLab.exe'.capitalize():
            name = InstrumentList.VERSALAB.name
        elif exe_name.capitalize() == 'OptiCool.exe'.capitalize():
            name = InstrumentList.OPTICOOL.name
        elif exe_name.capitalize() == 'Dynacool.exe'.capitalize():
            name = InstrumentList.DYNACOOL.name
        else:
            raise ValueError(f'{exe_name} is not a recognized executable name')
        return name

    def _get_class_id(self, inst_name: str) -> str:
        """
        Uses the instrument name to generate the class ID used for pywin32com.

        Parameters:
        -----------
        inst_name : str
            The name of the MultiVu flavor.

        Returns:
        --------
        string
            The MultiVu class ID.  Used for things like opening MultiVu.
        """
        class_id = f'QD.MULTIVU.{inst_name}.1'
        return class_id

    def _connect_to_MultiVu(self, instrument_name: str) -> None:
        """
        Detects the flavor of MultiVu running, and then sets
        the exe and class ID private member variables for
        MultiVu and then initializes the win32comm.

        Parameters:
        -----------
        instrument_name: str
            The expected MultiVu flavor.
        """
        if not self.scaffolding_mode:
            if platform != 'win32':
                err_msg  = 'The server only works on a Windows machine. '
                err_msg += 'However, the server\n'
                err_msg += 'can be tested using the -s flag, along with '
                err_msg += 'specifying \n'
                err_msg += 'the MultiVu flavor.'
                raise MultiPyVuError(err_msg)

            self.name, self.exe_name = self.detect_multivu()
            if (instrument_name == ''
                    or instrument_name == self.name):
                msg = f'Found {self.name} running.'
                self.logger.info(msg)
                msg = f'MultiPyVu Version: {mpv_version}'
                self.logger.debug(msg)
            elif self.name != instrument_name:
                    msg = f'User specified {instrument_name}, but detected '
                    msg += f'{self.name} running. Either leave out a '
                    msg += 'specific MultiVu flavor and use the detected '
                    msg += 'one, or have the specified flavor match the '
                    msg += 'running instance.'
                    raise MultiPyVuError(msg)
            self.class_id = self._get_class_id(self.name)
            self.initialize_multivu_win32com()

    def detect_multivu(self) -> Tuple[str, str]:
        """
        This looks at the processes for a running version of
        MultiVu.  Once it is found, the function returns the a
        tuple with the common name and the executable name.

        Returns:
        --------
        tuple[str, str]
            Returns the (common name, executable name) of the QD instrument.

        Raises:
        -------
        MultiVuExeException
            This is thrown if MultiVu is not running, or if multiple
            instances of MultiVu are running and the user did not specify
            which one to use.
        """
        # Build a list of enum, instrumentType
        instrument_names = list(InstrumentList)
        # Remove the last item (called na)
        instrument_names.pop()

        # declare these variables so that they are available to return
        common_name = ''
        exe_name = ''
        open_mv_dict = {}

        # Find processes with 'MultiVu' in the name and make
        # a dictionary whose key is the MultiVu flavor, and the
        # value is a tuple with the exe path and process id
        pids = win32process.EnumProcesses()
        for pid in pids:
            try:
                # Open processes to query its executable path
                h_process = win32api.OpenProcess(0x0410, False, pid)
                exe_path = win32process.GetModuleFileNameEx(h_process, 0)
                win32api.CloseHandle(h_process)

                # Check if the path contains the keyword
                if 'multivu' in exe_path.lower():
                    exe_name = path.basename(exe_path)
                    common_name = self._exe_to_common_name(exe_name)
                    open_mv_dict[common_name] = (exe_path, exe_name)
            except Exception:
                # Ignore processes that we don't have access to
                pass

        # Declare errors if no MultiVu instance is found
        if len(open_mv_dict) == 0:
            err_msg  = 'No running instance of MultiVu was detected. Please\n'
            err_msg += 'start MultiVu and retry, or call this script using\n'
            err_msg += 'scaffolding (-s ppms, for example).'
            raise MultiPyVuError(err_msg)
        elif len(open_mv_dict) == 1:
            common_name = list(open_mv_dict.keys())[0]
        elif len(open_mv_dict) > 1:
            # if no flavor was specified, then throw an error
            if self.name == '':
                err_msg = 'There are multiple running instances of '
                err_msg += 'MultiVu running.'
                for flavor in open_mv_dict:
                    err_msg += f'\n{open_mv_dict[flavor][1]}'
                err_msg += '\nPlease close all but one and retry, '
                err_msg += 'or specify the flavor to connect to.  See the '
                err_msg += 'help (-h)'
                raise MultiPyVuError(err_msg)
            else:
                # check if the declared flavor was found running
                if self.name in open_mv_dict.keys():
                    common_name = self.name
                else:
                    err_msg = f'The specified MultiVu flavor, {self.name}, '
                    err_msg += 'is not running.  Try either not specifying '
                    err_msg += 'the flavor and let MultiPyVu pick the running '
                    err_msg += 'version, or have the specified flavor running.'
                    raise MultiPyVuError(err_msg)

        # declare which version is identified
        msg = f"{common_name} detected here:  {open_mv_dict[common_name][0]}"
        if self.verbose:
            self.logger.info(msg)
        else:
            self.logger.debug(msg)
        return common_name, open_mv_dict[common_name][1]

    def initialize_multivu_win32com(self):
        """
        This creates an instance of the MultiVu ID which is
        used for enabling win32com to work with threading.

        This method updates self.multi_vu and self.mv_id

        Raises:
        -------
        MultiVuExeException
            No detected MultiVu running, and initialization failed.

        """
        if not self.scaffolding_mode:
            max_tries = 3
            for attempt in range(max_tries):
                try:
                    # This will try to connect Python with MultiVu
                    if self.run_with_threading:
                        pythoncom.CoInitialize()
                    # Get an instance
                    self.multi_vu = win32.Dispatch(self.class_id)
                except pythoncom.com_error as e:
                    pythoncom_error = vars(e)['strerror']
                    err_msg = ''
                    if pythoncom_error == 'Invalid class string':
                        err_msg += f'PythonCOM error:  {pythoncom_error}:'
                        err_msg += 'Error instantiating wind32com.client.Dispatch '
                        err_msg += f'using class_id = {self.class_id}'
                        err_msg += '\nTry reinstalling MultiVu.'
                    if attempt < max_tries - 1:
                        time.sleep(0.3)
                    else:
                        err_msg += f'Quitting script after {attempt + 1} '
                        err_msg += 'failed attempts to detect a running copy '
                        err_msg += 'of MultiVu.'
                    raise MultiPyVuError(err_msg) from e
                finally:
                    break

    def get_multivu_win32com_instance(self) -> None:
        """
        This method is used to get an instance of the win32com.client
        and is necessary when using threading.

        This method updates self.multi_vu
        """
        if self.run_with_threading \
                and not self.scaffolding_mode \
                and not self._got_threaded_win32:
            max_tries = 3
            for attempt in range(max_tries):
                try:
                    # This will try to connect Python with MultiVu
                    pythoncom.CoInitialize()
                    self.multi_vu = win32.Dispatch(self.class_id)
                    break
                except (pythoncom.com_error, TimeoutError) as e:
                    if attempt >= max_tries-1:
                        err_msg = f'Quitting script after {attempt + 1} '
                        err_msg += 'failed attempts to connect to MultiVu.'
                        raise MultiPyVuError(err_msg) from e
                time.sleep(0.3)
            self._got_threaded_win32 = True

    def end_multivu_win32com_instance(self):
        """
        Remove the marshalled connection to the MultiVu instance.
        """
        if self.run_with_threading and not self.scaffolding_mode:
            pythoncom.CoUninitialize()
            self._got_threaded_win32 = False
