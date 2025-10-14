# -*- coding: utf-8 -*-
"""
CommandChamber has the information required to get and set the chamber state.

Created on Tue May 18 13:14:28 2021

@author: djackson
"""

from abc import abstractmethod
from enum import IntEnum
from typing import Dict, List, Tuple, Union

from .exceptions import MultiPyVuError
from .ICommand import (ICommand, ICommandImp, ICommandObserverSim,
                       ISimulateChange, catch_thread_error)
from .IEventManager import IObserver


class modeEnum(IntEnum):
    seal = 0
    purge_seal = 1
    vent_seal = 2
    pump_continuous = 3
    vent_continuous = 4
    high_vacuum = 5


# State code dictionary
STATE_DICT: Dict[int, str] = {
    0: 'Unknown',
    1: 'Purged and Sealed',
    2: 'Vented and Sealed',
    3: 'Sealed (condition unknown)',
    4: 'Performing Purge/Seal',
    5: 'Performing Vent/Seal',
    6: 'Pre-HiVac',
    7: 'HiVac',
    8: 'Pumping Continuously',
    9: 'Flooding Continuously',
    14: 'HiVac Error',
    15: 'General Failure'
}


units = ''

############################
#
# Base Class
#
############################


class CommandChamberBase(ICommand):
    # class variables
    _set_point: int = modeEnum.vent_seal
    _current_val: float = modeEnum.vent_seal
    _state: int = 3

    def __init__(self, instrument_name: str):
        super().__init__()
        self.instrument_name = instrument_name

        self.units = units

    @property
    def current_val(self):
        return CommandChamberBase._current_val

    @current_val.setter
    def current_val(self, new):
        CommandChamberBase._current_val = new

    @property
    def set_point(self):
        return CommandChamberBase._set_point

    @set_point.setter
    def set_point(self, new):
        CommandChamberBase._set_point = new

    @property
    def state(self):
        return CommandChamberBase._state

    @state.setter
    def state(self, new):
        CommandChamberBase._state = new

    def convert_result(self, response: Dict[str, str]) -> Tuple:
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
            n = 2
        elif len(r) == 1:
            n = 0
        else:
            msg = f'Invalid response: {response}'
            raise MultiPyVuError(msg)
        return (0.0, r[n])

    def prepare_query(self, mode: IntEnum) -> str:
        try:
            mode_as_int = mode.value
        except ValueError:
            msg = 'mode must be an integer. One could use the .modeEnum'
            raise ValueError(msg)
        return f'{mode_as_int}'

    def convert_state_dictionary(self, status_number):
        if isinstance(status_number, str):
            return status_number
        else:
            return STATE_DICT[status_number]

    @abstractmethod
    def get_state_server(self, value_variant, state_variant,  params=''):
        raise NotImplementedError

    @abstractmethod
    def _set_state_imp(self, mode: modeEnum) -> Union[str, int]:
        raise NotImplementedError

    def set_state_server(self, arg_string) -> Union[str, int]:
        if self.instrument_name == 'OPTICOOL':
            err_msg = 'set_chamber() is not available for the OptiCool'
            raise MultiPyVuError(err_msg)
        if len(arg_string.split(',')) != 1:
            err_msg = 'Setting the chamber requires 1 input: mode'
            return err_msg
        set_mode = int(arg_string)
        if set_mode > len(modeEnum) - 1:
            err_msg = f'The selected mode, {set_mode}, is '
            err_msg += 'out of bounds.  Must be one of the following:'
            for m in modeEnum:
                err_msg += f'\n\t{m.value}: {m.name}'
            raise MultiPyVuError(err_msg)
        self.state = modeEnum(set_mode)
        return self._set_state_imp(self.state)

    def state_code_dict(self):
        return STATE_DICT


############################
#
#  Standard Implementation
#
############################


class CommandChamberImp(ICommandImp, CommandChamberBase):
    def __init__(self, multivu_win32com, instrument_name):
        """
        Parameters:
        ----------
        multivu_win32com: win32.dynamic.CDispatch
        instrument_name: str
        """
        CommandChamberBase.__init__(self, instrument_name)
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
        Tuple(float, int)
            The value (0.0 in the case of the chamber) and state number
        """
        if self.instrument_name == 'OPTICOOL':
            err_msg = 'get_chamber() is not available for the OptiCool'
            raise MultiPyVuError(err_msg)
        can_error = self._mvu.GetChamber(state_variant)
        # On 6/10/25, I found that the PPMS was returning something greater
        # than 1 with the GetTemperature() command.  After talking with Mark,
        # I have decided to only check for a value greater than 1 for all
        # systems.
        if can_error > 1:
            raise MultiPyVuError('Error when calling GetChamber()')
        self.state = int(state_variant.value)

        return 0.0, self.state

    def _set_state_imp(self, mode: modeEnum) -> Union[str, int]:
        can_error = self._mvu.SetChamber(mode)
        self.set_point = mode

        if self.instrument_name in ('PPMS', 'DYNACOOL', 'MPMS3'):
            if can_error > 1:
                raise MultiPyVuError('Error when calling SetChamber()')
            else:
                # returning this string makes CommandMultiVu_base happy
                return 'Call was successful'
        elif can_error > 1:
            raise MultiPyVuError('Error when calling SetChamber()')
        return can_error

    def test(self) -> bool:
        """
        This method is used to monitor the chamber. It waits for
        the status to become 'stable' at the set point

        Returns:
        --------
        bool
        """
        self._get_values()
        state_name = self.convert_state_dictionary(self.state)
        if self.set_point == modeEnum.seal:
            if state_name in [STATE_DICT[1],
                              STATE_DICT[2],
                              STATE_DICT[3],
                              ]:
                return True
        elif self.set_point == modeEnum.purge_seal:
            return (state_name == STATE_DICT[1])
        elif self.set_point == modeEnum.vent_seal:
            if state_name in [STATE_DICT[1],
                              STATE_DICT[2],
                              STATE_DICT[3],
                              ]:
                return True
        elif self.set_point == modeEnum.high_vacuum:
            return (state_name == STATE_DICT[7])
        elif self.set_point == modeEnum.pump_continuous:
            return (state_name == STATE_DICT[8])
        elif self.set_point == modeEnum.vent_continuous:
            if self.instrument_name == 'PPMS':
                return (state_name == STATE_DICT[5])
            else:
                return (state_name == STATE_DICT[9])
        else:
            msg = f'invalid mode setting: {self.set_point}'
            raise MultiPyVuError(msg)
        return False


############################
#
# Scaffolding Implementation
#
############################

@catch_thread_error
class SimulateChamberChange(ISimulateChange):
    # class variables
    _stop_flag: bool = False
    _val: float
    _state: str
    _set_point: float
    _rate: float
    _flavor: str
    _observers: List[IObserver] = []

    def __init__(self):
        super().__init__('SimulateChamberChange')

    @property
    def current_val(self):
        return SimulateChamberChange._val

    @current_val.setter
    def current_val(self, new):
        SimulateChamberChange._val = new

    @property
    def set_point(self):
        return SimulateChamberChange._set_point

    @set_point.setter
    def set_point(self, new):
        SimulateChamberChange._set_point = new

    @property
    def rate(self):
        return SimulateChamberChange._rate

    @rate.setter
    def rate(self, new):
        SimulateChamberChange._rate = new

    @property
    def flavor(self) -> str:
        return SimulateChamberChange._flavor

    @flavor.setter
    def flavor(self, new: str):
        SimulateChamberChange._flavor = new

    def stop_requested(self):
        return SimulateChamberChange._stop_flag

    def stop_thread(self, set_stop=True):
        SimulateChamberChange._stop_flag = set_stop

    def _monitor(self):
        self.acquire_mutex()
        if self.stop_requested():
            return
        if self.set_point == modeEnum.seal.value:
            self.state = STATE_DICT[1]
        elif self.set_point == modeEnum.purge_seal.value:
            self.state = STATE_DICT[1]
        elif self.set_point == modeEnum.vent_seal.value:
            self.state = STATE_DICT[2]
        elif self.set_point == modeEnum.high_vacuum.value:
            self.state = STATE_DICT[7]
        elif self.set_point == modeEnum.pump_continuous.value:
            self.state = STATE_DICT[8]
        elif self.set_point == modeEnum.vent_continuous.value:
            if self.flavor == 'PPMS':
                self.state = STATE_DICT[5]
            else:
                self.state = STATE_DICT[9]
        else:
            msg = f'{self.set_point} is an invalid mode'
            raise ValueError(msg)
        self.release_mutex()

        if self.stop_requested():
            return

        self.notify_observers(self.set_point, self.state)
        # unsubscribe from all observers before exiting
        for o in self._observers:
            self.unsubscribe(o)
        return


class CommandChamberSim(CommandChamberBase,
                        ICommandObserverSim,
                        ):
    # class variables
    _set_point: modeEnum = modeEnum.seal
    _current_val: str = ''
    # state is unknown
    _state: int = 0

    def __init__(self, instrument_name: str):
        CommandChamberBase.__init__(self, instrument_name)
        ICommandObserverSim.__init__(self,
                                     SimulateChamberChange,
                                     )
        CommandChamberSim.delta_seconds: float = 0.3

    @property
    def current_val(self):
        return CommandChamberSim._current_val

    @current_val.setter
    def current_val(self, new):
        CommandChamberSim._current_val = new

    @property
    def set_point(self):
        return CommandChamberSim._set_point

    @set_point.setter
    def set_point(self, new):
        CommandChamberSim._set_point = new

    @property
    def state(self):
        return CommandChamberSim._state

    @state.setter
    def state(self, new):
        CommandChamberSim._state = new

    def get_state_server(self,
                         value_variant,
                         state_variant,
                         params='') -> Tuple[float, int]:
        if self.instrument_name == 'OPTICOOL':
            err_msg = 'get_chamber() is not available for the OptiCool'
            raise MultiPyVuError(err_msg)
        return 0.0, self.state

    def _set_state_imp(self, mode: modeEnum) -> Union[str, int]:
        self.change_thread: SimulateChamberChange = self.get_sim_instance()
        state_string = STATE_DICT[self.state]
        self.change_thread.set_params('',
                                      mode,
                                      0.0,
                                      state_string,
                                      )
        self.change_thread.flavor = self.instrument_name
        self.change_thread.subscribe(self)
        self.change_thread.start()
        # When testing this, it is easy to ask for the state
        # before the thread has decided the answer.  So put
        # in a delay here to wait until the thread has completed
        # before exiting.
        while self.change_thread.is_sim_alive():
            pass
        error = 0
        return error

    def update(self, value, state):
        for state_number, state_str in STATE_DICT.items():
            if state_str == state:
                self.state = state_number
                break
