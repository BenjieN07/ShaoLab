"""
IView.py an interface for the 'View' part of the Model-
View-Controller design pattern for MultiPyVu.Server

@author: djackson
"""


from abc import ABC, abstractmethod


class IView(ABC):
    @classmethod
    def __subclasshook__(cls, subclass):
        return (
            hasattr(subclass, '__init__')
            and callable(subclass.__init__) and
            hasattr(subclass, 'create_display')
            and callable(subclass.create_display) and
            hasattr(subclass, 'get_connection_status')
            and callable(subclass.get_connection_status) and
            hasattr(subclass, 'server_status')
            and callable(subclass.server_status) and
            hasattr(subclass, 'mvu_flavor')
            and callable(subclass.mvu_flavor) and
            hasattr(subclass, 'start_gui')
            and callable(subclass.start_gui) and
            hasattr(subclass, 'quit_gui')
            and callable(subclass.quit_gui)

            or NotImplemented)

    # Quantum Design colors:
    # QD Red: RGB: 183/18/52 & QD "Black": RGB: 30/30/30
    qd_red = '#B71234'
    qd_black = '#1E1E1E'

    @abstractmethod
    def __init__(self, controller):
        self._controller = controller

    @abstractmethod
    def create_display(self):
        """
        Specifies the gui layout
        """
        raise NotImplementedError

    @abstractmethod
    def get_connection_status(self):
        """
        Queries if a Client is connected
        """
        raise NotImplementedError

    @abstractmethod
    def server_status(self):
        """
        Updates the server status
        """
        raise NotImplementedError

    @property
    @abstractmethod
    def mvu_flavor(self):
        """
        Gets the flavor of the MultiVu which is running
        """
        raise NotImplementedError

    @abstractmethod
    def start_gui(self):
        """
        Opens the gui window and runs the gui.
        """
        raise NotImplementedError

    @abstractmethod
    def quit_gui(self):
        """
        Close the gui and its window.
        """
        raise NotImplementedError
