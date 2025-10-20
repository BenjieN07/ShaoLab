"""
This provides an interface for the MultiVu Server.

It requires ABCplus (Abstract Base Class plus), which is found here:
    https://pypi.org/project/abcplus/

@author: djackson
"""

from abc import ABC, abstractmethod
from typing import Tuple, Union

from .project_vars import PORT


class IServer(ABC):
    """
    Interface for the MultiVu Server
    """
    @classmethod
    def __subclasshook__(cls, subclass):
        return (
            hasattr(subclass, 'instrument_name')
            and callable(subclass.instrument_name)
            and
            hasattr(subclass, 'open')
            and callable(subclass.open)
            and
            hasattr(subclass, 'close')
            and callable(subclass.close)
            and
            hasattr(subclass, 'is_client_connected')
            and callable(subclass.is_client_connected)
            and
            hasattr(subclass, 'update_address')
            and callable(subclass.update_address)

            or NotImplemented)

    def __init__(self):
        self.host: str = '0.0.0.0'
        self.port: int = PORT

    @abstractmethod
    def instrument_name(self) -> str:
        """
        Returns the MultiVu flavor
        """
        raise NotImplementedError

    @abstractmethod
    def open(self) -> Union['IServer', None]:
        raise NotImplementedError

    @abstractmethod
    def is_client_connected(self) -> bool:
        """
        Returns a bool if a client is connected
        """
        raise NotImplementedError

    @abstractmethod
    def update_address(self, new_address: Tuple[str, int]):
        """
        Updates the Server IP address and port number as long
        as the Server is not currently running
        """
        raise NotImplementedError
