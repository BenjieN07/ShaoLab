# -*- coding: utf-8 -*-
"""
CommandRotator.py has the information required to get and
set the horizontal rotator.

@author: djackson
"""

import time
from abc import abstractmethod
from enum import IntEnum
from sys import platform
from typing import Dict, List, Tuple, Union

from .check_windows_esc import _check_windows_esc
from .exceptions import MultiPyVuError, PythoncomImportError
from .ICommand import (ICommand, ICommandImp, ICommandObserverSim,
                       ISimulateChange, catch_thread_error, floats_equal)
from .IEventManager import IObserver
from .project_vars import CLOCK_TIME

if platform == 'win32':
    try:
        import pythoncom
        import win32com.client as win32
    except ImportError:
        raise PythoncomImportError


class RotatorEnum(IntEnum):
    move_to_position = 0
    move_to_index = 1
    redefine_present_position = 2


# Field state code dictionary
STATE_DICT = {
    0: "Unknown",
    1: "Transport stopped at set point",
    2: "Calibrating",
    3: "Unrecognized status code",
    4: "Unrecognized status code",
    5: "Transport moving toward set point",
    6: "Unrecognized status code",
    7: "Unrecognized status code",
    8: "Transport hit limit switch",
    9: "Transport hit index switch",
    10: "Unrecognized status code",
    11: "Unrecognized status code",
    12: "Unrecognized status code",
    13: "Unrecognized status code",
    14: "Unrecognized status code",
    15: "General failure in position control system"
    }


units = 'Deg'


############################
#
# Base Class
#
############################


class CommandRotatorBase(ICommand):
    # class variables
    _set_point: float = 0.0
    _current_val: float = 0.0
    _rate: float = 1
    _state: int = 1
    _mode: RotatorEnum = RotatorEnum.move_to_position
    _serial_number: str = ''    # example: 'ROT123'
    _posName: str = 'Horizontal Rotator'

    def __init__(self, instrument_name: str):
        super().__init__()
        self.instrument_name = instrument_name

        self.units = units

    @property
    def current_val(self):
        return CommandRotatorBase._current_val

    @current_val.setter
    def current_val(self, new):
        CommandRotatorBase._current_val = new

    @property
    def set_point(self):
        return CommandRotatorBase._set_point

    @set_point.setter
    def set_point(self, new):
        CommandRotatorBase._set_point = new

    @property
    def rate(self):
        return CommandRotatorBase._rate

    @rate.setter
    def rate(self, new):
        CommandRotatorBase._rate = new

    @property
    def state(self):
        return CommandRotatorBase._state

    @state.setter
    def state(self, new):
        CommandRotatorBase._state = new

    # These properties are not going to be used by the rotator.
    # @property
    # def rotator_mode(self):
    #     return CommandRotatorBase._mode

    # @rotator_mode.setter
    # def rotator_mode(self, new):
    #     CommandRotatorBase._mode = new

    @property
    def serial_number(self):
        return CommandRotatorBase._serial_number

    @serial_number.setter
    def serial_number(self, new):
        CommandRotatorBase._serial_number = new

    def convert_result(self, response: Dict[str, str]) -> Tuple[float, str]:
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
        if len(r) == 3:
            p, _, status = r
        elif len(r) == 1:
            p = '0.0'
            [status] = r
        else:
            msg = f'Invalid response: {response}'
            raise MultiPyVuError(msg)
        position = float(p)
        return position, status

    def prepare_query(self,
                      set_point: float,
                      rate_per_sec: float) -> str:
        try:
            set_point = float(set_point)
        except ValueError:
            err_msg = f"set_point must be a float (set_point = '{set_point}')"
            raise ValueError(err_msg)

        try:
            rate_per_sec = float(rate_per_sec)
            rate_per_sec = abs(rate_per_sec)
        except ValueError:
            err_msg = 'rate_per_sec must be a float '
            err_msg += f'(rate_per_sec = \'{rate_per_sec}\')'
            raise ValueError(err_msg)

        return f'{set_point},{rate_per_sec}'

    def convert_state_dictionary(self, status_number):
        if isinstance(status_number, str):
            return status_number
        else:
            return STATE_DICT.get(status_number, status_number)

    @abstractmethod
    def _get_state_imp(self, value_variant, state_variant, params=''):
        raise NotImplementedError

    def get_state_server(self, value_variant, state_variant, params=''):
        # Check this is being used on a valid instrument
        valid_instruments = [
                'PPMS',
                'DYNACOOL',
                'VERSALAB',
            ]
        if self.instrument_name not in valid_instruments:
            err_msg = 'The horizontal rotator does not work '
            err_msg = f'with the {self.instrument_name}'
            raise MultiPyVuError(err_msg)
        return self._get_state_imp(value_variant, state_variant, params)

    @abstractmethod
    def _set_state_imp(self,
                       position: float,
                       set_rate_per_sec: float,
                       set_mode: RotatorEnum,
                       ) -> Union[str, int]:
        raise NotImplementedError

    def set_state_server(self, arg_string) -> Union[str, int]:
        if len(arg_string.split(',')) != 2:
            err_msg = 'Setting the rotator position requires two numeric '
            err_msg += 'inputs, separated by a comma: '
            err_msg += 'Set Point (deg), '
            err_msg += 'rate (ded/sec),'
            raise MultiPyVuError(err_msg)
        position, rate = arg_string.split(',')

        # Check this is being used on a valid instrument
        valid_instruments = [
                'PPMS',
                'DYNACOOL',
                'VERSALAB',
            ]
        if self.instrument_name not in valid_instruments:
            err_msg = 'The horizontal rotator does not work '
            err_msg = f'with the {self.instrument_name}'
            raise MultiPyVuError(err_msg)

        position = float(position)
        min_position = -10.0
        max_position = 370.0
        if (position < min_position) or (position > max_position):
            err_msg = "set_point out of range.  Must be between "
            err_msg += f"{min_position} and {max_position} degrees."
            raise ValueError(err_msg)
        set_rate_per_sec = float(rate)

        # Only give users access to move the position.
        set_mode = RotatorEnum.move_to_position
        error = self._set_state_imp(position,
                                    set_rate_per_sec,
                                    set_mode,
                                    )
        return error

    def state_code_dict(self):
        return STATE_DICT


############################
#
# Standard Implementation
#
############################


class CommandRotatorImp(ICommandImp, CommandRotatorBase):
    def __init__(self, multivu_win32com, instrument_name: str):
        """
        Parameters:
        ----------
        multivu_win32com: win32.dynamic.CDispatch
        instrument_name: str
        """
        CommandRotatorBase.__init__(self, instrument_name)
        self._mvu = multivu_win32com

    def _get_state_imp(self, value_variant, state_variant, params=''):
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
        Tuple(str, int)
            The value and state number
        """
        if self.instrument_name == 'PPMS':
            # Setting up a by-reference (VT_BYREF) string (VT_BSTR)
            # variant.  This is used to get the response.
            string_variant = (win32.VARIANT(
                pythoncom.VT_BYREF | pythoncom.VT_BSTR, ""))

            # Setting up a by-reference (VT_BYREF) string (VT_BSTR)
            # variant.  This is used to get the error.
            error_variant = (win32.VARIANT(
                pythoncom.VT_BYREF | pythoncom.VT_BSTR, ""))

            # Start by getting the degrees per count
            command = 'MOVECFG?'
            device = 0
            timeout = 0
            can_error = self._mvu.SendPpmsCommand(command,
                                                  string_variant,
                                                  error_variant,
                                                  device,
                                                  timeout,
                                                  )
            response = string_variant.value.split(',')
            if len(response) != 4:
                error = error_variant.value
                err_msg = 'Invalid response while getting '
                err_msg += f'the motor calibration: "{response}"'
                err_msg += f' error = "{error}"'
                raise MultiPyVuError(err_msg)
            degree_index, deg_per_count, max_range, index_switch_flag = response
            deg_per_count = float(deg_per_count)

            # Now get the count position
            command = '$MOVE?'
            can_error = self._mvu.SendPpmsCommand(command,
                                                  string_variant,
                                                  error_variant,
                                                  device,
                                                  timeout,
                                                  )
            response = string_variant.value.split(',')
            if len(response) != 4:
                error = error_variant.value
                err_msg = 'Invalid response while getting '
                err_msg += f'the motor position: "{response}"'
                err_msg += f' error = "{error}"'
                raise MultiPyVuError(err_msg)
            count, final_count, index_switch_flag, backlash = response
            count = int(count)
            final_count = int(final_count)
            self.current_val = deg_per_count * count
            # If count is not at final_count, then the rotator
            # is moving (state = 5) else at set point (state = 1).
            self.state = 5 if count != final_count else 1
        else:
            can_error = self._mvu.GetPosition(self._posName,
                                              value_variant,
                                              state_variant
                                              )
            self.current_val = value_variant.value
            self.state = int(state_variant.value)
        if can_error > 1:
            raise MultiPyVuError('Error when calling GetPosition()')

        return self.current_val, self.state

    def _set_state_imp(self,
                       position: float,
                       set_rate_per_sec: float,
                       set_mode: int,
                       ) -> Union[str, int]:
        if self.instrument_name == 'PPMS':
            slow_down = 0
            command = f'MOVE {position} {set_mode} {slow_down}'

            # Setting up a by-reference (VT_BYREF) string (VT_BSTR)
            # variant.  This is used to get the response.
            string_variant = (win32.VARIANT(
                pythoncom.VT_BYREF | pythoncom.VT_BSTR, ""))

            # Setting up a by-reference (VT_BYREF) string (VT_BSTR)
            # variant.  This is used to get the error.
            error_variant = (win32.VARIANT(
                pythoncom.VT_BYREF | pythoncom.VT_BSTR, ""))

            device = 0
            timeout = 0
            can_error = self._mvu.SendPpmsCommand(command,
                                                  string_variant,
                                                  error_variant,
                                                  device,
                                                  timeout,
                                                  )
            if can_error > 1:
                # This seems to be expected behavior.
                # Returning this string makes CommandMultiVu_base happy
                can_error = 'Call was successful'
        else:
            can_error = self._mvu.setPosition(self._posName,
                                              position,
                                              set_rate_per_sec,
                                              set_mode,
                                              )
            if can_error > 1:
                err_msg = 'Error when calling setPosition(), is the '
                err_msg += 'Rotator Option active?'
                raise MultiPyVuError(err_msg)
        self.set_point = position
        self.rate = set_rate_per_sec
        self.rotator_mode = set_mode
        return can_error

    def test(self) -> bool:
        """
        This method is used to monitor the position. It waits for
        the status to become 'Transport stopped at set point' at
        the set point

        Returns:
        --------
        bool
        """
        # These values are guesses and are held over from
        # CommandFieldImp.
        accept_pct = 0.005
        abs_tol = 0.4

        steady = False
        self._get_values()
        # Look for 'Transport stopped at set point'
        if self.state == 1:
            steady = floats_equal(self.current_val,
                                  self.set_point,
                                  accept_pct,
                                  abs_tol,
                                  )
        return steady


############################
#
# Scaffolding Implementation
#
############################

@catch_thread_error
class SimulateRotatorChange(ISimulateChange):
    # class variables
    _stop_flag: bool = False
    _val: float
    _state: str
    _set_point: float
    _rate: float
    _mode: RotatorEnum = RotatorEnum.move_to_position
    _observers: List[IObserver] = []

    def __init__(self):
        super().__init__('SimulateRotatorChange')

    @property
    def current_val(self):
        return SimulateRotatorChange._val

    @current_val.setter
    def current_val(self, new):
        SimulateRotatorChange._val = new

    @property
    def set_point(self):
        return SimulateRotatorChange._set_point

    @set_point.setter
    def set_point(self, new):
        SimulateRotatorChange._set_point = new

    @property
    def rate(self):
        return SimulateRotatorChange._rate

    @rate.setter
    def rate(self, new):
        SimulateRotatorChange._rate = new

    @property
    def mode(self) -> RotatorEnum:
        return SimulateRotatorChange._mode

    @mode.setter
    def mode(self, new: RotatorEnum):
        SimulateRotatorChange._mode = new

    def stop_requested(self):
        return SimulateRotatorChange._stop_flag

    def stop_thread(self, set_stop=True):
        SimulateRotatorChange._stop_flag = set_stop

    def _monitor(self):
        starting_position = self.current_val

        # set up the ramp
        delta_pos = self.set_point - starting_position
        self.rate *= -1 if delta_pos < 0 else 1
        rate_time = delta_pos / self.rate

        # set state to moving
        start_time = time.time()
        self.state = STATE_DICT[5]
        self.notify_observers(self.current_val, self.state)

        # simulate the ramp
        while ((time.time() - start_time) < rate_time) \
                or (self.current_val != self.set_point):
            if self.stop_requested():
                return
            time.sleep(CLOCK_TIME)
            self.acquire_mutex()
            self.current_val += CLOCK_TIME * self.rate
            # The movement is discrete, so it can
            # pass over the set point.  This check ensures
            # that there is no overshoot.
            if self.rate > 0:
                self.current_val = min(self.current_val,
                                       self.set_point)
            else:
                self.current_val = max(self.current_val,
                                       self.set_point)
            self.release_mutex()
            self.notify_observers(self.current_val, self.state)
            # check the escape key
            _check_windows_esc()

        # set the final values
        self.current_val = self.set_point
        self.state = STATE_DICT[1]
        self.notify_observers(self.current_val, self.state)
        start_time = time.time()

        # at the set point
        self.notify_observers(self.current_val, self.state)
        # unsubscribe from all observers before exiting
        for o in self._observers:
            self.unsubscribe(o)
        return


class CommandRotatorSim(CommandRotatorBase,
                        ICommandObserverSim,
                        ):

    def __init__(self, instrument_name: str):
        CommandRotatorBase.__init__(self, instrument_name)
        ICommandObserverSim.__init__(self,
                                     SimulateRotatorChange,
                                     )

    def _get_state_imp(self, value_variant, state_variant, params=''):
        return self.current_val, self.state

    def _set_state_imp(self,
                       position: float,
                       set_rate_per_sec: float,
                       set_mode: RotatorEnum,
                       ) -> Union[str, int]:
        self.change_thread: SimulateRotatorChange = self.get_sim_instance()
        state_string = STATE_DICT[self.state]
        self.change_thread.set_params(self.current_val,
                                      position,
                                      set_rate_per_sec,
                                      state_string,
                                      )
        self.mode = set_mode
        self.change_thread.mode = set_mode

        self.change_thread.subscribe(self)
        self.change_thread.start()
        error = 0
        return error

    def update(self, value, state):
        self.current_val = value
        for state_number, state_str in STATE_DICT.items():
            if state == state_str:
                self.state = state_number
                break
