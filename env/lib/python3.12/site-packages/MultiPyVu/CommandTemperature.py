"""
CommandTemperature.py has the information required to get and set the
temperature state.

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
    fast_settle = 0
    no_overshoot = 1


# Temperature state code dictionary
STATE_DICT = {
    1: "Stable",
    2: "Tracking",
    5: "Near",
    6: "Chasing",
    7: "Pot Operation",
    10: "Standby",
    13: "Diagnostic",
    14: "Impedance Control Error",
    15: "General Failure",
}


units = 'K'

############################
#
# Base Class
#
############################


class CommandTemperatureBase(ICommand):
    _set_point: float = 300.0
    _val: float = 300.0
    _state: int = 1
    _rate: float = 1.0
    _approach: ApproachEnum = ApproachEnum.fast_settle

    def __init__(self):
        super().__init__()
        self.approach_mode = ApproachEnum

        self.units = units

    @property
    def current_val(self):
        return CommandTemperatureBase._val

    @current_val.setter
    def current_val(self, new):
        CommandTemperatureBase._val = new

    @property
    def set_point(self):
        return CommandTemperatureBase._set_point

    @set_point.setter
    def set_point(self, new):
        CommandTemperatureBase._set_point = new

    @property
    def state(self):
        return CommandTemperatureBase._state

    @state.setter
    def state(self, new):
        CommandTemperatureBase._state = new

    @property
    def rate(self):
        return CommandTemperatureBase._rate

    @rate.setter
    def rate(self, new):
        CommandTemperatureBase._rate = new

    @property
    def approach(self) -> ApproachEnum:
        return CommandTemperatureBase._approach

    @approach.setter
    def approach(self, new):
        CommandTemperatureBase._approach = new

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
            t, _, status = r
        elif len(r) == 1:
            t = '0.0'
            [status] = r
        else:
            msg = f'Invalid response: {response}'
            raise MultiPyVuError(msg)
        temperature = float(t)
        return temperature, status

    def prepare_query(self,
                      set_point: float,
                      rate_per_minute: float,
                      approach_mode: IntEnum) -> str:
        try:
            set_point = float(set_point)
        except ValueError:
            err_msg = 'set_point must be a float (set_point = '
            err_msg += "'{set_point}')"
            raise ValueError(err_msg)
        try:
            rate_per_minute = float(rate_per_minute)
            rate_per_minute = abs(rate_per_minute)
        except ValueError:
            err_msg = 'rate_per_minute must be a float '
            err_msg += f'(rate_per_minute = \'{rate_per_minute}\')'
            raise ValueError(err_msg)
        if (rate_per_minute < 0.01) or (rate_per_minute > 20):
            err_msg = f'Rate ({rate_per_minute} K/min) out of '
            err_msg += 'bounds.  Must be between 0.01 and 20 K/min'
            raise MultiPyVuError(err_msg)

        return f'{set_point},{rate_per_minute},{approach_mode.value}'

    def convert_state_dictionary(self, status_number) -> str:
        if isinstance(status_number, str):
            return status_number
        else:
            return STATE_DICT[status_number]

    def state_code_dict(self):
        return STATE_DICT

    @abstractmethod
    def get_state_server(self, value_variant, state_variant,  params=''):
        raise NotImplementedError

    @abstractmethod
    def _set_state_imp(self,
                       temperature: float,
                       set_rate_per_min: float,
                       set_approach: ApproachEnum
                       ) -> Union[str, int]:
        raise NotImplementedError

    def set_state_server(self, arg_string: str) -> Union[str, int]:
        if len(arg_string.split(',')) != 3:
            err_msg = 'Setting the temperature requires three numeric inputs, '
            err_msg += 'separated by a comma: '
            err_msg += 'Set Point (K), '
            err_msg += 'rate (K/min), '
            err_msg += 'approach:'
            for mode in self.approach_mode:
                err_msg += f'\n\t{mode.value}: approach_mode.{mode.name}'
            return err_msg
        temperature, rate, approach = arg_string.split(',')
        temperature = float(temperature)
        if temperature < 0:
            err_msg = "Temperature must be a positive number."
            return err_msg
        set_rate_per_min = float(rate)
        set_approach_number = int(approach)
        if set_approach_number > len(self.approach_mode) - 1:
            err_msg = f'The approach, {set_approach_number}, is out of bounds.  Must be '
            err_msg += 'one of the following'
            for mode in self.approach_mode:
                err_msg += f'\n\t{mode.value}: approach_mode.{mode.name}'
            return err_msg
        set_approach = ApproachEnum(set_approach_number)

        err = self._set_state_imp(temperature,
                                  set_rate_per_min,
                                  set_approach)
        return err


############################
#
# Standard Implementation
#
############################


class CommandTemperatureImp(ICommandImp, CommandTemperatureBase):
    def __init__(self, multivu_win32com, instrument_name):
        """
        Parameters:
        ----------
        multivu_win32com: win32.dynamic.CDispatch
        instrument_name: str
        """
        super().__init__()
        self._mvu = multivu_win32com
        self.instrument_name = instrument_name

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
            The value and state number
        """
        can_error = self._mvu.GetTemperature(value_variant, state_variant)
        # On 6/10/25, I found that the PPMS was returning something greater
        # than 1 with this command.  After talking with Mark, I have decided
        # to only check for a value greater than 1 for all systems.
        if can_error > 1:
            raise MultiPyVuError('Error when calling GetTemperature()')
        self.current_val = value_variant.value
        self.state = int(state_variant.value)

        return self.current_val, self.state

    def _set_state_imp(self,
                       temperature: float,
                       set_rate_per_min: float,
                       set_approach: ApproachEnum
                       ) -> Union[str, int]:
        can_error = self._mvu.SetTemperature(temperature,
                                             set_rate_per_min,
                                             set_approach,
                                             )
        self.set_point = temperature
        self.rate = set_rate_per_min
        self.approach = set_approach

        if self.instrument_name in ('PPMS', 'MPMS3'):
            if can_error > 1:
                raise MultiPyVuError('Error when calling SetTemperature()')
            else:
                # returning this string makes CommandMultiVu_base happy
                return 'Call was successful'
        elif can_error > 1:
            raise MultiPyVuError('Error when calling SetTemperature()')
        return can_error

    def _temperature_at_setpoint(self) -> bool:
        # find the percentage off, and exit if within specs
        if self.set_point < 20.0:
            # brochure says 0.1%, so I am going a little higher
            return floats_equal(self.current_val,
                                self.set_point,
                                1e-3,
                                self.set_point * 0.001,
                                )
        else:
            # brochure says 0.02%, but MultiVu breaks out earlier
            # the breakout value here was determined by unit tests
            return floats_equal(self.current_val,
                                self.set_point,
                                1e-3,
                                self.set_point * 0.0002,
                                )

    def test(self) -> bool:
        """
        This method is used to monitor the temperature. It waits for
        the status to become 'stable' at the set point

        Returns:
        --------
        bool
        """
        self._get_values()
        state_name = self.convert_state_dictionary(self.state)
        steady = (state_name == 'Stable' and self._temperature_at_setpoint())
        return steady


############################
#
# Scaffolding Implementation
#
############################

@catch_thread_error
class SimulateTemperatureChange(ISimulateChange):
    # class variables
    _stop_flag: bool = False
    _val: float
    _state: str
    _set_point: float
    _rate: float
    _approach: Union[ApproachEnum, int] = ApproachEnum.fast_settle
    _observers: List[IObserver] = []

    def __init__(self):
        super().__init__('SimulateTemperatureChange')

    @property
    def current_val(self):
        return SimulateTemperatureChange._val

    @current_val.setter
    def current_val(self, new):
        SimulateTemperatureChange._val = new

    @property
    def set_point(self):
        return SimulateTemperatureChange._set_point

    @set_point.setter
    def set_point(self, new):
        SimulateTemperatureChange._set_point = new

    @property
    def rate(self):
        return SimulateTemperatureChange._rate

    @rate.setter
    def rate(self, new):
        SimulateTemperatureChange._rate = new

    @property
    def approach(self):
        return SimulateTemperatureChange._approach

    @approach.setter
    def approach(self, new):
        SimulateTemperatureChange._approach = new

    def stop_requested(self):
        return SimulateTemperatureChange._stop_flag

    def stop_thread(self, set_stop=True):
        SimulateTemperatureChange._stop_flag = set_stop

    def check_esc(self):
        try:
            _check_windows_esc()
        except KeyboardInterrupt:
            self.stop_thread()

    def _monitor(self):
        """
        This private method is used to simulate the temperature change.
        """
        starting_temp = self.current_val
        self.state = STATE_DICT[1]
        self.notify_observers(self.current_val, self.state)

        # simulate a pause before changing the temperature
        start_time = time.time()
        while time.time() - start_time < 1:
            time.sleep(CLOCK_TIME)

            # check if the main thread has killed this process
            if self.stop_requested():
                return
            # check the escape key
            self.check_esc()

        # set up the ramp
        delta_temp = self.set_point - starting_temp
        rate_per_sec = self.rate / 60
        rate_per_sec *= -1 if delta_temp < 0 else 1
        rate_time = delta_temp / rate_per_sec
        ramp_start_time = time.time()
        self.state = STATE_DICT[2]
        self.notify_observers(self.current_val, self.state)

        # simulate the ramp
        while (time.time() - ramp_start_time) < rate_time:
            if self.stop_requested():
                return
            time.sleep(CLOCK_TIME)
            self.acquire_mutex()
            self.current_val += CLOCK_TIME * rate_per_sec
            # The ramp points are discrete, so they can
            # pass over the set point.  This check ensures
            # that there is no overshoot.
            if rate_per_sec > 0:
                self.current_val = min(self.current_val,
                                       self.set_point)
            else:
                self.current_val = max(self.current_val,
                                       self.set_point)
            self.release_mutex()
            self.notify_observers(self.current_val, self.state)

            # check the escape key
            self.check_esc()

        # set the final values
        self.current_val = self.set_point
        self.state = STATE_DICT[5]
        self.notify_observers(self.current_val, self.state)
        stable_start_time = time.time()
        # simulate coming to stability
        while time.time() - stable_start_time < 5.0:
            time.sleep(CLOCK_TIME)
            if self.stop_requested():
                return
            # check the escape key
            self.check_esc()

        self.state = STATE_DICT[1]
        self.notify_observers(self.current_val, self.state)

        # unsubscribe from all observers before exiting
        for o in self._observers:
            self.unsubscribe(o)
        return


class CommandTemperatureSim(CommandTemperatureBase,
                            ICommandObserverSim,
                            ):

    def __init__(self):
        CommandTemperatureBase.__init__(self)
        ICommandObserverSim.__init__(self,
                                     SimulateTemperatureChange,
                                     )

    def get_state_server(self,
                         value_variant,
                         state_variant,
                         params='') -> Tuple[float, int]:
        return self.current_val, self.state

    def _set_state_imp(self,
                       temperature: float,
                       set_rate_per_min: float,
                       set_approach: ApproachEnum
                       ) -> Union[str, int]:
        # Get an instance of SimulateTemperatureChange.
        self.change_thread: SimulateTemperatureChange = self.get_sim_instance()
        state_string = STATE_DICT[self.state]
        self.change_thread.set_params(self.current_val,
                                      temperature,
                                      set_rate_per_min,
                                      state_string,
                                      )
        self.set_point = temperature
        self.rate = set_rate_per_min
        self.approach = set_approach
        self.change_thread.approach = set_approach

        self.change_thread.subscribe(self)
        self.change_thread.start()
        error = 0
        return error

    def update(self, value, state):
        self.current_val = value
        for state_number, state_str in STATE_DICT.items():
            if state_str == state:
                self.state = state_number
                break
