#!/usr/bin/env python3
"""
Created on Mon Jun 7 23:47:19 2021

MultiVuServer.py is a module for use on a computer running MultiVu.  It can
be used with MultiVuClient.py to control a Quantum Design cryostat.

@author: D. Jackson
"""

import logging
import re
import selectors
import sys
import traceback
from time import sleep
from typing import List, Tuple

from .CommandChamber import SimulateChamberChange as _SimulateChamberChange
from .CommandField import SimulateFieldChange as _SimulateFieldChange
from .CommandTemperature import \
    SimulateTemperatureChange as _SimulateTemperatureChange
from .exceptions import (ClientCloseError, MultiPyVuError, ServerCloseError,
                         SocketError)
from .IEventManager import IObserver as _IObserver
from .instrument import Instrument as _Instrument
from .IServer import IServer as _IServer
from .logging_config import remove_logs, setup_logging
from .ParseInputs import inputs_from_command_line
from .project_vars import CLOCK_TIME, HOST_SERVER, PORT, SERVER_NAME
from .scripts.helper_scripts import force_quit
from .SocketMessageServer import ServerMessage as _ServerMessage
from .SocketMessageServer import ServerStatus as _ServerStatus


class Server(_IServer):
    def __init__(self,
                 flags: List[str] = [],
                 host: str = HOST_SERVER,
                 port: int = PORT,
                 keep_server_open=False
                 ):
        """
        This class is used to start and maintain a socket server.  A client
        can be set up using MultiVuClient.py.

        Parameters:
        -----------
        flags : [str], optional
            For a list of flags, use the help flag, '--help'.  The default
            is [].
            Arguments are:
            -h(elp) to display the help text
            -s for scaffolding in order to simulate the script
            -ip=<host address> to specify the host IP
                address (default = '0.0.0.0' which accepts all incoming
                connections).  Note, specifying the IP address in the
                flags takes precedence over using the 'host' input
                parameter.
            -p(ort) to specify the port (default is 5000).  Note,
                specifying the port number in the flags takes precedence
                over using the 'port' input parameter.
            -v(erbose) to turn on the verbose text when the server
                sends/receives info

            An argument without a flag is the instrument.
            The default IP address is '0.0.0.0,' and the default port
            is 5000.
        host : str, optional
            The host IP address.  The default is '0.0.0.0', which allows
            connections from all network interfaces.  Note, specifying an
            IP address using the input flags will overwrite the setting
            used here.
        port : int, optional
            The desired port number.  The default is 5000.  Note, specifying
            an port number using the input flags will overwrite the setting
            used here.
        keep_server_open : bool, optional
            This flag can be set to true when running the server in its own
            script.  When True, the script will stay in the .open() method
            as long as the server is running.
            Default is False.
        """
        # instantiate the base class
        super().__init__()
        # The normal behavior of MultiVuServer runs the server in a separate
        # thread. In order to keep the server open when running the server
        # alone, one does not want to use threading.
        run_with_threading = not keep_server_open

        # _ServerMessage object
        self._message = None
        # Parsing the flags looks for user
        try:
            # Note that any  specified by the command line arguments (these
            # flags) will overwrite any parameters passed when instantiating
            # the class.
            flag_info = inputs_from_command_line(flags)
        except UserWarning as e:
            # This happens if it is displaying the help text
            setup_logging()
            self._logger = logging.getLogger(SERVER_NAME)
            self._logger.info(e)
            sys.exit(0)
        self._verbose = flag_info.verbose
        self._scaffolding = flag_info.scaffolding_mode
        # Update the host member variable if the user flags selected one
        self.host: str = host if flag_info.host == HOST_SERVER else flag_info.host
        self.port: int = port if flag_info.port == PORT else flag_info.port
        # force quit the server (in case one is already running)
        force_quit(self.host, self.port)

        mvu_flavor = flag_info.instrument_str
        # add a queue for sending observers to the Message
        # class once instantiated
        self._observer_queue: List[_IObserver] = []
        # Configure logging
        setup_logging(run_with_threading)
        self._logger = logging.getLogger(SERVER_NAME)
        #
        if mvu_flavor != '':
            msg = f'{mvu_flavor} MultiVu specified by user.'
            self._logger.info(msg)

        # Instantiate the _Instrument class
        try:
            self._instr = _Instrument(mvu_flavor,
                                      self._scaffolding,
                                      run_with_threading,
                                      self._verbose)
        except MultiPyVuError as e:
            self._logger.info(e.args[0])
            self.close()
            sys.exit(0)

    def instrument_name(self) -> str:
        """
        Returns the MultiVu flavor
        """
        name = ''
        if self._instr is not None:
            name = self._instr.name
        return name

    def stop(self) -> None:
        """
        Stops the SocketMessage thread
        """
        if self._message is not None:
            self._message.stop_message()
            checks = 6
            for _ in range(checks):
                sleep(CLOCK_TIME)
                if not self._message.is_alive():
                    break

    def __enter__(self) -> 'Server':
        """
        The class can be started using context manager terminology using
        'with.'  Opens the connection and passes off control to the rest
        of the class to monitor traffic in order to  receive commands
        from a client and respond appropriately.

        Returns:
        --------
        reference to this class
        """
        quit_keys = "ctrl-c"
        if sys.platform == 'win32':
            quit_keys = "ESC"
        self._logger.info(f'Press {quit_keys} to exit.')

        # The selectors must be first configured here, before
        # starting the _monitor_socket_connection thread.  This
        # was the only way I could get pywin32com to work with
        # threading
        sel = selectors.DefaultSelector()
        if self._message and self._message.is_alive():
            self.stop()
            self._message.join()
            self._message = None
        self._message = _ServerMessage(self._instr,
                                       sel,
                                       self.port,
                                       )

        # transfer the observers to self._message
        for obs in self._observer_queue:
            self._message.subscribe(obs)
        # reset the _observer_queue
        self._observer_queue = []

        try:
            if self._instr.run_with_threading:
                # The Server thread is now doing the work
                self._message.start()
            else:
                self._message.monitor_socket_connection()
        except SocketError as e:
            if e.strerror == 'Address already in use':
                self._logger.info(f'Port in use: {self.port}')
                self._logger.info(e.args[0])
                if self._message is not None:
                    self._message = None
                self.close()
        except BaseException:
            self.close()
        return self

    def __exit__(self, exc_type, exc_value, exc_traceback) -> BaseException:
        """
        Because this class is a context manager, this method is called when
        exiting the 'with' block.  It cleans up all of the connections and 
        deals with errors that may have arrived.

        Parameters:
        -----------
        exc_type, exc_value, exc_traceback make up the tuple returned
        by sys.exc_info()
        """
        # See if any of the threads used to monitor changes
        # are still running, and stop them if they are
        if self._scaffolding:
            change_threads = [
                _SimulateTemperatureChange(),
                _SimulateFieldChange(),
                _SimulateChamberChange(),
                ]
            for ct in change_threads:
                if ct.is_sim_alive():
                    ct.stop_thread()

        # Error handling
        if self._message is None:
            return exc_value

        self._instr.end_multivu_win32com_instance()

        # This is used when exiting the routine to let it
        # know if it should return the error or raise the
        # error.
        raise_error = False
        if isinstance(exc_value, SystemExit):
            logging.shutdown()
            raise_error = True
        elif isinstance(exc_value, KeyboardInterrupt):
            self._logger.info('')
            self._logger.info('Caught keyboard interrupt, exiting')
        elif isinstance(exc_value, MultiPyVuError):
            self._logger.info(exc_value)
        elif isinstance(exc_value, UserWarning):
            # Display the help and quit.
            self._logger.info(exc_value)
        elif isinstance(exc_value, ClientCloseError):
            pass
        elif isinstance(exc_value, ServerCloseError):
            pass
        elif isinstance(exc_value, ConnectionRefusedError):
            pass
        elif isinstance(exc_value, Exception):
            msg = 'MultiVuServer: error: exception for '
            msg += f'{self._message.addr}'
            msg += f'\n{traceback.format_exc()}'
            self._logger.info(msg)
            raise_error = True
        remove_logs(self._logger)
        self.stop()
        if self._instr.run_with_threading:
            self._message.join()
        self._message.unregister_and_close_sockets()
        self._observer_queue = self._message.transfer_observers()
        self._message = None
        if raise_error:
            raise exc_value
        else:
            return exc_value

    def open(self) -> 'Server':
        """
        This method is the entry point to the MultiVuServer class.  It starts
        the connection and passes off control to the rest of the class to
        monitor traffic in order to  receive commands from a client and
        respond appropriately.

        Returns
        -------
        reference to this class

        """
        return self.__enter__()

    def close(self) -> BaseException:
        """
        This closes the server

        Returns
        -------
        BaseException - any unexpected errors
        """
        err_info = sys.exc_info()
        return self.__exit__(err_info[0],
                             err_info[1],
                             err_info[2])

    def subscribe(self, observer: _IObserver) -> None:
        """
        Allows observers to subscribe to this class
        """
        if self._message:
            self._message.subscribe(observer)
        else:
            self._observer_queue.append(observer)

    def unsubscribe(self, observer: _IObserver) -> None:
        """
        Allows observers to unsubscribe from this class
        """
        if self._message:
            self._message.unsubscribe(observer)

    def server_status(self) -> str:
        """
        Returns 'closed,' 'idle,' or 'connected'
        """
        if self._message:
            return self._message.server_status.name
        else:
            return _ServerStatus.closed.name

    def get_connected_client_address(self) -> Tuple[str, int]:
        """
        Returns the client's IP address and port number
        """
        if (self._message
                and self._message.is_client_connected()):
            address = self._message.addr
        else:
            address = ('', 0)
        return address

    def is_client_connected(self) -> bool:
        """
        Returns a bool if a client is connected
        """
        if self._message:
            return self._message.is_client_connected()
        else:
            return False

    def number_of_clients(self) -> int:
        """
        Returns the number of clients connected to the server
        """
        if self._message:
            type_dict = self._message.get_type_and_references()
            number_rw = len(type_dict[self._message.ClientType.read_write])
            return number_rw
        else:
            return 0

    def update_address(self, new_address: Tuple[str, int]):
        """
        Updates the Server IP address and port number as long
        as the Server is not currently running
        """
        if self.is_client_connected():
            msg = 'Can not change the address while Server is running'
            raise MultiPyVuError(msg)
        else:
            if len(new_address) != 2:
                msg = 'Invalid format: new_address must be a tuple '
                msg += 'in the format "(<IP address>, PORT). '
                msg += f'Entered "{new_address}"'
                raise ValueError(msg)
            search_str = r'(\d{1,3}.\d{1,3}.\d{1,3}.\d{1,3}|localhost)'
            ip_result = re.findall(search_str, new_address[0])
            if len(ip_result) != 1:
                msg = f'Invalid format: "{new_address[0]}" is not '
                msg += 'a valid IP address.'
                raise ValueError(msg)
            try:
                port = new_address[1]
            except ValueError:
                msg = 'Invalid Port number.  Must be an integer '
                msg += f'(entered {new_address[1]}).'
                raise ValueError(msg)
            self.host = new_address[0]
            self.port = port
