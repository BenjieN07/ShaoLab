#!/usr/bin/env python3
"""
Created on Mon Jun 7 23:47:19 2021

MultiVuClient_base.py is a module for use on a network that has access to a
computer running MultiVuServer.py.  By running this client, a python script
can be used to control a Quantum Design cryostat.

This is the base class.  It has the basic communication commands.  The
MultiVuClient class has specific commands to be used with this class.

@author: D. Jackson
"""

import logging
import sys
import traceback
from socket import timeout as sock_timeout
from time import sleep
from typing import Dict

from .__version import __version__ as mpv_version
from .exceptions import (ClientCloseError, MultiPyVuError, ServerCloseError,
                         SocketError)
from .logging_config import remove_logs, setup_logging
from .project_vars import CLIENT_NAME, CLOCK_TIME, HOST_CLIENT, PORT
from .SocketMessageClient import ClientMessage as _ClientMessage


class ClientBase():
    """
    This class is used for a client to connect to a computer with
    MultiVu running MultiVuServer.py.

    Parameters
    ----------
    host: str (optional)
        The IP address for the server.  Default is 'localhost.'
    port: int (optional)
        The port number to use to connect to the server.
    """

    def __init__(self,
                 host: str = HOST_CLIENT,
                 port: int = PORT,
                 ):
        self.address = (host, port)
        # ClientMessage object
        self._message = None
        self._instr = None
        self.instrument_name = ''
        self._number_of_server_connections = 0

    def __enter__(self):
        """
        The class can be started using context manager terminology
        using 'with.' This connects to a running MultiVuServer.

        Raises
        ------
        ConnectionRefusedError
            This is raised if there is a problem connecting to the server. The
            most common issue is that the server is not running.

        Returns
        -------
        Reference to this class

        """
        # Configure logging
        setup_logging(True)
        self._logger = logging.getLogger(CLIENT_NAME)
        if not self._message:
            self._message = _ClientMessage(self.address)
        try:
            # Setting the retry attempts to just one.  This method
            # is attempting to connect to the server, so we can
            # simplify things by assuming if it doesn't connect on
            # the first attempt, that the server isn't running.
            self._message.setup_client_socket(self.address, 1, 5.0)
        except (sock_timeout, ConnectionRefusedError) as e:
            # Check if already connected to the server
            if self._number_of_server_connections > 0:
                msg = 'Can not use MultiPyVu.Client more than once.  '
                msg += 'Create a new instance of MultiPyVu.Client() for '
                msg += 'second connections.'
                self._logger.info(msg)
                raise MultiPyVuError(msg)
            
            msg = 'Could not connect to the server.  Please ensure the '
            msg += 'server is running, it is not already connected to another '
            msg += 'client, and the address matches '
            msg += f'(using {self.address}).'
            self._logger.info(msg)
            e.args = (msg,)
            raise self.__exit__(*sys.exc_info())
        except BaseException:
            raise self.__exit__(*sys.exc_info())
        self._logger.debug(f'MultiPyVu Version: {mpv_version}')
        self._logger.info(f'Starting connection to {self.address}')
        # send a request to the sever to confirm a connection
        action = 'START'
        response = self._query_server(action)

        if response is None:
            raise MultiPyVuError('Keyboard interrupt')

        if not self._message:
            msg = 'Failed to connect to the server'
            raise ServerCloseError(msg)

        self._logger.info(response['result'])
        self._instr = self._message.instr
        self.instrument_name = self._message.instr.name
        ver = self.get_version()
        if ver != mpv_version:
            self._query_server('CLOSE')
            msg = 'MultiPyVu Server and Client must be running '
            msg += 'the same versions:\n'
            msg += f'\tMultiPyVu.Server: ({ver})\n'
            msg += f'\tMultiPyVu.Client: ({mpv_version})'
            self.__exit__(SystemExit,
                          SystemExit(msg),
                          sys.exc_info()[2])
        self.address = self._message.addr
        # Increment the number of connections to the server
        self._number_of_server_connections += 1
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
        self._logger.debug('Exiting Client')
        send_close = True
        # Error handling
        if isinstance(exc_value, SystemExit):
            remove_logs(self._logger)
            logging.shutdown()
            raise exc_value
        elif isinstance(exc_value, KeyboardInterrupt):
            self._logger.info('Caught keyboard interrupt, exiting')
        elif isinstance(exc_value, ServerCloseError):
            msg = 'Shutting down the server.'
            self._logger.info(msg)
            send_close = False
        elif isinstance(exc_value, ConnectionRefusedError):
            # Note that ServerCloseError (ConnectionAbortedError) and
            # ConnectionRefusedError are subclasses of
            # ClientCloseError (ConnectionError)
            send_close = False
            # brief pause to let the server close
            sleep(CLOCK_TIME)
        elif isinstance(exc_value, ClientCloseError):
            # Note that ServerCloseError (ConnectionAbortedError) and
            # ConnectionRefusedError are subclasses of
            # ClientCloseError (ConnectionError)
            send_close = False
            sleep(CLOCK_TIME)
        elif isinstance(exc_value, TimeoutError):
            send_close = False
        elif isinstance(exc_value, sock_timeout):
            send_close = False
        elif isinstance(exc_value, SocketError):
            send_close = False
        elif isinstance(exc_value, ValueError):
            pass
        elif isinstance(exc_value, MultiPyVuError):
            self._logger.info(exc_value)
        elif isinstance(exc_value, BaseException):
            msg = 'MultiVuClient: error: exception for '
            msg += f'{self.address}:'
            msg += f'\n{traceback.format_exc()}'
            self._logger.info(msg)

            remove_logs(self._logger)
            logging.shutdown()

            # Prior to v2.3.0, this section of the code would force it
            # to quit.  But starting with 2.3.0, it just returns the error
            #
            # using os._exit(0) instead of sys.exit(0) because we need
            # all threads to exit, and we don't know if there will be
            # threads running.  os._exit(0) is more forceful, but in
            # this case everything is wrapped up when calling
            # this method.  Note that this can not clean up anything
            # from other threads, though. If one goes back to quitting,
            # create exit codes to help show why the script quit
            # os._exit(0)

            raise exc_value

        self._reset_client_state(send_close)

        return exc_value

    ###########################
    #  Client Methods
    ###########################

    def open(self):
        """
        This is the entry point into the MultiVuClient.  It connects to
        a running MultiVuServer

        Raises
        ------
        ConnectionRefusedError
            This is raised if there is a problem connecting to the server. The
            most common issue is that the server is not running.

        Returns
        -------
        A reference to this class

        """
        return self.__enter__()

    def close_client(self):
        """
        This command closes the client, but keeps the server running
        """
        err_info = sys.exc_info()
        self.__exit__(*err_info)

        # Add delay to allow socket TIME_WAIT state to resolve
        sleep(1)

    def __close_and_exit(self) -> BaseException:
        """
        calls the __exit__() method
        """
        err_info = sys.exc_info()
        return self.__exit__(*err_info)

    def close_server(self):
        """
        This command closes the server
        """
        self._query_server('EXIT')

    def _reset_client_state(self, send_close: bool):
        """
        Resets the client state to allow for reconnection to the server.
        This preserves address and timeout settings while clearing
        connection state.
        """
        self._logger.debug('Resetting client state')

        # Close the current connection if open
        if self._message:
            if send_close:
                try:
                    # Attempt graceful shutdown if possible
                    if hasattr(self._message, 'sock') and self._message.sock:
                        try:
                            self._query_server('CLOSE')
                        except Exception:
                            # If it failed to close for any reason,
                            # we will ignore it because this is getting
                            # called as the client is shutting down.
                            pass

                        # Close and clean up ClientMessage object
                        self._message.reset_socket_client()
                except Exception as e:
                    self._logger.debug(f"Error during message reset: {e}")
            # Reset connection object
            self._message = None

        # Reset instrument information
        self._instr = None
        self._logger.debug('Client reset complete')

    def get_version(self) -> str:
        """
        Returns the version number
        """
        if self._message:
            return self._message.server_version
        else:
            return mpv_version

    def force_quit_server(self) -> str:
        """
        Forces the MultiPyVu.Server to quit.  This is especially useful if
        something happens to the server and it remains open after the script
        closes.

        Returns:
        --------
        Response from quitting the server. Successfully quitting the client
        results in 'Quit the server at (<ip_address>, <port>)'
        """
        if self._message is None:
            message = _ClientMessage(self.address)
            rtrn_msg = f'Quit the server at {message.addr}'
            try:
                # Since this is, in part, looking to see if the
                # server is even running, we will only make
                # one attempt to make a connection
                sock = message.setup_client_socket(self.address, 1)
                if sock:
                    request = message.create_request('EXIT')
                    message.send_and_receive(request)
                    sock.close()
            except (ServerCloseError, ClientCloseError):
                # this is expected
                pass
            except ValueError as e:
                rtrn_msg = 'Failed to quit the server:\n'
                rtrn_msg += e.args[0]
            except (
                    sock_timeout,
                    ConnectionRefusedError,
                    TimeoutError,
                    SocketError,
                    MultiPyVuError,
                    ):
                rtrn_msg = 'Could not connect to the server at '
                rtrn_msg += f'{self.address}'
        else:
            try:
                request = self._message.create_request('EXIT')
                self._message.send_and_receive(request)
            except (
                    ConnectionAbortedError,
                    ServerCloseError,
                    ClientCloseError,
                    ):
                rtrn_msg = f'Quit the server at {self.address}'
            except ValueError as e:
                rtrn_msg = 'Failed to quit the server:\n'
                rtrn_msg += e.args[0]
            except BaseException as e:
                tb_str = ''.join(traceback.format_exception(None,
                                                            e,
                                                            e.__traceback__,
                                                            )
                                 )
                rtrn_msg = tb_str
        return rtrn_msg

    def is_server_running(self) -> bool:
        """
        Queries the MultiVuServer to see if it is running.

        Returns:
        --------
        True (False) if the server is running (not running).
        """
        if self._message:
            try:
                request = self._message.create_request('ALIVE', '')
                response = self._message.send_and_receive(request)
            except ValueError:
                # Since we received a response, the server must be running
                return True
            except Exception:
                return False
            if response:
                return response['action'] == 'ALIVE'
            else:
                return False
        message = _ClientMessage(self.address)
        try:
            # Since this is, in part, looking to see if the
            # server is even running, we will only make
            # one attempt to make a connection
            sock = message.setup_client_socket(self.address, 1)
            if sock:
                request = message.create_request('ALIVE', '')
                response = message.send_and_receive(request)
                sock.close()
                if response:
                    return response.get('action') == 'ALIVE'
                else:
                    return False
            else:
                msg = f'No server running on {self.address}'
                self._logger.info(msg)
                return False
        except (
                sock_timeout,
                ConnectionRefusedError,
                TimeoutError,
                SocketError,
                MultiPyVuError,
                ):
            return False
        except ValueError:
            # Since we received a response, the server must be running
            return True
        except BaseException:
            return False

    def get_server_status(self) -> str:
        """
        Queries the MultiVuServer for its status.

        Returns:
        --------
        string indicating the server status
        """
        response = {'result': 'closed'}
        if self._message:
            try:
                request = self._message.create_request('STATUS')
                response = self._message.send_and_receive(request)
            except ValueError:
                # Since we received a response, the server must be running
                return 'unknown'
            except BaseException:
                return 'closed'
            if response:
                return response['result']
            else:
                return 'closed'
        message = _ClientMessage(self.address)
        try:
            # Since this is, in part, looking to see if the
            # server is even running, we will only make
            # one attempt to make a connection
            sock = message.setup_client_socket(self.address, 1)
            if sock:
                request = message.create_request('STATUS')
                response = message.send_and_receive(request)
                sock.close()
                if response:
                    return response['result']
        except ValueError:
            # Since we received a response, the server must be running
            return 'unknown'
        except (
                sock_timeout,
                ConnectionRefusedError,
                TimeoutError,
                SocketError,
                MultiPyVuError,
                ):
            pass
        return 'closed'

    def _query_server(self,
                      action: str,
                      query: str = '',
                      ) -> Dict[str, str]:
        """
        Queries the server using the action and query parameters.

        Parameters
        ----------
        action : str
            The general command going to MultiVu:  TEMP(?), FIELD(?), and
            CHAMBER(?), etc..  If one wants to know the value of the action,
            then it ends with a question mark.  If one wants to set the action
            in order for it to do something, then it does not end with a
            question mark.
        query : str, optional
            The query gives the specifics of the command going to MultiVu.  For
            queries. The default is '', which is what is used when the action
            parameter ends with a question mark.

        Returns:
        --------
        The response dictionary from the ClientMessage class.
        """
        response_dict = {}
        if self._message is None:
            raise SocketError('Client not connected to the server')
        try:
            msg = f'query server: "{action}"'
            if query:
                msg += f' "{query}"'
            self._logger.debug(msg)
            request_dict = self._message.create_request(action, query)
            response_dict = self._message.send_and_receive(request_dict)
        except MultiPyVuError as e:
            raise self.__close_and_exit() from e
        except ServerCloseError:
            self.__close_and_exit()
            raise
        except ClientCloseError as e:
            self.close_client()
            response_dict = request_dict
            response_dict['result'] = e.args[0]
        except TimeoutError as e:
            # This includes ClientCloseError, ServerCloseError,
            # and TimeoutError
            response_dict = request_dict
            response_dict['result'] = e.args[0]
        except SocketError as e:
            self.close_client()
            if action in [
                    'ALIVE',
                    'STATUS',
                    ]:
                # set the response action
                response_dict = request_dict
                response_dict['action'] = ''
                response_dict['result'] = 'closed'
            elif action == 'START':
                msg = 'Connection refused. Is another client connected?'
                raise ConnectionRefusedError(msg) from e
            else:
                self._logger.info(e.args[0])
                sys.exit(0)
        except ValueError:
            # This has already been logged, so re-raise the error
            raise
        except KeyboardInterrupt:
            self.close_client()
            sys.exit(0)
        except Exception:
            self.__close_and_exit()
        if response_dict:
            result = response_dict.get('result')
            msg = f' "{action}"'
            if query:
                msg += f' "{query}"'
            msg += f' complete: "{result}"'
            self._logger.debug(msg)
            return response_dict
        else:
            return {}
