"""
CommandFieldSetPoints.py has the information required to get the
temperature set points.

Created on Tue May 18 13:14:28 2021

@author: djackson
"""

import re
from abc import abstractmethod
from enum import IntEnum
from sys import platform
from typing import Dict, Tuple, Union

from .CommandField import CommandFieldSim
from .exceptions import MultiPyVuError, PythoncomImportError
from .ICommand import ICommand

if platform == 'win32':
    try:
        import pythoncom
        import win32com.client as win32
    except ImportError:
        raise PythoncomImportError


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


units = 'Oe'

############################
#
# Base Class
#
############################


class CommandFieldSetPointsBase(ICommand):
    _set_point: float = 300.0
    _rate: float = 1.0
    _approach: ApproachEnum = ApproachEnum.linear
    _driven = drivenEnum.driven

    def __init__(self, instrument_name: str):
        super().__init__()
        self.instrument_name = instrument_name

        self.units = units

    def set_point(self):
        return CommandFieldSetPointsBase._set_point

    def rate(self):
        return CommandFieldSetPointsBase._rate

    def approach(self):
        return CommandFieldSetPointsBase._approach

    def driven_mode(self) -> drivenEnum:
        return CommandFieldSetPointsBase._driven

    def convert_result(self, response: Dict[str, str]) -> Tuple[float,
                                                                float,
                                                                ApproachEnum,
                                                                drivenEnum]:
        """
        Converts the CommandMultiVu response from get_state_server()
        to something usable for the user.

        Parameters:
        -----------
        response: Dict:
            Message.response['content']

        Returns:
        --------
        Tuple of value, rate, and approach mode.
        """
        search_str = r'\(([0-9.\-]*),[ ]?([0-9.\-]*),[ ]?([0-9]*),[ ]?([0-9]*)\),[ ]?([a-zA-Z]*),[ ]?([ a-zA-Z]*)'
        r = re.findall(search_str, response['result'])
        if len(r[0]) != 6:
            msg = f'Invalid response: {response}'
            raise MultiPyVuError(msg)
        temp_str, rate_str, appr_str, driven, units, _ = r[0]
        temp = float(temp_str)
        rate = float(rate_str)
        appr_num = int(appr_str)
        appr_mode = ApproachEnum(appr_num)
        driven_num = int(driven)
        driven_mode = drivenEnum(driven_num)
        return temp, rate, appr_mode, driven_mode

    def prepare_query(self, *args):
        raise NotImplementedError

    def convert_state_dictionary(self, status_number) -> str:
        """
        This query has no state dictionary. The status number
        is ignored and it returns a simple string.

        Arguments:
            status_number -- unused

        Returns:
            'Call was successful'
        """
        return 'Call was successful'

    def state_code_dict(self):
        raise NotImplementedError

    @abstractmethod
    def _get_state_imp(self,
                       value_variant,
                       state_variant,
                       params='') -> Tuple[float,
                                           float,
                                           int,
                                           int]:
        """
        Gets the temperature set points

        Returns:
            [temperature, rate, approach mode as int, drive mode as int]
        """
        raise NotImplementedError

    def get_state_server(self, value_variant, state_variant,  params=''):
        field, rate, approach, driven = self._get_state_imp(value_variant,
                                                            state_variant,
                                                            params)
        if self.instrument_name == 'MPMS3':
            raise MultiPyVuError('MPMS3 does not support getting field set points')
        self._set_point = field
        self._rate = rate
        self._approach = ApproachEnum(approach)
        self._driven = drivenEnum(driven)
        return (field, rate, approach, driven), 0

    def set_state_server(self, arg_string: str) -> Union[str, int]:
        raise NotImplementedError


############################
#
# Standard Implementation
#
############################


class CommandFieldSetPointsImp(CommandFieldSetPointsBase):
    def __init__(self, instrument_name, multivu_win32com):
        """
        Parameters:
        ----------
        instrument_name: str
        multivu_win32com: win32.dynamic.CDispatch
        """
        super().__init__(instrument_name)
        self._mvu = multivu_win32com

    def _get_state_imp(self,
                       value_variant,
                       state_variant,
                       params='') -> Tuple[float,
                                           float,
                                           int,
                                           int]:
        """
        Retrieves information from MultiVu

        Parameters:
        -----------
        value_variant: VARIANT: set up by pywin32com for getting the value
        state_variant: VARIANT: set up by pywin32com for getting the approach mode
        params: str (optional)
            optional parameters that may be required to query MultiVu

        Returns:
        --------
        Tuple(str, str, str, str)
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

            command = 'FIELD?'
            device = 0
            timeout = 0
            # This command returns nonsense if there is no Model6000 attached.
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
                err_msg += f'temperature setpoints: "{response}"'
                err_msg += f' error = "{error}"'
                raise MultiPyVuError(err_msg)
            set_point, rate, approach, mode = response
            set_point = float(set_point)
            rate = float(rate)
            approach = int(approach)
            mode = int(mode)
            return set_point, rate, approach, mode
        else:
            # Setting up a by-reference (VT_BYREF) double (VT_R8)
            # variant.  This is used to get the value.
            rate_variant = (win32.VARIANT(
                pythoncom.VT_BYREF | pythoncom.VT_R8, 0.0))
            # Setting up a by-reference (VT_BYREF) integer (VT_I4)
            # variant.  This is used to get the status code.
            mode_variant = (win32.VARIANT(
                pythoncom.VT_BYREF | pythoncom.VT_I4, 0))
            if self.instrument_name == 'VERSALAB':
                can_error = self._mvu.GetLastFieldSetpoint(value_variant,
                                                           rate_variant,
                                                           state_variant,
                                                           mode_variant)
            else:
                can_error = self._mvu.GetFieldSetpoints(value_variant,
                                                        rate_variant,
                                                        state_variant,
                                                        mode_variant)
            # On 6/10/25, I found that the PPMS was returning something greater
            # than 1 with commands.  After talking with Mark, I have decided
            # to only check for a value greater than 1 for all systems.
            if can_error > 1:
                raise MultiPyVuError('Error when calling GetFieldSetpoints()')
            set_point = value_variant.value
            rate = rate_variant.value
            approach = state_variant.value
            driven = mode_variant.value
            return set_point, rate, approach, driven


############################
#
# Scaffolding Implementation
#
############################

class CommandFieldSetPointsSim(CommandFieldSetPointsBase):

    def __init__(self, instrument_name: str):
        CommandFieldSetPointsBase.__init__(self, instrument_name)

    def _get_state_imp(self,
                       value_variant,
                       state_variant,
                       params='') -> Tuple[float,
                                           float,
                                           int,
                                           int]:
        # The code is retrieving the values and the specific mvu flavor
        # does not matter, so picking the PPMS
        field = CommandFieldSim('PPMS')
        # This part converts the enum types from CommandField to CommandFieldSetPoints
        approach = field.approach.value
        drive = field.driven.value
        return field.set_point, field.rate, approach, drive
