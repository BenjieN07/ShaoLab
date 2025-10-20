# -*- coding: utf-8 -*-
"""
This file contains several variables which are used throughout the project.

Created on Mon Sep 27 10:53:06 2021

@author: D. Jackson
"""

import sysconfig
import os
from sys import platform

from .exceptions import PythoncomImportError

py_win_version = 0.0
if platform == 'win32':
    try:
        import win32com.client as win32
    except ImportError:
        raise PythoncomImportError

    # Get the version number for pywin32
    pth = sysconfig.get_path('platlib')
    pth = os.path.join(pth, "pywin32.version.txt")
    if os.path.exists(pth):
        with open(pth) as ver_file_obj:
            version = ver_file_obj.read().strip()
    else:
        raise PythoncomImportError
    # the version number is usually an int, but sometimes
    # it is a fraction, so convert to a float
    py_win_version = float(version)
PYWIN32_VERSION = py_win_version


# this will allow for any local IP address to be used
# note that the server's default is '0.0.0.0' which
# is for accepting all incoming connections, and the Client's
# default is 'localhost' which is for finding the server on
# the client's computer
HOST_SERVER = '0.0.0.0'
HOST_CLIENT = 'localhost'
# non-privileged ports are 1023 < 65535
PORT = 5000

SOCKET_RETRIES = 3
TIMEOUT_LENGTH = 1.0
CLOCK_TIME = 0.3

SERVER_NAME = 'MultiVuServer'
CLIENT_NAME = 'MultiVuClient'

MIN_PYWIN32_VERSION = 300

LOG_NAME = 'QdMultiVu.log'

# Each message starts with a hex number that is this many bytes
# long.  This number is the length of the json header.
HEADER_BYTE_LENGTH = 2
MESSAGE_TYPE = 'text/json',
ENCODING = 'utf-8'
