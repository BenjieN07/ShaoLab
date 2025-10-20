"""
This provides an interface for MultiVu commands (CommandTemperature,
                                                 CommandField,
                                                 and CommandChamber)
as well as an interface to track setting changes which can be used
by the wait_for() command.

It requires ABCplus (Abstract Base Class plus), which is found here:
    https://pypi.org/project/abcplus/

Created on Tue May 18 12:59:24 2021

@author: djackson
"""

from abc import ABC, abstractmethod
from sys import platform
from threading import Lock, Thread, enumerate
from time import sleep, time
from typing import Dict, Generic, Tuple, Type, TypeVar, Union

from .exceptions import PythoncomImportError
from .IEventManager import IObserver, Publisher
from .project_vars import CLOCK_TIME

if platform == 'win32':
    try:
        import pythoncom
        import win32com.client as win32
        from pywintypes import com_error as pywin_com_error
    except ImportError:
        raise PythoncomImportError

T = TypeVar('T', bound='ISimulateChange')


def floats_equal(current_val: float,
                 set_point: float,
                 rel_tol: float,
                 abs_tol: float,
                 ) -> bool:
    """
    Use a combination of relative tolerance and absolute tolerance
    to determine if the values are equal
    """
    diff = abs(current_val - set_point)
    pass_absolute = diff <= abs_tol
    if pass_absolute:
        return pass_absolute

    ave = 0.5 * (current_val + set_point)
    rel_diff = diff / max(abs(ave), 1)
    return rel_diff <= rel_tol


class ICommand(ABC):
    @classmethod
    def __subclasshook__(cls, subclass):
        return (
            hasattr(subclass, 'convert_result')
            and callable(subclass.convert_result)
            and
            hasattr(subclass, 'prepare_query')
            and callable(subclass.prepare_query)
            and
            hasattr(subclass, 'convert_state_dictionary')
            and callable(subclass.convert_state_dictionary)
            and
            hasattr(subclass, 'get_state_server')
            and callable(subclass.get_state_server)
            and
            hasattr(subclass, 'set_state_server')
            and callable(subclass.set_state_server)
            and
            hasattr(subclass, 'state_code_dict')
            and callable(subclass.state_code_dict)

            or NotImplemented)

    @abstractmethod
    def __init__(self):
        self.units = ''

    @abstractmethod
    def convert_result(self, response: Dict) -> Tuple:
        raise NotImplementedError

    @abstractmethod
    def prepare_query(self, *args):
        raise NotImplementedError

    @abstractmethod
    def convert_state_dictionary(self, status_number):
        raise NotImplementedError

    @abstractmethod
    def get_state_server(self,
                         value_variant,
                         state_variant,
                         params: str = '') -> Tuple[float, int]:
        raise NotImplementedError

    @abstractmethod
    def set_state_server(self, arg_string: str) -> Union[str, int]:
        raise NotImplementedError

    @abstractmethod
    def state_code_dict(self) -> Dict:
        raise NotImplementedError

def catch_thread_error(func):
    """
    This decorator is used to catch an error within a function
    """
    def error_handler(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        # ignore keyboard interrupts
        except KeyboardInterrupt as e:
            raise e
    return error_handler


class ICommandImp(ICommand):
    """This interface is used to monitor changes in settings
    in order to help the wait_for() method to see when changes
    have been completed.

    Implement the .run() method, and then start a thread by
    calling .start().  That works because this class overrides
    the Thread.run() method which is called by Thread.start().

    This class inherits CommandPublisher, which is used to
    broadcast the value and status settings.
    """
    @classmethod
    def __subclasshook__(cls, subclass):
        return (hasattr(subclass, 'test')
                and callable(subclass.test)
                or NotImplemented)

    def __init__(self):
        super().__init__()

    def _get_values(self):
        """
        Queries the server
        """
        # Setting up a by-reference (VT_BYREF) double (VT_R8)
        # variant.  This is used to get the value.
        value_variant = (win32.VARIANT(
            pythoncom.VT_BYREF | pythoncom.VT_R8, 0.0)
            )
        # Setting up a by-reference (VT_BYREF) integer (VT_I4)
        # variant.  This is used to get the status code.
        state_variant = (win32.VARIANT(
            pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
            )
        current_info = self.get_state_server(value_variant,
                                             state_variant,
                                             )
        self.current_val, self.state = current_info

    @abstractmethod
    def test(self):
        raise NotImplementedError


class ISimulateChange(Thread, Publisher):
    """This interface is used to monitor changes in settings
    in order to help the wait_for() method to see when changes
    have been completed.

    Implement the .run() method, and then start a thread by
    calling .start().  That works because this class overrides
    the Thread.run() method which is called by Thread.start().

    This class inherits CommandPublisher, which is used to
    broadcast the value and status settings.
    """
    @classmethod
    def __subclasshook__(cls, subclass):
        return (hasattr(subclass, '_monitor')
                and callable(subclass._monitor)
                and
                hasattr(subclass, 'stop_requested')
                and callable(subclass.stop_requested)
                and
                hasattr(subclass, 'stop_thread')
                and callable(subclass.stop_thread)
                or NotImplemented)

    def __init__(self,
                 name: str = 'ISimulateChange',
                 ):
        Thread.__init__(self)
        Publisher.__init__(self)
        self.name = name
        self.daemon = True
        self.mutex = Lock()
        self._stop_flag = False

    def acquire_mutex(self):
        if self.mutex is not None:
            self.mutex.acquire()

    def release_mutex(self):
        if self.mutex is not None:
            self.mutex.release()

    def notify_observers(self, *args) -> None:
        """
        Since the publishers are running in threads,
        do a thread lock before notifying everyone.
        """
        self.acquire_mutex()
        super().notify_observers(*args)
        self.release_mutex()

    def is_sim_alive(self):
        alive = False
        for t in enumerate():
            if t.name == self.name:
                alive = True
                break
        return alive

    @abstractmethod
    def stop_thread(self, set_stop=True):
        self.acquire_mutex()
        self._stop_flag = set_stop
        self.release_mutex()

    @abstractmethod
    def stop_requested(self):
        return self._stop_flag

    def run(self):
        # Turn off the stop flag
        self.stop_thread(False)
        self._monitor()

    @property
    def set_point(self):
        return self._set_point

    @set_point.setter
    def set_point(self, new):
        self._set_point = new

    @property
    def rate(self):
        return self._rate

    @rate.setter
    def rate(self, new):
        self._rate = new

    @property
    def current_val(self):
        return self._val

    @current_val.setter
    def current_val(self, new):
        self._val = new

    @property
    def state(self) -> str:
        return self._state

    @state.setter
    def state(self, new: str):
        self._state = new

    def set_params(self,
                   current_val: Union[float, str, tuple],
                   set_point: Union[float, tuple],
                   rate: float,
                   state: str,
                   ):
        self.current_val = current_val
        self.set_point = set_point
        self.rate = abs(rate)
        self.state = state

    @abstractmethod
    def _monitor(self):
        raise NotImplementedError


class ICommandObserverSim(IObserver, Generic[T]):
    def __init__(self,
                 i_sim_change: Type[T],
                 ):
        super().__init__()
        self._change_thread_type = i_sim_change
        self.change_thread = i_sim_change()

    @property
    def change_thread(self) -> T:
        return self._change_thread

    @change_thread.setter
    def change_thread(self, new: T):
        self._change_thread = new

    def get_sim_instance(self) -> T:
        """
        Instantiates the sim_class change thread.  This checks to see
        if the thread is already running, and stops it if so.
        """
        # if running, stop the thread
        self.change_thread.stop_thread()
        # the while loop just makes sure that the
        # thread eventually ends.
        start_time = time()
        while self.change_thread.is_sim_alive():
            sleep(CLOCK_TIME)
            # this should take less than 2 seconds
            if start_time - time() < 2.0:
                break
        self.change_thread.unsubscribe(self)
        self.change_thread = self._change_thread_type()
        return self.change_thread
