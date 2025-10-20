"""
CommandSdo.py is used to read and write SDOs

@author: djackson
"""

import logging
import re
import struct
from abc import abstractmethod
from sys import platform
from typing import Dict, Tuple, Union

from .exceptions import (CanError, MultiPyVuError, PwinComError,
                         PythoncomImportError, abort_err_enum, can_err_enum)
from .ICommand import ICommand
from .project_vars import CLIENT_NAME, SERVER_NAME
from .sdo_object import SdoObject, val_type

if platform == 'win32':
    try:
        import pythoncom
        import win32com.client as win32
        from pywintypes import com_error as pywin_com_error
    except ImportError:
        raise PythoncomImportError


units = ''

############################
#
# Base Class
#
############################


class CommandSdoBase(ICommand):
    def __init__(self):
        super().__init__()

        self.units = units
        self.status_number = can_err_enum.R_OK
        self.logger_server = logging.getLogger(SERVER_NAME)
        self.logger_client = logging.getLogger(CLIENT_NAME)

    def _is_int(self, v_type: val_type) -> bool:
        int_types = [
            val_type.short_t,
            val_type.ushort_t,
            val_type.int_t,
            val_type.uint_t,
            val_type.long_t,
            val_type.ulong_t,
            ]
        return v_type in int_types

    def _is_float(self, v_type: val_type) -> bool:
        float_types = [
            val_type.double_t,
            val_type.single_t
            ]
        return v_type in float_types

    def _is_str(self, v_type: val_type) -> bool:
        type_is_str = v_type is val_type.string_t
        return type_is_str

    def _errors_to_str(self, can_err: int, abort_err: int) -> str:
        """
        convert the can_err and abort_err numbers into a string
        of the format (can_err;abort_err)
        """
        return f'({can_err};{abort_err})'

    def _str_to_errors(self, err_str: str) -> Tuple[int, int]:
        """
        convert a string of can_err and abort_err to numbers
        """
        try:
            search_str = r'\(([\-0-9]*);([0-9]*)\)'
            [search_rslt] = re.findall(search_str, err_str)
            can_err_as_str, abort_err_as_str = search_rslt
            can_err_as_int = int(can_err_as_str)
            abort_err_as_int = int(abort_err_as_str)
        except BaseException as e:
            msg = 'String can not be converted into two numbers'
            raise ValueError(f'{msg}:  {err_str}') from e
        return can_err_as_int, abort_err_as_int

    def convert_result(self, response: Dict) -> Tuple:
        """
        Converts the CommandMultiVu response from get_state_server()
        to something usable for the user.

        Parameters:
        -----------
        response: dict:
            command, result_string, '' (variable type), code_in_words

        Returns:
        --------
        Value and error status returned from read/write
        """
        r = response['result'].split(',')
        if len(r) == 3:
            val, _, status = r
        elif len(r) == 1:
            val = '0'
            [status] = r
        else:
            msg = f'Invalid response: {response}'
            raise MultiPyVuError(msg)
        if status == 'Call was successful':
            sdo = SdoObject.str_to_obj(response['query'])
            if self._is_int(sdo.val_type):
                val = int(float(val))
            elif self._is_float(sdo.val_type):
                val = float(val)
        return val, status

    def prepare_query(self,
                      val: Union[str, int, float],
                      sdo: SdoObject) -> str:
        """
        Returns a string with the format:
        sdo_object,val
        """
        return f'{sdo},{val}'

    def convert_state_dictionary(self, status_number: str) -> str:
        """
        Takes a string with the can error and abort error in the form
        of (can_error;abort_error) and returns a human readable
        description of the error.

        Parameters:
        -----------
        statusNumber: str
            can and abort errors separated by a semicolon and contained
            inside parentheses

        Returns:
        -------
        A string of the error in words.
        """
        can_err_as_int, abort_err_as_int = self._str_to_errors(status_number)
        return str(CanError(can_err_as_int, abort_err_as_int))

    def state_code_dict(self):
        state_dict = {}
        for can_num, abort_num in zip(can_err_enum, abort_err_enum):
            state_dict[can_num, abort_num] = str(CanError(can_num, abort_num))
        return state_dict

    @abstractmethod
    def get_state_server(self,
                         value_variant,
                         state_variant,
                         params: str = ''):
        raise NotImplementedError

    @abstractmethod
    def set_state_server(self, arg_string: str) -> Union[str, int]:
        raise NotImplementedError


############################
#
# Standard Implementation
#
############################


class CommandSdoImp(CommandSdoBase):
    """
    This class is used to read and write SDOs
    """
    def __init__(self, multivu_win32com):
        """
        Parameters:
        -----------
        multivu_win32com: Union[win32.dynamic.CDispatch, None]
        """
        super().__init__()
        self._mvu = multivu_win32com

    def _binary_to_value(self,
                         sdo: SdoObject,
                         length,
                         val) -> Union[str, int, float]:
        """
        Convert a binary value from reading an SDO into its correct
        type.

        Parameters:
        -----------
        sdo: SdoObject
        length: win32com.client.VARIANT
            This is the parameter used in ReadSDO which
            holds the length of the value that was read.
        val: win32com.client.VARIANT
            This is the parameter used in ReadSDO which
            holds the value being read.

        Returns:
        --------
        The value being returned from ReadSDO in its native
        python format of string, int, or float.
        """
        if sdo.val_type is val_type.string_t:
            var_memory = val.value[0:length.value - 1]
            return_val = bytes(var_memory).decode('utf-8')
        elif sdo.val_type in (val_type.short_t,
                              val_type.int_t,
                              val_type.long_t):
            b = list(bytes(val.value)[0:length.value])
            return_val = int.from_bytes(b,
                                        byteorder='little',
                                        signed=True)
        elif sdo.val_type in (val_type.ushort_t,
                              val_type.uint_t,
                              val_type.ulong_t):
            b = list(bytes(val.value)[0:length.value])
            return_val = int.from_bytes(b,
                                        byteorder='little',
                                        signed=False)
        elif sdo.val_type in (val_type.single_t,
                              val_type.double_t):
            b = bytes(val.value)[0:length.value]
            # format = '<f' means little endian ('>f' is big endian)
            [return_val] = struct.unpack('<f', b)
        else:
            raise ValueError('unsupported variant type')
        return return_val

    def _value_to_binary(self,
                         sdo: SdoObject,
                         val: Union[str, int, float]) -> bytes:
        """
        Convert a value being sent to WriteSDO into binary.

        Parameters:
        -----------
        sdo: sdo_object
        val: str, int, or float
            The value in native python type that needs to be
            converted to bytes for use in WriteSDO

        Returns:
        --------
        The value being set in binary.
        """
        sdo_length = sdo.object_length()
        sdo_val = b''
        if sdo.val_type in (val_type.short_t, val_type.ushort_t):
            sdo_val = int(val).to_bytes(sdo_length, 'little', signed=False)
        elif sdo.val_type in (val_type.int_t, val_type.uint_t):
            sdo_val = int(val).to_bytes(sdo_length, 'little', signed=False)
        elif sdo.val_type in (val_type.long_t, val_type.ulong_t):
            sdo_val = int(val).to_bytes(sdo_length, 'little', signed=False)
        elif sdo.val_type in (val_type.single_t, val_type.double_t):
            sdo_val = struct.pack('<f', float(val))
        elif sdo.val_type is val_type.string_t:
            sdo_val = val.encode()
        else:
            msg = 'Unsupported val_type: ' + str(sdo)
            raise ValueError(msg)
        return sdo_val

    def read_sdo(self, sdo: SdoObject,) -> Tuple:
        """
        Configures and reads an SDO value.

        Parameters:
        -----------
        sdo: sdo_object

        Returns:
        --------
        A tuple with the first term the value that was read from
        the SDO, and the second value is a string that looks like
        a tuple whose first term is the CAN error and the second
        term is the abort error.
        """
        length_variant = win32.VARIANT(
                            pythoncom.VT_BYREF | pythoncom.VT_I4,
                            0)
        value_variant = win32.VARIANT(
                            pythoncom.VT_BYREF | pythoncom.VT_VARIANT,
                            bytes(255))
        error_variant = win32.VARIANT(
                            pythoncom.VT_BYREF | pythoncom.VT_I4,
                            0)
        return_val = 0
        can_error: int = can_err_enum.R_OK
        try:
            can_error = self._mvu.ReadSDO(sdo.node,
                                          sdo.index,
                                          sdo.sub,
                                          length_variant,
                                          value_variant,
                                          error_variant)
            self.return_state = self._errors_to_str(can_error,
                                                    error_variant.value)
        except pywin_com_error as e:
            return_val = str(PwinComError(e))
            self.return_state = self._errors_to_str(can_err_enum.R_ERR,
                                                    error_variant.value)
        if (can_error != can_err_enum.R_OK) or (error_variant.value != 0):
            err_msg = str(CanError(can_error, error_variant.value))
            msg = 'ReadSDO returned error '
            msg += f"'{can_error}: {err_msg}' "
            msg += f'while reading ({str(sdo)})'
            raise MultiPyVuError(msg)
        else:
            return_val = self._binary_to_value(sdo,
                                               length_variant,
                                               value_variant)

        return return_val, self.return_state

    def write_sdo(self,
                  sdo: SdoObject,
                  val: Union[str, int, float]) -> str:
        """
        This configures the parameters and then calls WriteSDO.

        Parameters:
        -----------
        sdo: sdo_object
            The sdo info for what is being written.
        val: str, int, or float
            The value being written

        Returns:
        --------
        string with the error from MultiVu
        """
        binary_val = self._value_to_binary(sdo, val)
        data_length = sdo.object_length()
        value_variant = win32.VARIANT(
                            pythoncom.VT_BYREF | pythoncom.VT_VARIANT,
                            binary_val)
        error_variant = win32.VARIANT(
                            pythoncom.VT_BYREF | pythoncom.VT_I4,
                            0)
        can_error: int = can_err_enum.R_OK.value
        try:
            can_error = self._mvu.WriteSDO(sdo.node,
                                           sdo.index,
                                           sdo.sub,
                                           data_length,
                                           value_variant,
                                           error_variant)
            self.return_state = self._errors_to_str(can_error,
                                                    error_variant.value)
        except pywin_com_error as e:
            return str(PwinComError(e))
        if (can_error != can_err_enum.R_OK) or (error_variant.value != 0):
            err_msg = str(CanError(can_error, error_variant.value))
            msg = 'WriteSDO returned error '
            msg += f"'{can_error}: {err_msg}' "
            msg += f'while writing {str(sdo)}'
            self.logger_server.debug(msg)
            self.logger_client.debug(msg)
        return self.return_state

    def get_state_server(self,
                         value_variant,
                         state_variant,
                         params: str) -> Tuple:
        """
        Returns a tuple of the SDO query result and the can_error number.

        Note that the first two input parameters are unused, but included
        because the other CommandXXX classes use them.

        Parameters:
        -----------
        value_variant: (not used)
        state_variant: (not used)
        params: str
            The string representation of an sdo_object

        Returns:
        --------
        A tuple with the first term the value that was read from
        the SDO, and the second value is the CAN error returned
        from the ReadSDO command.
        """
        sdo_input = SdoObject.str_to_obj(params)
        sdo_tuple = self.read_sdo(sdo_input)
        return sdo_tuple

    def set_state_server(self, arg_string: str) -> str:
        """
        Expects a string with the format:
        sdo_object, val
        """
        sdo_str, val = arg_string.split(',')
        sdo = SdoObject.str_to_obj(sdo_str)

        error = self.write_sdo(sdo, val)
        return error


############################
#
# Scaffolding Implementation
#
############################


class CommandSdoSim(CommandSdoBase):
    """
    This class is used to read and write SDOs
    """
    def __init__(self):
        super().__init__()

        CommandSdoSim._int_val = 0
        CommandSdoSim._float_val = 0.0
        CommandSdoSim._str_val = 'simulated response'

    def get_state_server(self, value_variant, state_variant, params) -> Tuple:
        """
        Returns a tuple of the SDO query result and the can_error number.

        Note that the first two input parameters are unused, but included
        because the other CommandXXX classes use them.

        Parameters:
        -----------
        value_variant: (not used)
        state_variant: (not used)
        params: str
            The string representation of an SdoObject

        Returns:
        --------
        A tuple with the first term the value that was read from
        the SDO, and the second value is the CAN error returned
        from the ReadSDO command.
        """
        sdo_input = SdoObject.str_to_obj(params)
        status = self._errors_to_str(can_err_enum.R_OK,
                                     abort_err_enum.NORMAL_CONF)
        if self._is_int(sdo_input.val_type):
            val = CommandSdoSim._int_val
        elif self._is_float(sdo_input.val_type):
            val = CommandSdoSim._float_val
        elif self._is_str(sdo_input.val_type):
            val = CommandSdoSim._str_val
        else:
            val = ''
            status = self._errors_to_str(can_err_enum.R_INVALID,
                                         abort_err_enum.NORMAL_CONF)
        sdo_tuple = val, status
        return sdo_tuple

    def set_state_server(self, arg_string: str) -> str:
        """
        Expects a string with the format:
        SdoObject, val

        Returns:
        --------
        string with the error from MultiVu
        """
        sdo_str, val = arg_string.split(',')
        sdo = SdoObject.str_to_obj(sdo_str)

        if self._is_int(sdo.val_type):
            CommandSdoSim._int_val = int(val)
        elif self._is_float(sdo.val_type):
            CommandSdoSim._float_val = float(val)
        elif self._is_str(sdo.val_type):
            CommandSdoSim._str_val = val

        error = self._errors_to_str(can_err_enum.R_OK, 0)
        return error
