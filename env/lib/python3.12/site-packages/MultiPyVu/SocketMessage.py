# -*- coding: utf-8 -*-
"""
SocketMessage.py is the base class for sending information across sockets.  It
has two inherited classes, SocketMessageServer.py and SocketMessageClient.py

Created on Mon Jun 7 23:47:19 2021

@author: D. Jackson
"""

import json
import logging
import re
import socket
import struct
import sys
import traceback
from enum import Enum, auto
from typing import Dict, Optional, Tuple, Union

from .__version import __version__ as mpv_version
from .exceptions import ClientCloseError, MultiPyVuError, SocketError
from .project_vars import HEADER_BYTE_LENGTH, MESSAGE_TYPE, PORT, TIMEOUT_LENGTH


class ResponseType(Enum):
    confirmed = auto()
    completed = auto()


class Message():
    def __init__(self):
        """
        This is the base class for holding data when sending or receiving
        sockets.  The class is instantiated by Server() and
        Client().

        The data is sent and received as a dictionary of the form:
                id
                action (ie, 'TEMP?', 'FIELD',...)
                query
                result

        The information goes between sockets using the following format:
            Header length in bytes
            JSON header (.json_header) dictionary with keys:
                byteorder
                message-type
                message-encoding
                message-length
            Content dictionary with key:
                id
                action
                query
                result

        """
        self.logger = logging      # this is defined in the child classes
        self.port = PORT
        self.addr: Tuple[str, int]
        self._recv_buffer = b''
        self._send_buffer = b''
        self.mvu_flavor = None
        self.verbose = False
        self.scaffolding = False
        self.server_threading = False
        self.server_version = 'unknown server version'

    #########################################
    #
    # Private Methods
    #
    #########################################

    def _start_to_str(self) -> str:
        """
        Converts flags noting configuration parameters into a string.
        """
        query_list = []
        # add the version number
        query_list.append(mpv_version)
        if self.verbose:
            query_list.append('v')
        if self.scaffolding:
            query_list.append('s')
        if self.server_threading:
            query_list.append('t')
        return ';'.join(query_list)

    def _str_to_start_options(self, server_options: str) -> Dict:
        """
        Converts a string noting configuration parameters into flags

        Returns:
        --------
        Dict: key = option name, value = option flag (str)
        """
        options_list = server_options.split(';')
        options_dict = {}
        # find the server version number
        for option in options_list:
            search = r'([0-9]+.[0-9]+.[0-9]+)'
            v_list = re.findall(search, option)
            # check that it found a version number
            if len(v_list) == 1:
                options_dict['version'] = v_list[0]
            break
        options_dict['verbose'] = 'v' in options_list
        options_dict['scaffolding'] = 's' in options_list
        options_dict['threading'] = 't' in options_list
        return options_dict

    def _receive_message(self, sock: socket.socket):
        """
        Reads the socket and loads it into the ._recv_buffer

        Raises:
        -------
        ClientCloseError if the server closed the connection
            or if the data received from the socket is none.
        SocketError if a socket was aborted
        """

        sock.settimeout(TIMEOUT_LENGTH)
        try:
            # Should be ready to read
            data = sock.recv(4096)
        except BlockingIOError:
            # Resource temporarily unavailable (errno EWOULDBLOCK)
            pass
        else:
            if data:
                self._recv_buffer += data
                self._log_received_result(self.addr, data)
            else:
                raise ClientCloseError('Close client')

    def _write(self, sock: socket.socket) -> bool:
        """
        Writes data via a socket.  Sets the ._sent_success flag.

        Args:
            sock: The socket to write to

        Returns:
            True if the message was sent successfully, False otherwise

        Raises:
        -------
        SocketError if there is no socket connection
        """
        try:
            while self._send_buffer:
                sent = sock.send(self._send_buffer)
                if sent == 0:
                    # Connection broken
                    return False
                self._log_send(sock.getpeername())
                self._send_buffer = self._send_buffer[sent:]
                return True
        except BlockingIOError:
            # Resource temporarily unavailable (errno EWOULDBLOCK)
            pass
        except BrokenPipeError:
            # Resource temporarily unavailable
            pass
        # Note that socket.error = OSError, which is a base class with
        # the following subclasses:
        # ClientCloseError (ConnectionError)
        # ServerCloseError (ConnectionAbortedError)
        # ConnectionRefusedError
        except socket.error:
            # No socket connection
            err_msg = 'No socket connection.  Please make sure '
            err_msg += 'MultiVuServer is running, that '
            err_msg += 'MultiVuClient is using the same IP address, '
            err_msg += 'that the IP address is correct, that the server '
            err_msg += 'can accept connections, etc.'
            raise SocketError(err_msg)
        return False

    def _log_received_result(self,
                             addr: Tuple[str, int],
                             message: bytes):
        """
        Helper tool to add an entry to the log for the message received
        """
        msg = f';from {addr}; Received {message}'
        self.log_message(msg)

    def _log_send(self, addr: Tuple[str, int]):
        """
        Helper tool to add an entry to the log for the message being sent
        """
        msg = f';to {addr}; Sending {repr(self._send_buffer)}'
        self.log_message(msg)

    def _check_start(self,
                     request_dict: Dict,
                     response_dict: Dict) -> bool:
        """
        Checks to see if the client has requested to make a connection

        Returns:
        --------
        Bool: True means 'START' was requested
        """
        start_sent = request_dict['action'] == 'START'
        start_received = response_dict['action'] == 'START'
        return start_sent and start_received

    def _check_close(self,
                     request_dict: Dict,
                     response_dict: Dict) -> bool:
        """
        Checks to see if the client has requested to close the connection
        to the server.

        Returns:
        --------
        Bool: True if CLOSE was called
        """
        close_sent = request_dict['action'] == 'CLOSE'
        closing_received = response_dict['query'] == 'CLOSE'
        return close_sent and closing_received

    def _check_exit(self,
                    request_dict: Dict,
                    response_dict: Dict) -> bool:
        """
        Checks to see if the client has requested to exit the program, meaning
        the client closes the connection and the server exits

        Returns:
        --------
        Bool: True means 'EXIT' was requested
        """
        exit_sent = request_dict['action'] == 'EXIT'
        exit_received = response_dict['query'] == 'EXIT'
        return exit_sent and exit_received

    def _check_alive_cmd(self,
                         request_dict: Dict,
                         response_dict: Dict) -> bool:
        """
        Checks to see if the client has requested to see if the
        server is running

        Returns:
        --------
        Bool: True if ALIVE was called
        """
        alive_sent = request_dict['action'] == 'ALIVE'
        alive_received = response_dict['query'] == 'ALIVE'
        return alive_sent and alive_received

    def _check_status_cmd(self,
                          request_dict: Dict,
                          response_dict: Dict) -> bool:
        """
        Checks to see if the client has requested to check server status

        Returns:
        --------
        Bool: True if STATUS was called
        """
        status_sent = request_dict['action'] == 'STATUS'
        status_received = response_dict['query'] == 'STATUS'
        return status_sent and status_received

    def _json_encode(self,
                     dict_obj: Dict[str, str],
                     encoding: str) -> bytes:
        """
        Takes a dictionary and converts it to a JSON formatted byte string

        Parameters:
        -----------
        dict_obj: Dict[str, str]
            A dictionary that needs to be converted
        encoding: str
            While the header is always 'utf-8,' the message
            content can have any type.

        Returns:
        --------
        bytes: a byte string containing the dict_obj information
        """
        return json.dumps(dict_obj, ensure_ascii=False).encode(encoding)

    def _json_decode(self,
                     json_bytes: bytes,
                     encoding: str) -> Dict[str, str]:
        """
        Takes a JSON formatted byte string and converts it to a dictionary

        Parameters:
        -----------
        json_bytes: bytes
            A byte string containing the dict_obj information
        encoding: str
            While the header is always 'utf-8,' the message
            content can have any type.

        Returns:
        --------
        Dict[str, str]: a dictionary made from the input dict_obj
        """
        obj = json.loads(json_bytes.decode(encoding))
        return obj

    def _create_message(self,
                        content: Dict[str, str],
                        encoding: str) -> bytes:
        """
        Creates the full message to be sent across the socket connection.

        Parameters:
        -----------
        * This notes that this method is a keyword only argument so all
            parameters must be named.
        content: Dict[str, str]
            The JSON message to be sent

        Returns:
        --------
        bytes: a binary encoded string made from the input parameters
        """
        # The content can be encoded using any desired method
        content_bytes = self._json_encode(content, encoding)
        header = {
            'byteorder': sys.byteorder,
            'message-type': MESSAGE_TYPE,
            'message-encoding': encoding,
            'message-length': len(content_bytes),
        }
        # The header must be encoded using utf-8 so that it can be
        # decoded.  The header has a key which gives the encoding type
        header_bytes = self._json_encode(header, 'utf-8')
        message_hdr = struct.pack('>H', len(header_bytes))
        message = message_hdr + header_bytes + content_bytes
        return message

    def _process_proto_header(self) -> Optional[int]:
        """
        Reads the ._recv_buffer to find the header and save it to
        ._json_header_len.  This method removes the header info from
        ._recv_buffer.

        Returns:
            Length of the JSON header
        """
        if len(self._recv_buffer) >= HEADER_BYTE_LENGTH:
            # format = >H, which means:
            #   > = big-endian
            #   H = unsigned short, length = 2 bytes
            # This returns a tuple, but only the first item has a value,
            # which is why the line ends with [0]
            json_header_len = struct.unpack(
                '>H',
                self._recv_buffer[:HEADER_BYTE_LENGTH])[0]
            if len(self._recv_buffer) > json_header_len:
                # Now that we know how big the header is, we can trim
                # the buffer and remove the header length info
                self._recv_buffer = self._recv_buffer[HEADER_BYTE_LENGTH:]
            return json_header_len

    def _process_json_header(self, header_len: int) -> Optional[Dict]:
        """
        This processes ._recv_buffer to get information from the JSON
        header and then remove the header from ._recv_buffer.
        """
        self._confirm_json_style(self._recv_buffer, 0,  header_len)

        # The buffer holds the header and the data.  This makes sure
        # that the buffer is at least as long as we expect.  It will
        # be longer if there is data.
        if len(self._recv_buffer) >= header_len:
            # parse the buffer to save the header
            try:
                self.json_header = self._json_decode(
                                        self._recv_buffer[:header_len],
                                        'utf-8')
            except UnicodeDecodeError as e:
                msg = f'\nFull received buffer = {self._recv_buffer}'
                msg += '\nBuffer sent to ._json_decode = '
                msg += f'{self._recv_buffer[:header_len]}'
                self.log_message(msg)

                original_traceback = traceback.format_exc()
                traceback_with_msg = original_traceback + msg
                raise UnicodeDecodeError(e.encoding,
                                         e.object,
                                         e.start,
                                         e.end,
                                         traceback_with_msg)

            # This ensures that the header has all of the required fields
            for required_header in (
                    'byteorder',
                    'message-length',
                    'message-type',
                    'message-encoding',
                    ):
                if required_header not in self.json_header:
                    msg = f'Missing required header "{required_header}".'
                    raise ValueError(msg)

            # Then cut the buffer down to remove the header so that
            # now the buffer only has the data.
            self._recv_buffer = self._recv_buffer[header_len:]
            return self.json_header

    def _confirm_json_style(self,
                            buffer: bytes,
                            char_start: int,
                            char_end: int):
        # While It isn't possible to confirm that the whole message is
        # correct, we can do some simple checking on the format.  If
        # there is an unexpected character at the start, we have an issue
        start_bracket = buffer[char_start:char_start + 1] == b'{'
        close_bracket = buffer[char_end - 1:char_end] == b'}'
        if not start_bracket and not close_bracket:
            msg = 'Bad format for received packet:\n'
            msg += f'"{self._recv_buffer}"\n'
            msg += 'Should be of the format:\n'
            expect = r'\x00g{"byteorder": "little", "message-type": "text/json", "message-encoding": "utf-8", "message-length": 46}{"action": "START", "query": "", "result": ""}'
            msg += expect
            self.logger.info(msg)
            raise SocketError(msg)

    def _process_message(self, json_header: Dict) -> Optional[Dict]:
        """
        This decodes the request/response for mpv socket messages
        """

        content_len = json_header["message-length"]
        if len(self._recv_buffer) < content_len:
            return

        # check if the data is in a json dictionary format
        self._confirm_json_style(self._recv_buffer, 0, content_len)

        data = self._recv_buffer[:content_len]
        self._recv_buffer = self._recv_buffer[content_len:]
        encoding = json_header['message-encoding']
        request = self._json_decode(data, encoding)
        return request

    def _queue_request(self, request: Dict, encoding: str):
        """
        Collects everything needed to create the request message
        for the Server
        """
        message_bytes = self._create_message(request,
                                             encoding)
        self._send_buffer += message_bytes

    #########################################
    #
    # Public Methods
    #
    #########################################

    def log_message(self, msg: str):
        """
        A helper tool to log the socket message.  This uses the
        .verbose flag to decide if it should only log the message
        in the log file, or if it should also print the message.

        Parameters:
        -----------
        msg: str
            The string to be logged
        """
        if self.verbose:
            self.logger.info(msg)
        else:
            self.logger.debug(msg)

    def close(self, sock: socket.socket) -> None:
        """
        Close the socket connection
        """
        msg = f'Closing connection to {self.addr}'
        self.logger.info(msg)
        if sock is not None:
            self.addr = sock.getpeername()
            try:
                # Try to send a closing signal to server
                sock.shutdown(socket.SHUT_RDWR)
            except socket.error:
                pass
            sock.close()

    def get_version(self) -> str:
        """
        Returns the version number
        """
        return self.server_version
