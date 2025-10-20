# -*- coding: utf-8 -*-
"""
SocketMessageServer inherits SocketMessage and is used by the server
to communicate with socket client via SocketMessageClient

Created on Mon Jun 7 23:47:19 2021

@author: D. Jackson
"""

import logging
import re
import selectors
import socket
import threading
import time
import traceback
from enum import IntEnum, IntFlag, auto
from sys import platform
from typing import Dict, List, Optional, Union

from .check_windows_esc import _check_windows_esc
from .Command_factory import create_command_mv
from .exceptions import (ClientCloseError, MultiPyVuError, PwinComError,
                         PythoncomImportError, ServerCloseError, SocketError)
from .IEventManager import IObserver as _IObserver
from .IEventManager import Publisher as _Publisher
from .instrument import Instrument
from .project_vars import (CLOCK_TIME, ENCODING, SERVER_NAME, SOCKET_RETRIES,
                           TIMEOUT_LENGTH)
from .SocketMessage import Message, ResponseType

if platform == 'win32':
    try:
        import pythoncom
        import pywintypes

        from .exceptions import pywin_com_error
    except ImportError:
        raise PythoncomImportError


class ServerStatus(IntEnum):
    closed = auto()
    idle = auto()
    connected = auto()


def catch_thread_error(func):
    """
    This decorator is used to catch an error within a function
    """
    def error_handler(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        # ignore the errors handled in _exit()
        except (
            KeyboardInterrupt,
            MultiPyVuError,
            UserWarning,
            ClientCloseError,
            SocketError,
                ):
            pass
        except BaseException:
            name = threading.current_thread().name
            msg = f'Exception in thread \'{name}\' '
            msg += f'in method \'{func.__name__}\':\n'
            msg += traceback.format_exc()
            logger = logging.getLogger(SERVER_NAME)
            logger.info(msg)
    return error_handler


class ServerMessage(Message, threading.Thread, _Publisher):
    """
    This class is used by the Server to send and receive messages through
    the socket connection and respond to the Client's request.

    It inherits the Message base class, threading.Thread, and the
    Publisher class.

    Parameters:
    -----------
    instr: Instrument
        holds information about communications with MultiVu
    selector: selectors.DefaultSelector
        the selector object
    port: int
        the port number.
    """
    class ClientType(IntFlag):
        listening = auto()
        read_write = auto()
        other = auto()
    # bite wise or all of the enum options
    _all_client_types = ClientType.listening \
        | ClientType.read_write \
        | ClientType.other

    def __init__(self,
                 instr: Instrument,
                 selector: selectors.DefaultSelector,
                 port: int,
                 ):
        threading.Thread.__init__(self)
        Message.__init__(self)
        _Publisher.__init__(self)

        self.name = SERVER_NAME
        self.daemon = True

        self.selector = selector
        self.port = port
        self.addr = ('0.0.0.0', self.port)
        self.instr = instr
        self.verbose = instr.verbose
        self.scaffolding = instr.scaffolding_mode
        self.server_threading = instr.run_with_threading
        self.logger = logging.getLogger(SERVER_NAME)
        self.mutex = threading.Lock()
        self.server_status: ServerStatus = ServerStatus.idle
        # keep track of the read/write selectors when 'START' is received
        self._main_selectors: Dict[socket.socket,
                                   'ServerMessage.ClientType'] = {}
        self._stop_flag = False

    #########################################
    #
    # Private Methods
    #
    #########################################

    def _log_selector_status(self):
        type_dict = self.get_type_and_references()
        number_of_listening = len(type_dict[self.ClientType.listening])
        number_of_rw = len(type_dict[self.ClientType.read_write])
        number_of_other = len(type_dict[self.ClientType.other])
        msg = f'\tListening = {number_of_listening}'
        msg += f'\tRead/Write = {number_of_rw}'
        msg += f'\tOther = {number_of_other}'
        self.log_message(msg)

    def _log_selector_details(self):
        """
        Logs the list of selector key objects for each
        client type
        """
        type_dict = self.get_type_and_references()
        msg = 'Key Objects for each Client Type:'
        for type, key_obj in type_dict.items():
            if key_obj:
                msg += f'\n\t{type.name}: {key_obj}'
        self.log_message(msg)

    def _setup_server_socket(self) -> socket.socket:
        """
        Configure the socket

        Returns:
        --------
        Configured socket
        """
        # Set up the sockets
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        # Avoid bind() exception: OSError: [Errno 48] Address already in use
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind(('0.0.0.0', self.port))
        except socket.error as e:
            if e.strerror == 'Address already in use':
                msg = f'{e.strerror}: try using a different '
                msg += f'port (used {self.port})'
                self.logger.info(msg)
                raise SocketError(msg)
        sock.listen()
        sock.setblocking(False)
        self.server_status = ServerStatus.idle
        self.notify_observers()
        return sock

    def _accept_wrapper(self, sock: socket.socket) -> None:
        """
        This method accepts a new client.
        """
        # get the sock to be ready to read
        accepted_sock, self.addr = sock.accept()
        accepted_sock.setblocking(False)
        # Register the new socket with _do_work as the handler
        self.selector.register(accepted_sock,
                               selectors.EVENT_READ,
                               self._do_work,
                               )
        # Initially mark as 'other' type until we receive a START command
        with self.mutex:
            self._main_selectors[accepted_sock] = self.ClientType.other
            self.server_status = ServerStatus.idle
        self.notify_observers()

    def _send_reply(self,
                    sock: socket.socket,
                    message_dict: Dict,
                    message_type: ResponseType) -> Dict:
        message_dict['message_type'] = message_type.name

        # Clear the send buffer
        self._send_buffer = b''
        self._queue_request(message_dict, ENCODING)
        self._write(sock)
        return message_dict

    def _process_requested_message(self,
                                   sock: socket.socket) -> Optional[Dict]:
        """
        The data is transferred with a header that starts with two bytes
        which gives the length of the JSON header, which is decoded using
        utf-8. The header is used to decode the JSON message. As the buffer
        is decoded, self._recv_buffer, is trimmed so that by the end,
        self._recv_buffer just holds the message (action, request, and
        response).
        """
        self._receive_message(sock)
        header_length = self._process_proto_header()
        if header_length:
            json_header = self._process_json_header(header_length)
        else:
            return
        if json_header:
            request_dict = self._process_message(json_header)
        return request_dict

    def _validate_confirmation(self,
                               confirmation_dict: Optional[Dict],
                               response_dict: Dict) -> bool:
        """
        This checks that the client confirmed that it received
        the response from the server. Confirms the confirmation_dict
        exists; Both dictionaries have the same id; the
        confirmation_dict['message_type'] = 'confirmed'

        Arguments:
            confirmation_dict -- confirmation response from the client
            response_dict -- response sent to the client

        Returns:
            True if the server received confirmation from the client.
        """
        if not confirmation_dict:
            return False
        if confirmation_dict.get('id') != response_dict.get('id'):
            return False
        if confirmation_dict.get('message_type') != ResponseType.confirmed.name:
            return False
        return True

    def _do_work(self, sock: socket.socket):
        """
        After ._accept_wrapper is called, it sets this method to be called
        next.  This method reads the socket, deals with what it found, then
        writes the result to the socket and finally prepares the class for the
        next incoming command.

        Parameters:
        -----------
        sock: socket.socket
            The socket connection
        """
        # Clear request and the buffer
        request = {}
        self._recv_buffer = b''
        # read sockets
        try:
            request = self._process_requested_message(sock)
        except ConnectionResetError:
            raise ClientCloseError('Server closed the connection')
        except ConnectionAbortedError:
            msg = 'An established connection was aborted.'
            raise SocketError(msg)

        if request:
            request = self._send_reply(sock,
                                       request,
                                       ResponseType.confirmed)
            response_dict = self._prep_server_commands(request)
            if not response_dict.get('result'):
                # Now do the MultiVu command
                response_dict = self._process_content(response_dict)

            # Send the response to the client
            for attempt in range(SOCKET_RETRIES):
                _check_windows_esc()
                try:
                    self._send_reply(sock,
                                     response_dict,
                                     ResponseType.completed)
                except socket.error as e:
                    print(f'Error receiving data: {e}')
                    self.close(sock)
                    return
                except Exception as e:
                    print(f'Error processing message: "{e}"')

                # Get the confirmation that the reply was received
                try:
                    confirmation_dict = self._process_requested_message(sock)
                except ClientCloseError:
                    # Thrown if the client shuts down
                    break
                except socket.timeout:
                    if attempt >= SOCKET_RETRIES - 1:
                        err_msg = "Timeout waiting for confirmation"
                        self.log_message(err_msg)
                        raise TimeoutError(err_msg)
                else:
                    if self._validate_confirmation(confirmation_dict,
                                                   response_dict):
                        break

            self._do_server_commands(response_dict, sock)

    def _get_listen_sock(self) -> socket.socket:
        """
        Uses the selectors information to get the client socket info
        """
        with self.mutex:
            for s, t in self._main_selectors.items():
                if t == self.ClientType.listening:
                    return s
        # if it gets here, then the listening sock was not defined
        raise MultiPyVuError('No listening socket defined')

    def _poll_connections(self):
        """
        Pings the non-listening sockets to ensure they are still active.
        If they are inactive, it closes the socket and removes it from the
        _main_selectors dict.
        """
        for sel_obj in list(self.selector.get_map().values()):
            conn = sel_obj.fileobj
            if isinstance(conn, socket.socket) \
                    and conn != self._get_listen_sock():
                try:
                    conn.sendall(b'PING')
                    conn.recv(1, socket.MSG_PEEK)
                except (ConnectionResetError,
                        ConnectionAbortedError,
                        BrokenPipeError,
                        BlockingIOError):
                    self.selector.unregister(conn)
                    self.close(conn)
                    with self.mutex:
                        del self._main_selectors[conn]

    def _create_response_json_content(self,
                                      content: Dict[str, str],
                                      encoding
                                      ) -> Dict[str, str]:
        """
        Configures the response given the content.

        Parameters:
        -----------
        content: Dict[str, str]
            the information that goes into the 'content' key
        encoding: str
            encoding type for messages.

        Returns:
        --------
        Dict: key = 'type', 'encoding', and 'content'
        """
        response = {
            'type': 'text/json',
            'encoding': encoding,
            'content': content,
        }
        return response

    def _prep_server_commands(self, request_dict: Dict) -> Dict:
        # Copy the request_dict in order to keep the 'id'
        response_dict = request_dict.copy()

        default_result = f'Connected to {self.instr.name} '
        default_result += f'MultiVuServer at {self.addr}'
        if response_dict.get('action') == 'START':
            # check if a read/write client is already connected
            type_dict = self.get_type_and_references()
            if type_dict[self.ClientType.read_write]:
                result = 'Connection attempt rejected from '
                result += f'{self.addr}: another client is connected.'
                self.logger.info(result)
                response_dict['result'] = result
            else:
                # change the query to let the client know server info
                response_dict['query'] = self._start_to_str()
                response_dict['result'] = default_result
                self.logger.info(f'Accepted connection from {self.addr}')
        elif response_dict.get('action') == 'ALIVE':
            # Use the query to confirm the command was sent and received
            response_dict['query'] = 'ALIVE'
            response_dict['result'] = default_result
        elif response_dict.get('action') == 'STATUS':
            response_dict['result'] = self.server_status.name
            # Use the query to confirm the command was sent and received
            response_dict['query'] = 'STATUS'
        elif response_dict.get('action') == 'CLOSE':
            result = f'Client {self.addr} disconnected.'
            self.logger.info(result)
            response_dict['result'] = result
            # Use the query to confirm the command was sent and received
            response_dict['query'] = 'CLOSE'
        elif response_dict.get('action') == 'EXIT':
            # Use the query to confirm the command was sent and received
            result = 'Closing client and exiting server.'
            self.logger.info(result)
            response_dict['result'] = result
            response_dict['query'] = 'EXIT'
        else:
            return response_dict
        return response_dict

    def _update_server_status(self):
        """
        Updates the server status based on the current client connections
        """
        type_dict = self.get_type_and_references()
        number_of_rw = len(type_dict[self.ClientType.read_write])

        # Check if there are any clients still connected
        with self.mutex:
            if number_of_rw > 0:
                self.server_status = ServerStatus.connected
            else:
                # Only change to idle if we're not already closed
                if self.server_status != ServerStatus.closed:
                    self.server_status = ServerStatus.idle
            msg = f"Server status updated to: {self.server_status.name}"
            self.logger.debug(msg)

    def _do_server_commands(self,
                            response_dict: Dict,
                            sock: socket.socket) -> None:
        if response_dict.get('action') == 'START':
            # check if a read/write client is already connected
            type_dict = self.get_type_and_references()
            if type_dict[self.ClientType.read_write]:
                self.selector.unregister(sock)
                sock.close()
                with self.mutex:
                    if sock in self._main_selectors:
                        del self._main_selectors[sock]
            else:
                self.server_status = ServerStatus.connected
                with self.mutex:
                    self._main_selectors[sock] = self.ClientType.read_write
        elif response_dict.get('action') == 'ALIVE':
            self.unregister_and_close_sockets(self.ClientType.other)
        elif response_dict.get('action') == 'STATUS':
            self.unregister_and_close_sockets(self.ClientType.other)
        elif response_dict.get('action') == 'CLOSE':
            self.unregister_and_close_sockets(self.ClientType.read_write)
            # Call the ClientCloseError
            raise ClientCloseError('Received close command')

        elif response_dict.get('action') == 'EXIT':
            self.stop_message()
            self.shutdown()
            raise ServerCloseError('Close server')
        else:
            return
        self.notify_observers()

    def _process_content(self, response_dict: Dict) -> Dict:
        """
        Decides what to do with the request dictionary and returns
        the response dictionary
        """
        action = response_dict.get('action')
        query = response_dict.get('query')
        command = f'{action} {query}'
        try:
            response_dict['result'] = self._do_request(command)
        except MultiPyVuError as e:
            response_dict['result'] = e.value
        except ValueError:
            msg = f"The command '{action}' has not been implemented."
            response_dict['result'] = msg

        response_dict['message_type'] = ResponseType.completed.name
        return response_dict

    def _do_request(self, arg_string: str, attempts: int = 0) -> str:
        """
        This takes the arg_string parameter to create a query for
        CommandMultiVu.

        Parameters:
        -----------
        arg_string: str
            The string has the form:
                arg_string = f'{action} {query}'
            For example, if asking for the temperature, the query is blank:
                arg_string = 'TEMP? '
            Or, if setting the temperature:
                arg_string = 'TEMP set_point,
                              rate_per_minute,
                              approach_mode.value'
            The easiest way to create the query is to use:
                ICommand.prepare_query(set_point,
                                       rate_per_min,
                                       approach_mode,
                                       )
        attempts: int (optional, default = 0)
            The number of times this method has been called

        Returns:
        --------
        str
            The return string is of the form:
            '{action}?,{result_string},{units},{code_in_words}'

        """
        split_string = r'([A-Z_]+)(\?)?[ ]?([ :\-?\d.,\w]*)?'
        # this returns a list of tuples - one for each time
        # the groups are found.  We only expect one command,
        # so only taking the first element
        [command_args] = re.findall(split_string, arg_string)
        try:
            cmd, question_mark, params = command_args
            query = (question_mark == '?')
        except IndexError:
            return f'No argument(s) given for command {command_args}.'
        else:
            mvu_commands = create_command_mv(self.instr.name,
                                             self.instr.multi_vu)
            max_retries = 5
            try:
                if query:
                    return mvu_commands.get_state(cmd, params)
                else:
                    return mvu_commands.set_state(cmd, params)
            except (pythoncom.com_error,
                    pywintypes.com_error,
                    AttributeError,
                    ) as e:
                if attempts < max_retries:
                    attempts += 1
                    msg = 'pythoncom.com_error attempt number: '
                    msg += f'{attempts}'
                    self.logger.debug(msg)
                    self.instr.end_multivu_win32com_instance()
                    time.sleep(CLOCK_TIME)
                    self.instr.get_multivu_win32com_instance()
                    return self._do_request(arg_string, attempts)
                else:
                    raise MultiPyVuError(str(e))

    #########################################
    #
    # Public Methods
    #
    #########################################

    def run(self):
        """
        This method is run when ServerMessage.start() is called. It stops any
        currently running threads, then calls .monitor_socket_connection().
        Once that method has completed, it calls .shutdown()
        """
        # Initialize the _stop_flag to False
        self.stop_message(False)
        self.monitor_socket_connection()
        self.shutdown()

    def stop_message(self, set_stop: bool = True):
        """
        Stops this class from running as a thread.

        Parameters:
        -----------
        set_stop: bool (optional)
            True (default) will stop the thread
        """
        with self.mutex:
            self._stop_flag = set_stop

    def stop_requested(self) -> bool:
        """
        Queries this class to see if it has been asked to stop the thread
        """
        return self._stop_flag

    @catch_thread_error
    def monitor_socket_connection(self):
        """
        This monitors traffic and looks for new clients and new requests.
        It configures the socket connection, registers the
        selectors and gets a win32com instance to talk to MultiVu.

        It then enters a loop to monitor the traffic.  For new clients, it
        calls ._accept_wrapper().  After that, it uses ._do_work() to figure
        out how to implement the client's request.
        """
        # we can never get to this point without Instrument being instantiated
        if self.instr is None:
            err_msg = 'The class, Instrument, was not instantiated'
            raise MultiPyVuError(err_msg)

        listening_sock = self._setup_server_socket()
        with self.mutex:
            self._main_selectors[listening_sock] = self.ClientType.listening
        # Register the server socket with the selector to
        # monitor for incoming connections
        self.selector.register(listening_sock,
                               selectors.EVENT_READ,
                               self._accept_wrapper,
                               )
        self.logger.info(f'Listening on port {self.port}')

        # Connect to MultiVu in order to enable a new thread,
        # but only if the connection has not yet been made (allows
        # for multiple consecutive client connections).
        self.instr.get_multivu_win32com_instance()

        while True:
            _check_windows_esc()
            if self.stop_requested():
                break

            # Polling could be implemented later.  If the server is
            # going to check the connections, it needs a timer so
            # that it only checks connections every xxx seconds
            # self._poll_connections()

            # Periodically check server status and ensure it can accept
            # new connections
            if self.server_status == ServerStatus.idle:
                # Verify listening socket is properly registered
                try:
                    self.selector.get_key(listening_sock)
                except (ValueError, KeyError):
                    # Re-register if needed
                    try:
                        self.selector.register(listening_sock,
                                               selectors.EVENT_READ,
                                               self._accept_wrapper)
                    except ValueError:
                        # Already registered, ignore
                        pass

            try:
                events = self.selector.select(timeout=TIMEOUT_LENGTH)
            except SocketError:
                # This error happens if the selectors is unavailable.
                continue
            for key, mask in events:
                # This is the data we passed to `register`
                # It is ._accept_wrapper() the first time,
                # then ._do_work() the next time
                work_method = key.data
                sock = key.fileobj
                try:
                    work_method(sock)
                except BlockingIOError:
                    # try calling this method again
                    time.sleep(CLOCK_TIME)
                    continue
                except MultiPyVuError as e:
                    self.logger.info(e)
                    break
                except ServerCloseError:
                    self.stop_message()
                    break
                except ClientCloseError as e:
                    self.logger.info(e)
                    break
                except ConnectionAbortedError as e:
                    self.logger.info(e)
                    self.stop_message()
                    break
                except AttributeError as e:
                    msg = 'Lost connection to socket.'
                    self.logger.info(f'{msg}:   AttributeError: {e}')
                    tb_str = ''.join(traceback.format_exception(None,
                                                                e,
                                                                e.__traceback__,
                                                                )
                                     )
                    self.logger.info(tb_str)
                    self.stop_message()
                    break
                except pywin_com_error as e:
                    self.logger.info(str(PwinComError(e)))
                    self.stop_message()
                    break
                except KeyboardInterrupt as e:
                    raise e

    def connection_good(self, sock: Union[socket.socket, None]) -> bool:
        """
        Calls selectors.get_key(socket) to see if the connection is good.
        """
        if not sock:
            return False
        try:
            # Check for a socket being monitored to continue.
            self.selector.get_key(sock)
            return True
        except (ValueError, KeyError):
            # can get ValueError if self.sock is None
            # KeyError means no selector is registered
            return False

    def unregister_and_close_sockets(self,
                                     types: Optional['ServerMessage.ClientType'] = None,
                                     ) -> None:
        """
        Unregister and close connections in the types variable.

        Parameters:
        -----------
        types: ServerMessage.ClientType or None
            Default: None (all ClientTypes)
            This can have a bit-wise input using the logical or
            for multiple types.
        """
        types = ServerMessage._all_client_types if types is None else types
        self._log_selector_status()

        # In normal situations, this list has two items, one for
        # _accept_wrapper() and another for _do_work()
        selectors_to_delete = []
        for key, sel_obj in list(self.selector.get_map().items()):
            fileobj = sel_obj.fileobj
            if isinstance(fileobj, socket.socket):
                conn: socket.socket = fileobj
                method = sel_obj.data
                if method:
                    default_type = self.ClientType.other
                    with self.mutex:
                        cl_type = self._main_selectors.get(conn, default_type)
                    if cl_type & types:
                        msg = f'Closing socket {conn.fileno()} of '
                        msg += f'type "{cl_type.name}"'
                        self.log_message(msg)
                        try:
                            self.selector.unregister(conn)
                            conn.close()
                            selectors_to_delete.append(conn)
                        except Exception as e:
                            self.log_message(f'Error closing socket: {e}')
        for s in selectors_to_delete:
            with self.mutex:
                if s in self._main_selectors:
                    del self._main_selectors[s]

        # Ensure listening socket is still registered with _accept_wrapper
        try:
            listening_sock = self._get_listen_sock()
            # Check if the listening socket is registered with _accept_wrapper
            try:
                key = self.selector.get_key(listening_sock)
                if key.data != self._accept_wrapper:
                    # Re-register with correct callback
                    self.selector.unregister(listening_sock)
                    self.selector.register(listening_sock,
                                           selectors.EVENT_READ,
                                           self._accept_wrapper)
                    self.log_message('Fixed listening socket callback')
            except (KeyError, ValueError):
                # re-register if not registered
                self.selector.register(listening_sock,
                                       selectors.EVENT_READ,
                                       self._accept_wrapper)
                self.log_message('Re-registered listening socket')
        except MultiPyVuError:
            # if no listening socket, we might be shutting down
            pass

        self._update_server_status()

    def shutdown(self):
        """
        Unregister the Selector and close the socket
        """
        # since we are exiting, need to unregister all selectors
        self.unregister_and_close_sockets(ServerMessage._all_client_types)
        self.server_status = ServerStatus.closed
        self.notify_observers()

    def get_type_and_references(self) -> Dict[ClientType, List[object]]:
        """
        Use the _main_selectors dictionary to make a dictionary of
        the types (key) and a list of reference objects (value).
        """
        type_dict = {
            self.ClientType.listening: [],
            self.ClientType.read_write: [],
            self.ClientType.other: [],
        }
        with self.mutex:
            unregistered_sockets = []
            for sock, cl_type in self._main_selectors.items():
                try:
                    key = self.selector.get_key(sock)
                except (KeyError, ValueError):
                    # Already unregistered, so add it to the delete list
                    unregistered_sockets.append(sock)
                    continue
                work_method = key.data
                type_dict[cl_type].append(work_method)

            # Delete unused items
            for sock in unregistered_sockets:
                del self._main_selectors[sock]
        return type_dict

    def is_client_connected(self) -> bool:
        """
        Determines if any read/write clients are connected by checking
        the socket state.
        """
        with self.mutex:
            # First check our internal count
            connected_count = 0
            active_sockets = []

            for sock, cl_type in list(self._main_selectors.items()):
                if cl_type == self.ClientType.read_write:
                    # Verify the socket is actually still valid
                    try:
                        # Non-blocking check if socket is still connected
                        if self.connection_good(sock):
                            connected_count += 1
                            active_sockets.append(sock)
                    except (socket.error, OSError):
                        # Socket is invalid - we should clean it up
                        msg = "Found invalid socket in _main_selectors, "
                        msg += "cleaning up"
                        self.log_message(msg)
                        try:
                            self.selector.unregister(sock)
                        except Exception:
                            pass
                        try:
                            sock.close()
                        except SocketError:
                            pass
                        # Will be removed from _main_selectors below

            # Update our internal state to match reality
            # Keep only the sockets that are actually still active
            self._main_selectors = {s: t for s, t in self._main_selectors.items()
                                if t != self.ClientType.read_write or s in active_sockets}
            msg = f"Active read/write connections: {connected_count}"
            self.log_message(msg)
            return connected_count > 0

    def transfer_observers(self) -> List[_IObserver]:
        """
        Unsubscribe and transfer the observers
        """
        outgoing_list = []
        for obs in self._observers:
            self.unsubscribe(obs)
            outgoing_list.append(obs)
        return outgoing_list
