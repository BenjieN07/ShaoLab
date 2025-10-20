"""
IController.py is an interface for the Controller part
of the Model-View-Controller pattern for MultiPyVu.

Note that this class has a concrete __init__() method
which should be called using super().__init__(flags) in
any inherited classes.  The reason for this is that
the member variables such as 'model' and 'view' are
necessary.  But note that this does not define what
those variables should be, leaving that to the concrete
classes.
"""


from abc import ABC, abstractmethod

from .IView import IView
from ..IServer import IServer


class IController(ABC):
    @classmethod
    def __subclasshook__(cls, subclass) -> bool:
        return (
            hasattr(subclass, 'is_client_connected')
            and callable(subclass.is_client_connected) and
            hasattr(subclass, 'start_gui')
            and callable(subclass.start_gui) and
            hasattr(subclass, 'quit_gui')
            and callable(subclass.quit_gui) and
            hasattr(subclass, 'absolute_path')
            and callable(subclass.absolute_path) and
            hasattr(subclass, 'ip_address')
            and callable(subclass.ip_address) and
            hasattr(subclass, 'start_server')
            and callable(subclass.start_server) and
            hasattr(subclass, 'stop_server')
            and callable(subclass.stop_server) and
            hasattr(subclass, 'server_status')
            and callable(subclass.server_status)

            or NotImplemented)

    def __init__(self):
        self.model = IServer
        self.view = IView
        self._ip_address = '0.0.0.0'

    @abstractmethod
    def is_client_connected(self) -> bool:
        """
        Returns a bool if a client is connected
        """
        raise NotImplementedError

    @abstractmethod
    def start_gui(self):
        """
        Starts the gui
        """
        raise NotImplementedError

    @abstractmethod
    def quit_gui(self):
        """
        Quits the gui
        """
        raise NotImplementedError

    @abstractmethod
    def absolute_path(self, filename: str) -> str:
        """
        Finds the absolute path of a file based on its location
        relative to the gui module

        Parameters:
        -----------
        filename: str
            The file location based on its relative path from the gui module
        """
        raise NotImplementedError

    @property
    @abstractmethod
    def ip_address(self) -> str:
        """
        The IP address for the MultiPyVuServer

        Returns:
        --------
        String with the IP address
        """
        raise NotImplementedError

    @ip_address.setter
    @abstractmethod
    def ip_address(self, ip: str):
        """
        The setter for the IP address property

        Parameters:
        -----------
        ip: str
            The user-selected IP address.  Must have the format of 
            four sets of one to three numbers, each separated by a period
        """
        raise NotImplementedError

    @abstractmethod
    def server_status(self) -> str:
        """
        Queries the server to get its status

        Returns:
        --------
        String containing either 'closed', 'idle', or 'connected'
        """
        raise NotImplementedError

    @abstractmethod
    def start_server(self):
        """
        Start the server using the specified IP address
        """
        raise NotImplementedError

    @abstractmethod
    def stop_server(self):
        """
        Disconnect the server.
        """
        raise NotImplementedError
