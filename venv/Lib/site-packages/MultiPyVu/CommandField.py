# -*- coding: utf-8 -*-
"""
CommandField.py has the information required to get and set the field state.

Created on Tue May 18 13:14:28 2021

@author: djackson
"""

import time
from abc import abstractmethod
from enum import IntEnum
from typing import Dict, List, Tuple, Union

from .check_windows_esc import _check_windows_esc
from .exceptions import MultiPyVuError
from .ICommand import (ICommand, ICommandImp, ICommandObserverSim,
                       ISimulateChange, catch_thread_error, floats_equal)
from .IEventManager import IObserver
from .project_vars import CLOCK_TIME


class ApproachEnum(IntEnum):
    linear = 0
    no_overshoot = 1
    oscillate = 2


# the PPMS is the only flavor which can run persistent
class drivenEnum(IntEnum):
    persistent = 0
    driven = 1

    @classmethod
    def _missing_(cls, value):
        return drivenEnum.driven


# Field state code dictionary
STATE_DICT = {
    0: 'Unknown',
    1: 'Stable',
    2: 'Switch Warming',
    3: 'Switch Cooling',
    4: 'Holding (driven)',
    5: 'Iterate',
    6: 'Ramping',
    7: 'Ramping',
    8: 'Resetting',
    9: 'Current Error',
    10: 'Switch Error',
    11: 'Quenching',
    12: 'Charging Error',
    14: 'PSU Error',
    15: 'General Failure',
}


units = 'Oe'


############################
#
# Base Class
#
############################


class CommandFieldBase(ICommand):
    # class variables
    _set_point: float = 0.0
    _current_val: float = 0.0
    _rate: float = 1
    _state: int = 1
    _approach: ApproachEnum = ApproachEnum.no_overshoot
    _driven: drivenEnum = drivenEnum.driven

    def __init__(self, instrument_name: str):
        super().__init__()
        self.instrument_name = instrument_name
        self.approach_mode = ApproachEnum
        self.drive_mode = drivenEnum

        self.units = units

    @property
    def current_val(self):
        return CommandFieldBase._current_val

    @current_val.setter
    def current_val(self, new):
        CommandFieldBase._current_val = new

    @property
    def set_point(self):
        return CommandFieldBase._set_point

    @set_point.setter
    def set_point(self, new):
        CommandFieldBase._set_point = new

    @property
    def rate(self):
        return CommandFieldBase._rate

    @rate.setter
    def rate(self, new):
        CommandFieldBase._rate = new

    @property
    def state(self):
        return CommandFieldBase._state

    @state.setter
    def state(self, new):
        CommandFieldBase._state = new

    @property
    def approach(self) -> ApproachEnum:
        return CommandFieldBase._approach

    @approach.setter
    def approach(self, new):
        CommandFieldBase._approach = new

    @property
    def driven(self) -> drivenEnum:
        return CommandFieldBase._driven

    @driven.setter
    def driven(self, new: drivenEnum):
        CommandFieldBase._driven = new

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
            h, _, status = r
        elif len(r) == 1:
            h = '0.0'
            [status] = r
        else:
            msg = f'Invalid response: {response}'
            raise MultiPyVuError(msg)
        field = float(h)
        return field, status

    def prepare_query(self,
                      set_point: float,
                      rate_per_sec: float,
                      approach: IntEnum,
                      mode=None) -> str:
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

        # driven is default because it is used by all but the PPMS
        mode = drivenEnum.driven.value if mode is None else mode.value

        return f'{set_point},{rate_per_sec},{approach.value},{mode}'

    def convert_state_dictionary(self, status_number):
        if isinstance(status_number, str):
            return status_number
        else:
            return STATE_DICT[status_number]

    @abstractmethod
    def get_state_server(self, value_variant, state_variant, params=''):
        raise NotImplementedError

    @abstractmethod
    def _set_state_imp(self,
                       field: float,
                       set_rate_per_sec: float,
                       set_approach: ApproachEnum,
                       set_driven: drivenEnum,
                       ) -> Union[str, int]:
        raise NotImplementedError

    def set_state_server(self, arg_string) -> Union[str, int]:
        if len(arg_string.split(',')) != 4:
            err_msg = 'Setting the field requires four numeric inputs, '
            err_msg += 'separated by a comma: '
            err_msg += 'Set Point (Oe), '
            err_msg += 'rate (Oe/sec),'
            err_msg += 'approach (Linear (0); No O\'Shoot (1); Oscillate (2)),'
            err_msg += 'magnetic state (persistent (0); driven (1))'
            return err_msg
        field, rate, approach, driven = arg_string.split(',')
        field = float(field)
        set_rate_per_sec = float(rate)
        set_approach = int(approach)
        set_approach_number = int(approach)
        if set_approach_number > len(ApproachEnum) - 1:
            err_msg = f'The approach, {set_approach_number}, is out of bounds.'
            err_msg += ' Must be one of the following:'
            for mode in ApproachEnum:
                err_msg += f'\n\t{mode.value}: {mode.name}'
            raise MultiPyVuError(err_msg)
        set_approach = ApproachEnum(set_approach_number)

        set_driven_number = int(driven)
        if self.instrument_name != 'PPMS':
            set_driven = drivenEnum(set_driven_number)
            if set_driven == drivenEnum.persistent:
                err_msg = f'{self.instrument_name} can only drive the magnet '
                err_msg += 'in driven mode.'
                raise MultiPyVuError(err_msg)
        else:
            if set_driven_number > len(drivenEnum) - 1:
                err_msg = f'The driven mode, {set_driven_number}, is out of '
                err_msg += 'bounds. Must be one of the following:'
                for mode in drivenEnum:
                    err_msg += f'\n\t{mode.value}: {mode.name}'
                raise MultiPyVuError(err_msg)
            set_driven = drivenEnum(set_driven_number)
        if self.instrument_name == 'VERSALAB':
            if set_approach == ApproachEnum.no_overshoot:
                err_msg = f'{self.instrument_name} does not support the '
                err_msg += 'no_overshoot approach mode.'
                raise MultiPyVuError(err_msg)

        error = self._set_state_imp(field,
                                    set_rate_per_sec,
                                    set_approach,
                                    set_driven
                                    )
        return error

    def state_code_dict(self):
        return STATE_DICT


############################
#
# Standard Implementation
#
############################


class CommandFieldImp(ICommandImp, CommandFieldBase):
    def __init__(self, multivu_win32com, instrument_name):
        """
        Parameters:
        ----------
        multivu_win32com: win32.dynamic.CDispatch
        instrument_name: str
        """
        CommandFieldBase.__init__(self, instrument_name)
        self._mvu = multivu_win32com

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
        Tuple(str, int)
            The value and state number
        """
        can_error = self._mvu.GetField(value_variant, state_variant)
        # On 6/10/25, I found that the PPMS was returning something greater
        # than 1 with the GetTemperature() command.  After talking with Mark,
        # I have decided to only check for a value greater than 1 for all
        # systems.
        if can_error > 1:
            raise MultiPyVuError('Error when calling GetField()')
        self.current_val = value_variant.value
        self.state = int(state_variant.value)

        return self.current_val, self.state

    def _set_state_imp(self,
                       field: float,
                       set_rate_per_sec: float,
                       set_approach: ApproachEnum,
                       set_driven: drivenEnum
                       ) -> Union[str, int]:
        can_error = self._mvu.setField(field,
                                       set_rate_per_sec,
                                       set_approach,
                                       set_driven,
                                       )
        self.set_point = field
        self.rate = set_rate_per_sec
        self.approach = set_approach
        self.driven = drivenEnum(set_driven)

        if can_error > 1:
            raise MultiPyVuError('Error when calling SetField()')
        # It is odd that sometimes a can_error of 1 is okay.  So far I have
        # only seen this behavior with a few flavors.
        if self.instrument_name in ('PPMS', 'MPMS3'):
                # returning this string makes CommandMultiVu_base happy
                return 'Call was successful'
        return can_error

    def test(self) -> bool:
        """
        This method is used to monitor the field. It waits for
        the status to become 'stable' at the set point

        Returns:
        --------
        bool
        """
        accept_pct = 0.005
        abs_tol = 0.4

        steady = False
        self._get_values()
        state_name = self.convert_state_dictionary(self.state)
        if state_name in ('Holding (driven)', 'Stable'):
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
class SimulateFieldChange(ISimulateChange):
    # class variables
    _stop_flag: bool = False
    _val: float
    _state: str
    _set_point: float
    _rate: float
    _approach: ApproachEnum = ApproachEnum.no_overshoot
    _driven: drivenEnum = drivenEnum.persistent
    _observers: List[IObserver] = []

    def __init__(self):
        super().__init__('SimulateFieldChange')

    @property
    def current_val(self):
        return SimulateFieldChange._val

    @current_val.setter
    def current_val(self, new):
        SimulateFieldChange._val = new

    @property
    def set_point(self):
        return SimulateFieldChange._set_point

    @set_point.setter
    def set_point(self, new):
        SimulateFieldChange._set_point = new

    @property
    def rate(self):
        return SimulateFieldChange._rate

    @rate.setter
    def rate(self, new):
        SimulateFieldChange._rate = new

    @property
    def approach(self) -> ApproachEnum:
        return SimulateFieldChange._approach

    @approach.setter
    def approach(self, new: ApproachEnum):
        SimulateFieldChange._approach = new

    @property
    def driven_mode(self) -> drivenEnum:
        return SimulateFieldChange._driven

    @driven_mode.setter
    def driven_mode(self, new: drivenEnum):
        SimulateFieldChange._driven = new

    def stop_requested(self):
        return SimulateFieldChange._stop_flag

    def stop_thread(self, set_stop=True):
        SimulateFieldChange._stop_flag = set_stop

    def _monitor(self):
        starting_field = self.current_val
        self.state = STATE_DICT[1]
        self.notify_observers(self.current_val, self.state)

        # simulate a pause before changing the field
        start_time = time.time()
        elapsed_time = time.time() - start_time
        while elapsed_time < 1:
            time.sleep(CLOCK_TIME)
            if self.stop_requested():
                return
            # check the escape key
            _check_windows_esc()
            elapsed_time = time.time() - start_time

        # set up the ramp
        delta_H = self.set_point - starting_field
        self.rate *= -1 if delta_H < 0 else 1
        rate_time = delta_H / self.rate

        # set state to ramping
        start_time = time.time()
        self.state = STATE_DICT[6]
        self.notify_observers(self.current_val, self.state)

        # simulate the ramp
        while ((time.time() - start_time) < rate_time) \
                or (self.current_val != self.set_point):
            if self.stop_requested():
                return
            time.sleep(CLOCK_TIME)
            self.acquire_mutex()
            self.current_val += CLOCK_TIME * self.rate
            # The ramp points are discrete, so they can
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
        self.state = STATE_DICT[5]
        self.notify_observers(self.current_val, self.state)
        start_time = time.time()
        # simulate coming to stability
        while time.time() - start_time < 0.5:
            time.sleep(CLOCK_TIME)
            if self.stop_requested():
                return
            _check_windows_esc()

        # at the set point
        if (self.driven_mode == drivenEnum.driven):
            state_number = drivenEnum(4)
        else:
            state_number = drivenEnum(1)
        self.state = STATE_DICT[state_number]
        self.notify_observers(self.current_val, self.state)
        # unsubscribe from all observers before exiting
        for o in self._observers:
            self.unsubscribe(o)
        return


class CommandFieldSim(CommandFieldBase,
                      ICommandObserverSim,
                      ):

    def __init__(self, instrument_name: str):
        CommandFieldBase.__init__(self, instrument_name)
        ICommandObserverSim.__init__(self,
                                     SimulateFieldChange,
                                     )

    def get_state_server(self, value_variant, state_variant, params=''):
        return self.current_val, self.state

    def _set_state_imp(self,
                       field: float,
                       set_rate_per_sec: float,
                       set_approach: ApproachEnum,
                       set_driven: drivenEnum
                       ) -> Union[str, int]:
        self.change_thread: SimulateFieldChange = self.get_sim_instance()
        state_string = STATE_DICT[self.state]
        self.change_thread.set_params(self.current_val,
                                      field,
                                      set_rate_per_sec,
                                      state_string,
                                      )
        self.set_point = field
        self.rate = set_rate_per_sec
        self.approach = set_approach
        self.change_thread.approach = set_approach
        self.driven = set_driven
        self.change_thread.driven_mode = self.driven

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
