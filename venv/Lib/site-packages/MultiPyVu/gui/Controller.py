"""
Controller.py is the controller part of the Model-View-Controller design
pattern for MultiPyVu.py

@author: djackson
"""


import re
import subprocess
import os
from sys import platform
from types import MethodType
from typing import List

from .IController import IController
from .ViewFactory import ViewType, ViewFactory
from ..IEventManager import IObserver
from ..instrument import InstrumentList
from ..MultiVuServer import Server
from ..ParseInputs import inputs_from_command_line


class ServerInfo(IObserver):
    def __init__(self, model_method_obj, view_func):
        """
        When the model object changes, it will update the view variables

        Parameters:
        -----------
        model_method_obj: class method, parameter, or variable
            This is the model properties that we have subscribed to
        view_func: callable method
            This is the view method that is called to get updated.
        """
        self._model_param = model_method_obj
        self._view_func = view_func

    def update(self):
        """
        Updates the view with information from the model
        """
        if isinstance(self._model_param, MethodType):
            if isinstance(self._view_func, MethodType):
                self._view_func(self._model_param())
            else:
                self._view_func = self._model_param()
        else:
            if isinstance(self._view_func, MethodType):
                self._view_func(self._model_param)
            else:
                self._view_func = self._model_param


class Controller(IController):
    """
    This is the 'controller' class of the Model-View-Controller design pattern.
    This is the entry point for the gui.
    """
    def __init__(self, flags: List):
        """
        Parameters:
        -----------
        flags: List
            This is the command line arguments
        """
        super().__init__()
        flag_info = inputs_from_command_line(flags)
        self._scaffolding = flag_info.scaffolding_mode
        self._flags = []
        self._flags.append(f'-ip={flag_info.host}')
        self._flags.append(f'-p={flag_info.port}')
        if flag_info.scaffolding_mode:
            self._flags.append('-s')
        if flag_info.instrument_str:
            self._flags.append(f'{flag_info.instrument_str}')

        self.model = Server(flags)
        self.view = ViewFactory().create(ViewType.tk, self)
        self.model.port = flag_info.port
        self.model.update_address((self.ip_address, flag_info.port))
        self._si_status = ServerInfo(self.server_status,
                                     self.view.server_status,
                                     )
        self.model.subscribe(self._si_status)
        self._si_num_connections = ServerInfo(self.model.number_of_clients,
                                              self.view.set_number_of_clients,
                                              )
        self.model.subscribe(self._si_num_connections)
        self._si_port = ServerInfo(self.model.port,
                                   self.view.port,
                                   )
        self.model.subscribe(self._si_port)
        self.view.create_display()

    def start_gui(self):
        """
        Starts the gui
        """
        self.view.start_gui()

    def quit_gui(self):
        """
        Quits the gui
        """
        self.model.unsubscribe(self._si_status)
        self.model.unsubscribe(self._si_num_connections)
        self.model.unsubscribe(self._si_port)
        self.view.quit_gui()

    def absolute_path(self, filename: str) -> str:
        """
        Finds the absolute path of a file based on its location
        relative to the gui module

        Parameters:
        -----------
        filename: str
            The file location based on its relative path from the gui module
        """
        abs_path = os.path.abspath(
            os.path.join(os.path.dirname(
                __file__), './'))
        return os.path.join(abs_path, filename)

    def _get_mvu_flavor(self):
        """
        Get the PPMS flavor and make it look nice
        """
        flavor = self.model.instrument_name()
        if flavor == InstrumentList.DYNACOOL.name:
            return 'DynaCool Running'
        elif flavor == InstrumentList.PPMS.name:
            return 'PPMS Running'
        elif flavor == InstrumentList.VERSALAB.name:
            return 'VersaLab Running'
        elif flavor == InstrumentList.MPMS3.name:
            return 'MPMS3 Running'
        elif flavor == InstrumentList.OPTICOOL.name:
            return 'OptiCool Running'
        else:
            raise ValueError(f"'{flavor}' not supported")

    @property
    def ip_address(self) -> str:
        """
        The IP address for the MultiPyVuServer

        Returns:
        --------
        String with the IP address
        """
        ip_output_str = ''
        search_str = r'([0-9]{1,3}.[0-9]{1,3}.[0-9]{1,3}.[0-9]{1,3})'
        if platform == 'win32':
            ip_addr_script = '../scripts/whats_my_ip_address.cmd'
            ip_addr_script = self.absolute_path(ip_addr_script)
            proc = subprocess.run([ip_addr_script],
                                  capture_output=True,
                                  text=True)
            if proc.returncode != 0:
                print(proc.stderr)
                raise Exception(proc.stderr)
            ip_result = re.findall(search_str, proc.stdout)
            if len(ip_result) == 1:
                self._ip_address = ip_result[0]
        else:
            # using this suggestion:
            # https://apple.stackexchange.com/questions/20547/how-do-i-find-my-ip-address-from-the-command-line
            ifconfig_proc = subprocess.Popen(["ifconfig"],
                                             stdout=subprocess.PIPE,
                                             text=True)
            grep_proc = subprocess.Popen(["grep", "inet"],
                                         stdin=ifconfig_proc.stdout,
                                         stdout=subprocess.PIPE,
                                         text=True)
            ip_output_str, err = grep_proc.communicate()
            if err is not None:
                print(err)
                raise Exception(grep_proc.stderr)
            ip_result = re.findall(search_str, ip_output_str)
            if '127.0.0.1' in ip_result:
                ip_result.remove('127.0.0.1')
            if len(ip_result) >= 1:
                self._ip_address = ip_result[0]
        return self._ip_address

    @ip_address.setter
    def ip_address(self, ip: str):
        """
        The setter for the IP address property

        Parameters:
        -----------
        ip: str
            The user-selected IP address.  Must have the format of 
            four sets of one to three numbers, each separated by a period
        """
        search_str = r'([0-9]{1,3}.[0-9]{1,3}.[0-9]{1,3}.[0-9]{1,3})'
        ip_result = re.findall(search_str, ip)
        if len(ip_result) == 1:
            self._ip_address = ip_result[0]
        else:
            msg = f'Invalid format.  {ip}'
            raise ValueError(msg)

    def get_scaffolding_mode(self) -> bool:
        """
        Returns a bool for the user specified scaffolding mode
        """
        return self._scaffolding

    def set_scaffolding_mode(self, scaffolding: bool) -> None:
        self._scaffolding = scaffolding

    def is_client_connected(self) -> bool:
        """
        Returns a bool if a client is connected
        """
        return self.model.is_client_connected()

    def server_status(self) -> str:
        """
        Queries the server to get its status

        Returns:
        --------
        String containing either 'closed', 'idle', or 'connected'
        """
        return self.model.server_status()

    def start_server(self):
        """
        Start the server using the specified IP address
        """
        self.model.update_address((self.ip_address,
                                   self.view.port))
        server = self.model.open()
        self.view.mvu_flavor = self._get_mvu_flavor()
        return server

    def stop_server(self):
        """
        Disconnect the server.
        """
        self.model.stop()
