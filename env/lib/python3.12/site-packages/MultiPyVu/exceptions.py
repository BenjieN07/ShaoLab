"""
Custom exceptions for MultiPyVu
"""


from enum import IntEnum
from sys import exit, platform
from typing import Tuple


class PythoncomImportError(ImportError):
    """
    This is used to deal with no pythoncom module found
    """
    def __init__(self):
        msg  = "Must import the pywin32 module.  Use:  \n"
        msg += "\tconda install -c conda-forge pywin32\n"
        msg += "   or\n"
        msg += "\tpip install pywin32"
        super().__init__(msg)
        exit(msg)


class MultiPyVuError(Exception):
    """
    MultiVu Exception Error
    """
    # Constructor or Initializer
    def __init__(self, message: str):
        mpvex_str = 'MultiPyVuError: '
        if isinstance(message, str) and message.startswith(mpvex_str):
            # the error adds mpvex_str automatically to
            # the front of the text, so remove it
            message = message.replace(mpvex_str, '')
        self.value = f'MultiPyVuError: {message}'
        super().__init__(self.value)


class ClientCloseError(ConnectionError):
    """
    Close the client connection
    """
    def __init__(self, message: str):
        super().__init__(message)


class SocketError(OSError):
    """
    No socket connection
    """
    def __init__(self, message: str):
        super().__init__(message)


class ServerCloseError(ConnectionAbortedError):
    """
    Close the server connection
    """
    def __init__(self, message: str):
        super().__init__(message)


class PwinComError(Exception):
    """Display the pywintypes.com_error"""
    def __init__(self, err: Exception):
        param = ''
        # A pywin_com_error.args is a tuple with 4 terms.
        # The last term gives the argument number, or None.
        # This first looks for that argument number, and 
        # then assumes that the error comes from read/write SDO
        param_num = err.args[3]
        pre_msg = 'Error when attempting to call ReadSDO()/WriteSDO(): '
        m1 = ' in the \''
        m2 = '\' parameter.'
        post_msg = lambda m1, p, m2: f'{m1}{p}{m2}'
        if param_num == 1:
            param = 'Node '
        if param_num == 2:
            param = 'Index'
        if param_num == 3:
            param = 'Sub Index'
        if param_num == 4:
            param = 'SDO Length'
        if param_num == 5:
            param = 'Value Variant'
        if param_num == 6:
            param = 'SDO Error'
        else:
            # make the parameters blank
            pre_msg = 'pywintypes.com_error: '
            m1 = ''
            param = ''
            m2 = ''
        self.message = f'{pre_msg}{err.args[1]}{post_msg(m1, param, m2)}'
        super().__init__(self.message)

    def __str__(self):
        return self.message


class can_err_enum(IntEnum):
    R_SDO_TIMEOUT = 10   # SDO timeout
    R_EMPTY = 9          # The Queue is empty
    R_NOT_READY = 8      # The USB device is busy
    R_INIT = 7           # The USB device is initialized
    R_NOT_INIT = 6       # The USB device was not initialized
    R_NO_NODE = 5        # Node was not found
    R_ABORT = 4          # Command was aborted by module
    R_IV = 3             # Invalid parameter
    R_CAL = 2            # Cal error
    R_NO = 1             # Unspecified error in call
    R_OK = 0             # Call was successful
    R_ERR = -1           # Unspecified error in call
    R_IFERROR = -2       # Interface error
    R_INVALID = -3       # Invalid Selection or length
    # R_ABORT = -4       # Request has been aborted
    R_BUSY = -5          # Another thread is using this routine
    # R_EMPTY = -6       # Queue is empty
    R_INVHNDL = -7       # Invalid handle passed
    R_DISABLED = -8      # Device is disabled
    R_NORESP = -27       # Device is not responding
    R_INVPARAM = -28     # Invalid parameter value or null pointer
    R_COMMERR = -30      # Communication error
    R_VERERR = -32       # Unsuitable version of firmware
    R_NOTFOUND = -34     # Node or device not found
    R_INPROCESS = -35    # Previous request still processing
    R_NOREQUEST = -36    # Data has not been requested
    R_INUSE = -37        # Device already in use
    R_TIMEOUT = -38      # Request has timed out
    R_NONEWDATA = -39    # No new message
    R_NOTSENT = -40      # Data or request was not sent
    R_WRONGDIR = -41     # Indication has wrong transfer direction


def can_error_msg(can_err: int) -> str:
    """
    Returns a description of the can error which is returned
    from either self._mvu.ReadSDO() or self._mvu.WriteSDO()
    """
    if can_err == can_err_enum.R_SDO_TIMEOUT:
        return "SDO timeout"
    elif can_err == can_err_enum.R_EMPTY:
        return "The Queue is empty"
    elif can_err == can_err_enum.R_NOT_READY:
        return "The USB device is busy"
    elif can_err == can_err_enum.R_INIT:
        return "The USB device is initialized"
    elif can_err == can_err_enum.R_NOT_INIT:
        return "The USB device was not initialized"
    elif can_err == can_err_enum.R_NO_NODE:
        return "Node was not found"
    elif can_err == can_err_enum.R_ABORT:
        return "Command was aborted by module"
    elif can_err == can_err_enum.R_IV:
        return "Invalid parameter"
    elif can_err == can_err_enum.R_CAL:
        return "Invalid Board Handle (Cal Error)"
    elif can_err == can_err_enum.R_NO:
        return "Unspecified error in call"
    elif can_err == can_err_enum.R_OK:
        return "Call was successful"
    elif can_err == can_err_enum.R_ERR:
        return "Unspecified error in call"
    elif can_err == can_err_enum.R_IFERROR:
        return "Interface error"
    elif can_err == can_err_enum.R_INVALID:
        return "Invalid Selection or length"
    elif can_err == can_err_enum.R_BUSY:
        return "Another thread is using this routine"
    elif can_err == can_err_enum.R_INVHNDL:
        return "Invalid handle passed"
    elif can_err == can_err_enum.R_DISABLED:
        return "Device is disabled"
    elif can_err == can_err_enum.R_NORESP:
        return "Device is not responding"
    elif can_err == can_err_enum.R_INVPARAM:
        return "Invalid parameter value or null pointer"
    elif can_err == can_err_enum.R_COMMERR:
        return "Communication error"
    elif can_err == can_err_enum.R_VERERR:
        return "Unsuitable version of firmware"
    elif can_err == can_err_enum.R_NOTFOUND:
        return "Node or device not found"
    elif can_err == can_err_enum.R_INPROCESS:
        return "Previous request still processing"
    elif can_err == can_err_enum.R_NOREQUEST:
        return "Data has not been requested"
    elif can_err == can_err_enum.R_INUSE:
        return "Device already in use"
    elif can_err == can_err_enum.R_TIMEOUT:
        return "Request has timed out"
    elif can_err == can_err_enum.R_NONEWDATA:
        return "No new message"
    elif can_err == can_err_enum.R_NOTSENT:
        return "Data or request was not sent"
    elif can_err == can_err_enum.R_WRONGDIR:
        return "Indication has wrong transfer direction"
    else:
        return "Unknown error"


class abort_err_enum(IntEnum):
    NORMAL_CONF = 0x00000000            #
    WRONG_TOGGLEBIT = 0x05030000        # Toggle bit not alternated.
    SDO_PROTOCOL_TIMEOUT = 0x05040000   # SDO protocol timed out.
    UNKNOWN_SPECIFIER = 0x05040001      # Client/server command specified not
                                        # valid or unknown.
    INVALID_BLOCK_SIZE = 0x05040002     # Invalid block size (block mode only).
    INVALID_SEQ_NUM = 0x05040003        # Invalid sequence number (block mode
                                        # only).
    CRC_ERROR = 0x05040004              # CRC error (block mode only).
    OUT_OF_MEMORY = 0x05040005          # Out of memory.
    READ_WRITE_ONLY = 0x06010000        # Unsupported access to an object.
    WRITE_ONLY = 0x06010001             # Attempt to read a write-only object.
    READ_ONLY = 0x06010002              # Attempt to write a read-only object.
    NOT_IN_DICTIONARY = 0x06020000      # Object does not exist in the object
                                        # dictionary.
    PDO_NOT_MAPPED = 0x06040041         # Object cannot be mapped to the PDO.
    PDO_TOO_LONG = 0x06040042           # Length of objects mapped would
                                        # exceed PDO length.
    INCOMPATIBLE_PARAM = 0x06040043     # General parameter incompatibility
                                        # reason.
    GEN_INTERNAL_ERR = 0x06040047       # General internal incompatibility in
                                        # the device.
    LOAD_SAVE_HDWR_ERR = 0x06060000     # Access failed due to a hardware error.
    DATATYPE_UNKNOWN = 0x06070010       # Data type or length of service param
                                        # does not match.
    DATATYPE_TOO_LONG = 0x06070012      # Data type or length of service param
                                        # too high.
    DATATYPE_TOO_SHORT = 0x06070013     # Data type or length of service param
                                        # too low.
    SUBINDEX_NOT_FOUND = 0x06090011     # Sub-index does not exist.
    RANGE_EXCEEDED = 0x06090030         # Value range of parameter exceeded
                                        # (only for write access).
    RANGE_OVERFLOW = 0x06090031         # Value of parameter written too high.
    RANGE_UNDERFLOW = 0x06090032        # Value of parameter written too low.
    MAX_LESS_THAN_MIN = 0x06090036      # Maximum value is less than minimum
                                        # value.
    RESOURCE_NOT_AVAIL = 0x060A0023     # Resource not available.
    GENERAL_SDO_ERROR = 0x08000000      # General error.
    SERVICE_NOT_EXECUTED = 0x08000020   # Data cannot be transferred or stored to
                                        # the application.
    LOCAL_CONTROL_ERROR = 0x08000021    # Data cannot be transferred or stored
                                        # because of local control.
    SERVICE_ERROR = 0x08000022          # Data cannot be transferred or stored
                                        # because of device state.
    NO_OBJECT_DICTIONARY = 0x08000023   # No object dictionary is present. May
                                        # be due to dynamic generation failure
                                        # or file error.
    NO_DATA_AVAILABLE = 0x08000024      #


def abort_error_msg(err: int) -> Tuple[str, bool]:
    """
    Converts the error_variant.value into string in words
    describing the error.  It also lets us know if it
    is worth the effort to retry calling the SDO.

    See http://svnserver.qdusa.com/repos/167CR/CanOpenLib/trunk/Error%20Code%20cross%20link%20and%20def.xls
    for error code reference.

    Parameters:
    -----------
    err: int
        The abort error code

    Returns:
    --------
    Tuple with the code in words and bool for retry
    """
    if err == abort_err_enum.WRONG_TOGGLEBIT:
        return ("unspecified error occurred", True)
    elif err == abort_err_enum.SDO_PROTOCOL_TIMEOUT:
        return ("SDO protocol timed out.", False)
    elif err == abort_err_enum.INVALID_SEQ_NUM:
        return ("invalid sequence number", True)
    elif err == abort_err_enum.INVALID_BLOCK_SIZE:
        return ("invalid block size", True)
    elif err == abort_err_enum.CRC_ERROR:
        return ("CRC checksum error", True)
    elif err == abort_err_enum.UNKNOWN_SPECIFIER:
        return ("client/server command specifier not valid or unknown", True)
    elif err == abort_err_enum.OUT_OF_MEMORY:
        return ("out of memory", True)
    elif err == abort_err_enum.READ_WRITE_ONLY:
        return ("unsupported access to an object", False)
    elif err == abort_err_enum.WRITE_ONLY:
        return ("attempt to read a write only object", False)
    elif err == abort_err_enum.READ_ONLY:
        return ("attempt to write a read only object", False)
    elif err == abort_err_enum.NOT_IN_DICTIONARY:
        return ("object does not exist in object directory", True)
    elif err == abort_err_enum.PDO_NOT_MAPPED:
        return ("object cannot be mapped to the appeal", False)
    elif err == abort_err_enum.PDO_TOO_LONG:
        msg = "the number and length of the objects to be mapped "
        msg += "would exceed PDO length"
        return (msg, False)
    elif err == abort_err_enum.INCOMPATIBLE_PARAM:
        return ("general parameter incompatibility error", False)
    elif err == abort_err_enum.GEN_INTERNAL_ERR:
        return ("general interrupt error", True)
    elif err == abort_err_enum.LOAD_SAVE_HDWR_ERR:
        return ("save / load failed due to hardware error", True)
    elif err == abort_err_enum.DATATYPE_UNKNOWN:
        msg = "datatype does not match, length of service "
        msg += "parameter does not match"
        return (msg, False)
    elif err == abort_err_enum.DATATYPE_TOO_LONG:
        msg = "datatype does not match, length of service "
        msg += "parameter too high"
        return (msg, False)
    elif err == abort_err_enum.DATATYPE_TOO_SHORT:
        msg = "datatype does not match, length of service "
        msg += "parameter too low"
        return (msg, False)
    elif err == abort_err_enum.SUBINDEX_NOT_FOUND:
        return ("subindex does not exist", False)
    elif err == abort_err_enum.RANGE_EXCEEDED:
        return ("value range of parameter exceeded", True)
    elif err == abort_err_enum.RANGE_OVERFLOW:
        return ("value of parameter too high", False)
    elif err == abort_err_enum.RANGE_UNDERFLOW:
        return ("value of parameter too low", False)
    elif err == abort_err_enum.MAX_LESS_THAN_MIN:
        return ("Maximum value is less than minimum value.", False)
    elif err == abort_err_enum.RESOURCE_NOT_AVAIL:
        return ("Resource not available.", False)
    elif err == abort_err_enum.GENERAL_SDO_ERROR:
        return ("CAN Open internal error", False)
    elif err == abort_err_enum.SERVICE_NOT_EXECUTED:
        msg = "data cannot be transferred or stored to the application"
        return (msg, True)
    elif err == abort_err_enum.LOCAL_CONTROL_ERROR:
        msg = "data cannot be transferred of stored to the application "
        msg += "because of local control"
        return (msg, True)
    elif err == abort_err_enum.SERVICE_ERROR:
        msg = "data cannot be transferred or stored to the application "
        msg += "because of the present device state"
        return (msg, True)
    elif err == abort_err_enum.NO_OBJECT_DICTIONARY:
        return ("resource not available", True)
    elif err == abort_err_enum.NO_DATA_AVAILABLE:
        return ("No data available", True)
    else:
        return ("Unknown error", False)


if platform == 'win32':
    try:
        from pywintypes import com_error as pywin_com_error
    except ImportError:
        raise PythoncomImportError
else:
    # defining this ensures that an object has this name,
    # but it should really only be used on win32 systems
    pywin_com_error = PwinComError


class CanError(Exception):
    def __init__(self, can_err: int, sdo_err: int):
        err_msg = can_error_msg(can_err)
        if can_err == can_err_enum.R_ABORT:
            err_msg, _ = abort_error_msg(sdo_err)
        if can_err != can_err_enum.R_OK:
            err_msg = 'CAN Error: ' + err_msg
        super().__init__(err_msg)
