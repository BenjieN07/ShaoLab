# -*- coding: utf-8 -*-
"""
SocketMessageClient.py inherits SocketMessage and is used by the client
to communicate with socket server via SocketMessageServer

Created on Mon Jun 7 23:47:19 2021

@author: D. Jackson
"""

import logging
import re
import socket
import time
import uuid
from typing import Dict, Optional, Tuple, Union

from .check_windows_esc import _check_windows_esc
from .exceptions import (ClientCloseError, MultiPyVuError, ServerCloseError,
                         SocketError)
from .instrument import Instrument
from .project_vars import (CLIENT_NAME, CLOCK_TIME, ENCODING, SOCKET_RETRIES,
                           TIMEOUT_LENGTH)
from .SocketMessage import Message, ResponseType


class ClientMessage(Message):
    """
    This class is used by the Client to send and receive messages through
    the socket connection and display the Server's response.

    It inherits the Message base class.

    Parameters:
    -----------
    address: Tuple[str, int]
        specify the host address information:  (IP address, port number)
    """
    def __init__(self, address: Tuple[str, int]):
        super().__init__()
        self.addr = address
        self._pending_requests = {}
        self.logger = logging.getLogger(CLIENT_NAME)

    #########################################
    #
    # Private Methods
    #
    #########################################

    def _process_start(self, response_dict: Dict):
        """
        This helper method is called if START was sent and received.  It
        deciphers all of the settings from the Server.
        """
        too_many = 'Connection attempt rejected from'
        if response_dict['result'].startswith(too_many):
            raise SocketError(response_dict['result'])

        self.addr = self.sock.getsockname()
        options_dict = self._str_to_start_options(response_dict['query'])
        self.server_version = options_dict['version']
        self.verbose = options_dict['verbose']
        self.scaffolding = options_dict['scaffolding']
        self.server_threading = options_dict['threading']
        resp = response_dict.get('result', '')
        search = r'Connected to ([\w]*) MultiVuServer'
        self.mvu_flavor = re.findall(search, resp)[0]
        # the Instrument class is used to hold info and
        # can be instantiated with scaffolding mode so that
        # it does not try to connect with a running MultiVu
        self.instr = Instrument(self.mvu_flavor,
                                True,   # instantiate in scaffolding mode
                                self.server_threading,
                                self.verbose)

    def _check_multipyvu_error(self, response_dict: Dict):
        """
        Check for a MultiPyVu error returned from the Server

        Raises:
        -------
        MultiPyVuError
        """
        result: str = response_dict['result']
        if result.startswith('MultiPyVuError: '):
            raise MultiPyVuError(result)

    def _check_response_answers_request(self,
                                        request: Dict,
                                        response: Dict) -> None:
        """
        check response answers a request

        Raises:
        -------
        MultiPyVuError if the response does not match the request
        """
        if request['action'] != response['action']:
            msg = 'Received a response to the '
            msg += 'wrong request:\n'
            msg += f' request = {request}\n'
            msg += f'response = {response}'
            raise MultiPyVuError(msg)

    #########################################
    #
    # Public Methods
    #
    #########################################

    def setup_client_socket(self,
                            server_address: Tuple[str, int],
                            retry_count: int,
                            timeout: float = 0.5,
                            ) -> Optional[socket.socket]:
        """Initialize and run the client, handling the connection
        to the server.

        Args:
            server_address: (IP address, Port number)
            retry_count: Number of connection attempts to make
            timeout: length of time to wait for a socket connection

        Returns:
            The configured server socket

        Raises:
            SystemExit: If there's an error setting up the server
        """
        msg = f"Connecting to '{server_address[0]} : {server_address[1]}'..."
        self.log_message(msg)
        for attempt in range(retry_count):
            if attempt > 0:
                msg = f"Retrying connection ({attempt}/{retry_count-1})..."
                self.log_message(msg)

            # Ensure any previous connection is properly closed
            try:
                self.sock.close()
                # Add a short delay to allow for socket cleanup
                time.sleep(0.1)
            except BaseException:
                # Since we're closing the socket, we don't need to handle
                # exceptions here. Just continue on.
                pass

            # Create new socket for each connection attempt
            try:
                client_socket = socket.socket(socket.AF_INET,
                                              socket.SOCK_STREAM)
                client_socket.setsockopt(socket.SOL_SOCKET,
                                         socket.SO_REUSEADDR,
                                         1)
            except ConnectionRefusedError:
                # Pause, then try again
                time.sleep(0.5)
                continue

            # Set a timeout for the connection attempt
            client_socket.settimeout(timeout)

            try:
                client_socket.connect(server_address)
                # Reset timeout for normal operation
                client_socket.settimeout(None)
                self.sock = client_socket
                return client_socket
            except BaseException:
                client_socket.close()
                if attempt >= retry_count - 1:
                    # If we get here, all attempts failed
                    raise

    def reset_socket_client(self):
        """
        Resets the socket connection and internal state to allow for
        reconnection. Preserves address and timeout settings while
        clearing connection state.
        """
        self.log_message('Resetting client message state')

        # Close socket if it exists
        try:
            if hasattr(self, 'sock') and self.sock:
                try:
                    self.sock.shutdown(socket.SHUT_RDWR)
                except Exception as e:
                    # Ignore if already closed
                    pass
                self.sock.close()
                self.sock = None
                self.addr = ('', 0)
        except Exception as e:
            self.log_message(f"Error closing socket: {e}")

        # Reset buffers and state
        self._recv_buffer = b''
        self._send_buffer = b''
        self._pending_requests = {}

        # Reset server-related state
        if hasattr(self, 'server_version'):
            self.server_version = ''
        if hasattr(self, 'verbose'):
            self.verbose = False
        if hasattr(self, 'scaffolding'):
            self.scaffolding = False
        if hasattr(self, 'server_threading'):
            self.server_threading = False
        if hasattr(self, 'mvu_flavor'):
            self.mvu_flavor = ''

        # Keep addr and socket_timeout as they are configuration parameters

        self.log_message('Client message reset complete')

    def create_request(self, action: str, query: str = '') -> Dict[str, str]:
        """
        Creates the framed .request dictionary

        Parameters:
        -----------
        action : str
            The general command going to MultiVu, for example TEMP(?),
            FIELD(?), and CHAMBER(?).  If one wants to know the value
            of the action, then it ends with a question mark.  If one
            wants to set the action in order for it to do something,
            then it does not end with a question mark.
        query : str, optional
            The query gives the specifics of the command going to MultiVu.
            For queries. The default is '', which is what is used when the
            action parameter ends with a question mark.

        Returns:
        --------
            The JSON dictionary that is to be sent.
        """
        # Generate a unique message ID
        msg_id = str(uuid.uuid4())
        request = {
            'id': msg_id,
            'action': action.upper(),
            'query': query,
            'result': '',
            }
        return request

    def send_message(self, request_dict: Dict) -> bool:
        """
        Send a framed message to ensure complete delivery.

        Arguments:
            request_dict -- The dictionary which is getting sent
        Returns:
            Bool indicating successful write.
        """
        # Clear the send buffer
        self._send_buffer = b''

        self._queue_request(request_dict, ENCODING)
        sock_sent = False
        if self.sock:
            sock_sent = self._write(self.sock)
        return sock_sent

    def _validate_message(self,
                          request: Dict,
                          response: Optional[Dict],
                          msg_type: ResponseType) -> bool:
        """
        check response answers a request

        Raises:
        -------
        MultiPyVuError if the response does not match the request
        """
        # Check for an empty response dictionary
        if not response:
            return False
        response_id = response.get('id', '')
        if response_id in self._pending_requests:
            response_msg_type = response.get('message_type')
            if response_msg_type == msg_type.name:
                if msg_type == ResponseType.confirmed:
                    self._pending_requests[response_id][msg_type.name] = True
                    confirmation = response.get('action', '')
                    log_msg = f'Confirmation from server: "{confirmation}"'
                    self.log_message(log_msg)
                    return True
                elif msg_type == ResponseType.completed:
                    self._pending_requests[response_id][msg_type.name] = True
                    return True
                else:
                    raise NameError(f'"{msg_type.name}" not implemented')
            else:
                msg = f"Received '{response_msg_type}', but "
                msg += f"was looking for '{msg_type.name}'"
                raise ValueError(msg)
        else:
            msg = 'Incorrect Message ID\n'
            # Gather the pending requests
            msg += 'List of pending requests:\n'
            for id, request in self._pending_requests.items():
                msg += f"\t{request['request']} ({id})\n"
            raise ValueError(msg)

    def process_receiving_message(self,
                                  request_dict: Dict,
                                  message_type: ResponseType,
                                  timeout: Optional[float]) -> Optional[Dict]:
        """
        Process the whole message.

        Arguments:
            request_dict -- JSON request
            message_type -- Confirmation or Completion
            timeout -- socket timeout.  Use None for no timeout

        Returns:
            JSON message received
        """
        response_dict = None
        start_time = time.time()
        elapsed_time = lambda: time.time() - start_time
        while not self._validate_message(request_dict,
                                         response_dict,
                                         message_type):
            # First check if there's already data in the buffer before
            # receiving more
            if not self._recv_buffer:
                try:
                    self._receive_message(self.sock)
                except socket.timeout:
                    # This will happen if the server is still thinking,
                    # so continue with the while-loop as long as the
                    # total time is less than the timeout
                    if timeout:
                        if elapsed_time() > timeout:
                            raise socket.timeout
                    continue
            header_length = self._process_proto_header()
            if header_length:
                json_header = self._process_json_header(header_length)
            else:
                return
            if json_header:
                response_dict = self._process_message(json_header)
            else:
                time.sleep(CLOCK_TIME)

        if response_dict:
            return response_dict
        else:
            msg = 'No return value, which could mean that MultiVu '
            msg += 'is not running or that the connection has '
            msg += 'been closed.'
            raise ClientCloseError(msg)

    def send_and_receive(self,
                         request_dict: Dict) -> Optional[Dict[str, str]]:
        """
        This takes an action and a query, and sends it to
        the server to figure out what to do with the information.

        Parameters:
        -----------
        request_dict: Dict
            The message that is getting sent to the SocketMessageServer class

        Returns:
        --------
        response_dict: Dict
            The information retrieved from the socket and interpreted by
            SocketMessageClient class.

        Raises:
        -------
        SocketError if it is unable to write to the server
        ServerCloseError if the Server closed the connection
            or if the data received from the socket is none.
        ClientCloseError if the Client closes the connection.
        """
        # Clear the buffer
        self._recv_buffer = b''
        # Track requests using their UUID
        self._pending_requests = {}
        socket_sent = False
        for attempt in range(SOCKET_RETRIES):
            _check_windows_esc()
            # Send the message
            sock_sent = self.send_message(request_dict)
            if sock_sent:
                request_id = request_dict['id']
                self._pending_requests[request_id] = {
                    'request': request_dict,
                    'sent_time': time.time(),
                    'confirmed': False,
                    'completed': False,
                }
            try:
                response_dict = self.process_receiving_message(
                                        request_dict,
                                        ResponseType.confirmed,
                                        timeout=TIMEOUT_LENGTH
                                        )
                if response_dict:
                    # Server got the message
                    break
                else:
                    log_msg = 'No confirmation from the sever after '
                    log_msg += f'{TIMEOUT_LENGTH} seconds.  Resending the '
                    log_msg += 'request.'
                    self.log_message(log_msg)
                if attempt > SOCKET_RETRIES - 1:
                    err_msg = 'No response received or connection lost'
                    self.log_message(err_msg)
                    raise ConnectionAbortedError(err_msg)
            except ConnectionResetError as e:
                # This is thrown if the server or the client shut down. If
                # the server shuts down, the client needs to also shut down
                if request_dict['action'] == 'START':
                    err_msg = 'No connection to the sever upon start.  Is the '
                    err_msg += 'server running?'
                    self.logger.info(err_msg)
                raise ClientCloseError('Server closed the connection') from e
            except ConnectionRefusedError as e:
                self.log_message('No data received from server')
                if attempt >= SOCKET_RETRIES - 1:
                    err_msg = f"No data received after {attempt + 1} tries"
                    self.log_message(err_msg)
                    raise TimeoutError(err_msg) from e
            except socket.timeout as e:
                if attempt >= SOCKET_RETRIES - 1:
                    err_msg = "Timeout waiting for confirmation"
                    self.log_message(err_msg)
                    raise TimeoutError(err_msg) from e
            except ConnectionAbortedError as e:
                if attempt >= SOCKET_RETRIES - 1:
                    msg = 'An established connection was aborted.'
                    self.log_message(err_msg)
                    raise SocketError(msg) from e
            except socket.error as e:
                self.log_message(f'Error receiving data: {e}')
                if attempt >= SOCKET_RETRIES - 1:
                    msg = f'Failed receiving data after {attempt + 1} attempts'
                    raise ServerCloseError(msg) from e
            except ValueError:
                # This has already been logged, so re-raise the error
                raise
            except Exception as e:
                self.log_message(f'Error processing message: "{e}"')
            # Pause for a bit before trying again
            time.sleep(0.5)

        # Now listen again in order to get the completed answer
        socket_sent = False
        try:
            response_dict = self.process_receiving_message(
                                    request_dict,
                                    ResponseType.completed,
                                    timeout=None
                                    )
        except (ConnectionResetError,
                ConnectionRefusedError,
                ConnectionAbortedError) as e:
            # Client closed the server
            self.close()
            raise ServerCloseError(e.args[0]) from e
        except SocketError as e:
            raise SocketError(e.args[0]) from e
        except socket.timeout:
            err_msg = "Timeout waiting for Completed response from server"
            raise socket.timeout(err_msg)
        # Send a confirmation of receipt of the response
        if response_dict:
            response_dict['message_type'] = ResponseType.confirmed.name
            socket_sent = self.send_message(response_dict)

            if socket_sent:
                # Deal with what the server sent us
                self._check_response_answers_request(request_dict,
                                                     response_dict)

                self._check_multipyvu_error(response_dict)

                if self._check_start(request_dict, response_dict):
                    self._process_start(response_dict)
                elif self._check_close(request_dict, response_dict):
                    # Client has requested to close the connection
                    self.close()
                elif self._check_exit(request_dict, response_dict):
                    # Client requested to close the server (and client)
                    # Since this was received on purpose, send a
                    # ClientCloseError to shut things down properly.
                    # Sending a ServerCloseError() would raise an error
                    # at the end.
                    raise ClientCloseError('Close server')
                return response_dict

        msg = 'No return value, which could mean that MultiVu '
        msg += 'is not running or that the connection has '
        msg += 'been closed.'
        raise ClientCloseError(msg)

    def close(self):
        """
        Close the socket connection
        """
        super().close(self.sock)
