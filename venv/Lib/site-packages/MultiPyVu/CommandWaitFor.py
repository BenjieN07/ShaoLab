"""
CommandWaitFor.py calls the MultiVu command of the same name

Created on Tue May 18 13:14:28 2021

@author: djackson
"""

import time
from abc import abstractmethod
from enum import IntEnum
from sys import platform
from typing import Dict, List, Tuple, Union

from .check_windows_esc import _check_windows_esc
from .CommandChamber import SimulateChamberChange
from .CommandField import SimulateFieldChange, CommandFieldImp
from .CommandFieldSetPoints import CommandFieldSetPointsImp
from .CommandTemperature import SimulateTemperatureChange, CommandTemperatureImp
from .CommandTempSetPoints import CommandTempSetpointsImp
from .exceptions import (CanError, MultiPyVuError, PythoncomImportError,
                         can_err_enum)
from .ICommand import ICommand, ICommandImp, ISimulateChange
from .IEventManager import IObserver
from .project_vars import CLOCK_TIME

if platform == 'win32':
    try:
        import pythoncom
        import win32com.client as win32
    except ImportError:
        raise PythoncomImportError


class MaskEnum(IntEnum):
    no_system = 0
    temperature = 1
    field = 2
    chamber = 4


units = ''

############################
#
# Base Class
#
############################


class CommandWaitForBase(ICommand):
    def __init__(self, instrument_name: str):
        super().__init__()

        self.units = units
        self.instrument_name = instrument_name

        self._max_bitmask = 0
        for mask in MaskEnum:
            self._max_bitmask = self._max_bitmask | mask
        if self.instrument_name == 'OPTICOOL':
            self._max_bitmask = self._max_bitmask ^ MaskEnum.chamber

        self._mask_options_text = ''
        for m in MaskEnum:
            if (m == MaskEnum.chamber) \
                    and (self.instrument_name != 'OPTICOOL'):
                self._mask_options_text += f'\n\t{m.name} = {m.value}'

    def convert_result(self, response: Dict) -> Tuple[float, str]:
        """
        Converts the CommandMultiVu response from get_state_server()
        to something usable for the user.

        Parameters:
        -----------
        response: Dict:
            Message.response['content']

        Returns:
        --------
        Value and error status returned from read/write
        """
        r = response['result'].split(',')

        if len(r) != 3:
            msg = f'Invalid response: {response}'
            raise MultiPyVuError(msg)
        return (r[0], r[2])

    def prepare_query(self,
                      delay_sec: float,
                      timeout_sec: float = 0.0,
                      bitmask: int = 0,
                      ) -> str:
        delay_sec, timeout_sec, bitmask = self._check_args(delay_sec,
                                                           timeout_sec,
                                                           bitmask,
                                                           )

        return f'{delay_sec},{timeout_sec},{bitmask}'

    def _check_args(self,
                    delay_sec: Union[float, int, str],
                    timeout_sec: Union[float, int, str] = 0.0,
                    bitmask: Union[float, int, str] = 0,
                    ) -> Tuple[float, float, int]:
        """
        Check that the incoming values are of the correct type.

        Parameters:
        -----------
        delay_sec: number or string
        timeout_sec: number or string
        bitmask: number or string

        Returns:
        --------
        (delay_sec, timeout_sec, bitmask): Tuple[float, float, int]
        """
        try:
            delay_sec = float(delay_sec)
        except ValueError:
            err_msg = 'delay_sec must be a float (delay_sec = '
            err_msg += "'{delay_sec}')"
            raise ValueError(err_msg)

        try:
            timeout_sec = float(timeout_sec)
        except ValueError:
            err_msg = 'timeout_sec must be a float (timeout_sec = '
            err_msg += "'{timeout_sec}')"
            raise ValueError(err_msg)

        try:
            bitmask = int(bitmask)
            bitmask = abs(bitmask)
        except ValueError:
            err_msg = 'bitmask must be an int '
            err_msg += f'(bitmask = \'{bitmask}\')'
            err_msg += self._mask_options_text
            raise ValueError(err_msg)
        if bitmask > self._max_bitmask:
            err_msg = f'The mask, {bitmask}, is out of bounds.'
            err_msg += self._mask_options_text
            raise MultiPyVuError(err_msg)
        return delay_sec, timeout_sec, bitmask

    def convert_state_dictionary(self, status_number: int) -> str:
        """
        Takes a string with the can error and abort error in the form
        of (can_error;abort_error) and returns a human readable
        description of the error.

        Parameters:
        -----------
        status_number: int
            can error returned from calling MultiVu

        Returns:
        -------
        A string of the error in words.
        """
        return str(CanError(status_number, 0))

    def state_code_dict(self):
        state_dict = {}
        for can_num in can_err_enum:
            state_dict[can_num, 0] = str(CanError(can_num, 0))
        return state_dict

    def get_state_server(self,
                         value_variant,
                         state_variant, 
                         params='') -> Tuple[float, int]:
        """
        Retrieves information from MultiVu

        Parameters:
        -----------
        value_variant: VARIANT: set up by pywin32com for getting the value
        state_variant: VARIANT: set up by pywin32com for getting the state
        params: str (optional)
            optional parameters that may be required to query MultiVu

        Returns:
        --------
        Tuple(float, int)
            int(bool)
        """
        try:
            bitmask = int(params)
            bitmask = abs(bitmask)
        except ValueError:
            err_msg = 'bitmask must be an int '
            err_msg += f'(bitmask = \'{bitmask}\')'
            err_msg += self._mask_options_text
            raise ValueError(err_msg)
        if bitmask > self._max_bitmask:
            if self.instrument_name == 'OPTICOOL':
                err_msg = 'Chamber control is not available for the OptiCool'
            else:
                err_msg = f'The mask, {bitmask}, is out of bounds.'
                err_msg += self._mask_options_text
            raise MultiPyVuError(err_msg)

        # Add a brief delay before moving on so that the setpoints
        # can get sent to MultiVu and it has time to internally
        # set them.
        time.sleep(CLOCK_TIME)

        return self._get_state(bitmask)

    @abstractmethod
    def _get_state(self, bitmask: int) -> Tuple[float, int]:
        """
        Monitors the state of the system and returns int(bool) for stability

        Parameters:
        -----------
        bitmask: int
            This is used with bite-wise or to know which sub-system
            is monitored for stability

        Returns:
        --------
        Tuple(float, int)
            int(bool)
        """
        raise NotImplementedError

    @abstractmethod
    def _set_state_imp(self,
                       delay_sec: float,
                       timeout_sec: float = 0.0,
                       bitmask: int = 0,
                       ) -> str:
        raise NotImplementedError

    def set_state_server(self, arg_string: str) -> Union[str, int]:
        """
        Sets up the waitfor based on the bitmask, then calls ._wait_for()

        bitmask : int, optional
            This tells wait_for which parameters to wait on.  The best way
            to set this parameter is to byte-wise or the three possibilities:
              client.temperature.waitfor
              client.field.waitfor
              client.chamber.waitfor
            For example, to wait for the temperature and field to stabilize,
            one would set
              bitmask = client.temperature.waitfor | client.field.waitfor
            The default is client.no_subsystem (which is 0).
        """
        if len(arg_string.split(',')) > 3:
            err_msg = 'wait_for() requires between one and three '
            err_msg += 'numeric inputs, separated by a comma: '
            err_msg += 'delay after stability is reached (s), '
            err_msg += 'timeout to wait for stability (s), '
            err_msg += 'bitmask:'
            err_msg += self._mask_options_text
            return err_msg

        # Add a brief delay before moving on so that the setpoints
        # can get sent to MultiVu and it has time to internally
        # set them.
        time.sleep(CLOCK_TIME)

        delay_sec, timeout_sec, bitmask = self._check_args(*arg_string.split(','))
        err = self._set_state_imp(delay_sec, timeout_sec, bitmask)

        return err


############################
#
# Standard Implementation
#
############################

class CommandWaitForImp(CommandWaitForBase):
    def __init__(self,
                 multivu_win32com,
                 instrument_name,
                 t_obj: CommandTemperatureImp,
                 h_obj: CommandFieldImp,
                 c_obj: ICommandImp
                 ):
        super().__init__(instrument_name)
        self.t = t_obj
        self.h = h_obj
        self.c = c_obj
        self.current_vals: Dict[str, Tuple] = {}
        self._mvu = multivu_win32com

    def _get_state(self, bitmask: int) -> Tuple[float, int]:
        """
        Monitors the state of the system and returns int(bool) for stability

        Parameters:
        -----------
        bitmask: int
            This is used with bite-wise or to know which sub-system
            is monitored for stability

        Returns:
        --------
        Tuple(float, int)
            int(bool)
        """
        # Setting up by-reference (VT_BYREF) double (VT_R8)
        # variants.  These will be used to get values.
        set_point_variant = (win32.VARIANT(
            pythoncom.VT_BYREF | pythoncom.VT_R8, 0.0))
        # Setting up a by-reference (VT_BYREF) integer (VT_I4)
        # variant.  This is used to get the status code.
        appr_variant = (win32.VARIANT(
            pythoncom.VT_BYREF | pythoncom.VT_I4, 0))

        self.i_cmds: List[ICommandImp] = []
        if (bitmask & MaskEnum.temperature == MaskEnum.temperature):
            t_set = CommandTempSetpointsImp(self.instrument_name, self._mvu)
            (t, rate, approach), _ = t_set.get_state_server(set_point_variant, appr_variant)
            self.t.set_point = t
            self.t.rate = rate
            self.t.approach = self.t.approach_mode(approach)
            self.i_cmds.append(self.t)
        if bitmask & MaskEnum.field == MaskEnum.field:
            if self.instrument_name == 'MPMS3':
                # The MPMS3 does not appear to have a way to get the field setpoint.
                # Customers will want to set the field before calling wait_for()
                # when telling the system to wait for field stability.
                pass
            else:
                h_set = CommandFieldSetPointsImp(self.instrument_name, self._mvu)
                (h, rate, approach, driven), _ = h_set.get_state_server(set_point_variant, appr_variant)
                self.h.set_point = h
                self.h.rate = rate
                self.h.approach = self.h.approach_mode(approach)
                self.h.driven = self.h.drive_mode(driven)
            self.i_cmds.append(self.h)
        if bitmask & MaskEnum.chamber == MaskEnum.chamber:
            self.i_cmds.append(self.c)

        # check if changes have finished
        stable = [c for c in self.i_cmds if not c.test()]
        # check if all threads have finished
        result = (len(stable) == 0)
        return (int(result), 0)

    def _set_state_imp(self,
                       delay_sec: float,
                       timeout_sec: float = 0.0,
                       bitmask: int = 0,
                       ) -> int:
        """
        This command pauses the code until the specified criteria are met.

        Parameters
        ----------
        delay_sec : float
            Time in seconds to wait after stability is reached.
        timeout_sec : float, optional
            If stability is not reached within timeout (in seconds), the
            wait is abandoned. The default timeout is 0, which indicates this
            feature is turned off (i.e., to wait forever for stability).
        bitmask : int, optional
            This tells wait_for which parameters to wait on.  The best way
            to set this parameter is to use the MultiVuClient.subsystem enum,
            using bite-wise or to wait for multiple parameters.  For example,
            to wait for the temperature and field to stabilize, one would set
            bitmask = (Client.temperature.waitfor
                       | MultiVuClient.field.waitfor).
            The default is MultiVuClient.no_subsystem (which is 0).

        """
        # Setting up by-reference (VT_BYREF) double (VT_R8)
        # variants.  These will be used to get values.
        set_point_variant = (win32.VARIANT(
            pythoncom.VT_BYREF | pythoncom.VT_R8, 0.0))
        # Setting up a by-reference (VT_BYREF) integer (VT_I4)
        # variant.  This is used to get the status code.
        appr_variant = (win32.VARIANT(
            pythoncom.VT_BYREF | pythoncom.VT_I4, 0))

        self.i_cmds: List[ICommandImp] = []
        if (bitmask & MaskEnum.temperature == MaskEnum.temperature):
            t_set = CommandTempSetpointsImp(self.instrument_name, self._mvu)
            (t, rate, approach), _ = t_set.get_state_server(set_point_variant, appr_variant)
            self.t.set_point = t
            self.t.rate = rate
            self.t.approach = self.t.approach_mode(approach)
            self.i_cmds.append(self.t)
        if bitmask & MaskEnum.field == MaskEnum.field:
            if self.instrument_name == 'MPMS3':
                # The MPMS3 does not appear to have a way to get the field setpoint.
                # Customers will want to set the field before calling wait_for()
                # when telling the system to wait for field stability.
                pass
            else:
                h_set = CommandFieldSetPointsImp(self.instrument_name, self._mvu)
                (h, rate, approach, driven), _ = h_set.get_state_server(set_point_variant, appr_variant)
                self.h.set_point = h
                self.h.rate = rate
                self.h.approach = self.h.approach_mode(approach)
                self.h.driven = self.h.drive_mode(driven)
            self.i_cmds.append(self.h)
        if bitmask & MaskEnum.chamber == MaskEnum.chamber:
            self.i_cmds.append(self.c)

        start_time = time.time()
        while True:
            elapsed_time = time.time() - start_time
            if (timeout_sec > 0.0) and (elapsed_time > timeout_sec):
                return 0
            else:
                time.sleep(CLOCK_TIME)
            _check_windows_esc()

            # check if changes have finished
            stable = [c for c in self.i_cmds if not c.test()]
            # quit if all threads have finished
            if len(stable) == 0:
                break

        # delay loop
        start_delay_time = time.time()
        while (time.time() - start_delay_time) < delay_sec:
            if (timeout_sec > 0.0) \
                    and ((time.time() - start_time) > timeout_sec):
                return 0
            _check_windows_esc()
            time.sleep(CLOCK_TIME)
        return 0


############################
#
# Scaffolding Implementation
#
############################


class CommandWaitForSim(CommandWaitForBase, IObserver):
    def __init__(self,
                 instrument_name,
                 t_obj: SimulateTemperatureChange,
                 h_obj: SimulateFieldChange,
                 c_obj: SimulateChamberChange,
                 ):
        super().__init__(instrument_name)
        self.t = t_obj
        self.h = h_obj
        self.c = c_obj

    def _get_state(self, bitmask: int) -> Tuple[float, int]:
        """
        Monitors the state of the system and returns int(bool) for stability

        Parameters:
        -----------
        bitmask: int
            This is used with bite-wise or to know which sub-system
            is monitored for stability

        Returns:
        --------
        Tuple(float, int)
            int(bool)
        """
        # subscribe to the changes.
        self.monitors: Dict[str, ISimulateChange] = {}
        if (bitmask & MaskEnum.temperature) == MaskEnum.temperature:
            self.monitors[self.t.name] = self.t
        if (bitmask & MaskEnum.field) == MaskEnum.field:
            self.monitors[self.h.name] = self.h
        if (bitmask & MaskEnum.chamber) == MaskEnum.chamber:
            self.monitors[self.c.name] = self.c

        for m in self.monitors.values():
            # see if the set_point has been defined
            try:
                m.set_point
            except AttributeError:
                m.set_point = m.current_val
            m.subscribe(self)

        # check if changes have finished
        stable = [name for name,
                  m in self.monitors.items()
                  if not m.is_sim_alive()]
        # remove the stable items
        for m in stable:
            del self.monitors[m]
        # quit if all threads have finished
        result = (len(self.monitors) == 0)
        return int(result), 0

    def _set_state_imp(self,
                       delay_sec: float,
                       timeout_sec: float = 0.0,
                       bitmask: int = 0,
                       ) -> int:
        # subscribe to the changes.
        self.monitors: Dict[str, ISimulateChange] = {}
        if (bitmask & MaskEnum.temperature) == MaskEnum.temperature:
            self.monitors[self.t.name] = self.t
        if (bitmask & MaskEnum.field) == MaskEnum.field:
            self.monitors[self.h.name] = self.h
        if (bitmask & MaskEnum.chamber) == MaskEnum.chamber:
            self.monitors[self.c.name] = self.c

        for m in self.monitors.values():
            # see if the set_point has been defined
            try:
                m.set_point
            except AttributeError:
                m.set_point = m.current_val
            m.subscribe(self)

        err = self._wait_for(delay_sec, timeout_sec)

        # unsubscribe from all the monitors
        for m in self.monitors.values():
            m.unsubscribe(self)
        return err

    def _wait_for(self,
                  delay_sec: float,
                  timeout_sec: float = 0.0,
                  ) -> int:
        """
        This command pauses the code until the specified criteria are met.

        Parameters
        ----------
        delay_sec : float
            Time in seconds to wait after stability is reached.
        timeout_sec : float, optional
            If stability is not reached within timeout (in seconds), the
            wait is abandoned. The default timeout is 0, which indicates this
            feature is turned off (i.e., to wait forever for stability).
        """
        start_time = time.time()
        while True:
            elapsed_time = time.time() - start_time
            if (timeout_sec > 0.0) and (elapsed_time > timeout_sec):
                return 0
            else:
                time.sleep(CLOCK_TIME)
            _check_windows_esc()

            # check if changes have finished
            stable = [name for name, m in self.monitors.items() if not m.is_sim_alive()]
            # remove the stable items
            for m in stable:
                del self.monitors[m]
            # quit if all threads have finished
            if len(self.monitors) == 0:
                break

        # delay loop
        start_delay_time = time.time()
        while (time.time() - start_delay_time) < delay_sec:
            if (timeout_sec > 0.0) \
                    and (time.time() - start_time) > timeout_sec:
                return 0
            _check_windows_esc()
            time.sleep(CLOCK_TIME)
        return 0

    def update(self, value, state):
        pass
