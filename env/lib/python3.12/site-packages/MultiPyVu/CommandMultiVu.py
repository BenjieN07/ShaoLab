# -*- coding: utf-8 -*-
"""
This is a factory method to call up the specific MultiVu commands.

Note that the accessible OLE commands are listed here:
http://svnserver/viewsvn/software/MultiVu/OptiCool/trunk/IMultiVuPpmsServer.h?revision=81290&view=markup

Created on Sat June 12 17:35:28 2021

@author: djackson
"""

import logging
from abc import abstractmethod
from sys import platform
from typing import Dict, Tuple

from .exceptions import MultiPyVuError, PythoncomImportError
from .ICommand import ICommand
from .project_vars import SERVER_NAME

if platform == 'win32':
    try:
        import pythoncom
        import win32com.client as win32
    except ImportError:
        raise PythoncomImportError


class CommandMultiVuBase():
    """
    This class is a factory method which is used as a getter and a
    setter for MultiVu commands.

    Parameters:
    -----------
    cmd_dict: Dict[str, ICommand]
        The key is the name of the command (TEMP, FIELD, etc) and the value
        is the object associated with the name.
    """
    def __init__(self, cmd_dict: Dict[str, ICommand]):
        self.logger = logging.getLogger(SERVER_NAME)
        self.cmd_dict = cmd_dict

    def _check_command_name(self, input_command: str):
        """
        Helper method to confirm the input_command exists.

        Parameters:
        -----------
        input_command, str
            The name of the command (TEMP, FIELD, etc.)

        Raises:
        -------
        MultiPyVuError if the input_command is unknown or not implemented.
        """
        if input_command not in self.cmd_dict:
            raise MultiPyVuError(f'Unknown command: "{input_command}".')

    @abstractmethod
    def _get_state_imp(self, mv_command: ICommand, params: str = '') -> Tuple:
        """
        The abstract method which executes the getter

        Parameters:
        -----------
        mv_command: ICommand
            The command object
        params: str
            parameters needed to execute the ICommand object
        """
        raise NotImplementedError

    def get_state(self, command: str, params: str = '') -> str:
        """
        Gets and returns a query from MultiVu.

        Parameters:
        -----------
        command: str
            The name of the command.  Possible choices are the keys
            listed in .cmd_dict.
        params: str, optional
            Input parameters for the command.  Used for reading SDO's

        Returns:
        --------
        str
            result_string, units, code_in_words.

        Raises:
        -------
        MultiVuExeException
            Raises an error if the command is not in the cmd_dict.
        """
        self._check_command_name(command)
        mv_command = self.cmd_dict[command]
        try:
            result, status_number = self._get_state_imp(mv_command, params)
        except AttributeError as e:
            raise MultiPyVuError(f'Command not found:  {e}')
        try:
            # Get the translated state code
            code_in_words = mv_command.convert_state_dictionary(status_number)
        except KeyError:
            msg = f'Returning value = {result} and '
            msg += f'status = {status_number}, '
            msg += 'which could mean MultiVu is not running.'
            raise MultiPyVuError(msg)

        result_string = result if isinstance(result, str) else str(result)
        return f'{result_string},{mv_command.units},{code_in_words}'

    def set_state(self, command: str, arg_string: str) -> str:
        """
        Sets the state for a given command using the arg_string for parameters

        Parameters
        ----------
        command: str
            The name of the command.  Possible choices are the keys
            listed in .cmd_dict.
        arg_string: str
            The arguments that should be passed on to the command.
                TEMP: set point, rate, mode
                FIELD: set point, rate, approach, and magnetic state.
                CHAMBER: mode

        Returns
        -------
        str
            result_string

        Raises
        ------
        MultiVuExeException
            Raises an error if the command is not in the cmd_dict.
        """
        result = ''
        self._check_command_name(command)
        mv_command = self.cmd_dict[command]
        try:
            err = mv_command.set_state_server(arg_string)
        except MultiPyVuError as e:
            raise MultiPyVuError(e.value) from e
        else:
            if isinstance(err, int):
                if err == 0:
                    self.set_state_error_number = 0
                    result = f'{command} Command Received'
                else:
                    msg = f'Error when setting the {command} {arg_string}: '
                    msg += f'error = {err}'
                    raise MultiPyVuError(msg)

            if isinstance(err, str):
                can_error_msg = mv_command.convert_state_dictionary(err)
                if can_error_msg == 'Call was successful':
                    self.set_state_error_number = 0
                    result = f'{command} Command Received'
                else:
                    msg = f'Error when setting the {command} {arg_string}: '
                    msg += f'{can_error_msg}'
                    raise MultiPyVuError(msg)
        return result


############################
#
#  Standard Implementation
#
############################


class CommandMultiVuImp(CommandMultiVuBase):
    def __init__(self, cmd_dict: dict):
        super().__init__(cmd_dict)

    def _get_state_imp(self,
                       mv_command: ICommand,
                       params: str = '') -> Tuple:
        # Setting up a by-reference (VT_BYREF) double (VT_R8)
        # variant.  This is used to get the value.
        value_variant = (win32.VARIANT(
            pythoncom.VT_BYREF | pythoncom.VT_R8, 0.0))
        # Setting up a by-reference (VT_BYREF) integer (VT_I4)
        # variant.  This is used to get the status code.
        state_variant = (win32.VARIANT(
            pythoncom.VT_BYREF | pythoncom.VT_I4, 0))
        try:
            response = mv_command.get_state_server(value_variant,
                                                   state_variant,
                                                   params,
                                                   )
            result, status_number = response
        except pythoncom.com_error as e:
            raise MultiPyVuError(e.args[0])
        return (result, status_number)


############################
#
# Scaffolding Implementation
#
############################


class CommandMultiVuSim(CommandMultiVuBase):
    def __init__(self, cmd_dict: dict):
        super().__init__(cmd_dict)

    def _get_state_imp(self, mv_command: ICommand,
                       params: str = '') -> Tuple:
        value_variant = None
        state_variant = None
        result, status_number = mv_command.get_state_server(value_variant,
                                                            state_variant,
                                                            params)
        return (result, status_number)
