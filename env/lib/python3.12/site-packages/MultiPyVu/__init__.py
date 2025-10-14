"""
MultiPyVu provides the ability to control the temperature, magnetic field,
and chamber status of Quantum Design, Inc. products using python.  This
module includes Server(), which runs on the same computer as MultiVu,
and Client(), which is where one writes the python script to control
MultiVu.  Client() can be used within the same script as
Server(), or within its own script that runs either on the same
computer as MultiVu, or any other computer that has TCP access to the
computer running Server().  The module also contains DataFile(), which
is used to save data to a MultiVu .dat file, and read a .dat file into
a Pandas DataFrame.

One can open a gui to start the Server by calling:

> python3 -m MultiPyVu

And scripts can import the module, for example:

Import MultiPyVu as mpv


@author: Damon D Jackson
"""

import traceback
from enum import IntEnum as _IntEnum
from enum import auto as _auto
from os import path
from sys import exc_info
from typing import Optional, Union

from pandas import DataFrame

from .__version import __version__
from .exceptions import MultiPyVuError, SocketError
from .MultiVuClient import Client
from .MultiVuDataFile.MultiVuDataFile import LabelResult
from .MultiVuDataFile.MultiVuDataFile import \
    MultiVuDataFile as _MultiVuDataFile
from .MultiVuDataFile.MultiVuDataFile import MultiVuFileException
from .MultiVuDataFile.MultiVuDataFile import TScaleType as _TScaleType
from .MultiVuDataFile.MultiVuDataFile import \
    TStartupAxisType as _TStartupAxisType
from .MultiVuDataFile.MultiVuDataFile import TTimeMode as _TTimeMode
from .MultiVuDataFile.MultiVuDataFile import TTimeUnits as _TTimeUnits
from .MultiVuServer import Server

__version__ = __version__
__author__ = 'Damon D Jackson'
__credits__ = 'Quantum Design, Inc.'
__license__ = 'MIT'


# create a new class which inherits MultiVuDataFile,
# but modifies the enums to make them simpler.

class _Scale_T(_IntEnum):
    linear_scale = _auto()
    log_scale = _auto()


class _Startup_Axis_T(_IntEnum):
    none = 0
    X = 1
    Y1 = 2
    Y2 = 4
    Y3 = 8
    Y4 = 16


class _Time_Units_T(_IntEnum):
    minutes = _auto()
    seconds = _auto()


class _Time_Mode_T(_IntEnum):
    relative = _auto()
    absolute = _auto()


class BadFileError(Exception):
    """
    Custom error for showing if the file is not found
    """
    def __init__(self, original_exception):
        # store the original error
        self.original_exception = original_exception
        self.module_folder = self.get_module_folder()
        self.characters_written = ''

    def get_module_folder(self):
        # get teh path to the current module's __init__.py file

        # point to the current file if it's __init__.py
        module_path = __file__
        module_folder = path.dirname(module_path)
        return module_folder

    def __str__(self):
        # get the original stack trace
        tb = exc_info()[2]
        # extract the traceback
        stack = traceback.extract_tb(tb)
        # filter out the frames that are
        # within this module
        filtered_stack = [
            frame for frame in stack if not frame.filename.startswith(self.module_folder)
        ]
        # format the stack trace to display only the external frames
        formatted_stack = traceback.format_list(filtered_stack)
        # return the filtered stack and the original exception message
        return_err = ''.join(formatted_stack)
        return_err += f"{self.original_exception.strerror}: "
        return_err += f"'{self.original_exception.filename}'"
        self.characters_written = return_err
        return return_err


class DataFile():
    """
    This class is used to save data in the proper MultiVu file format.
    An example for how to use this class may be:
        >
        > import MultiPyVu as mpv
        >
        > data = mpv.MultiVuDataFile()
        > mv.add_column('myY2Column', data.startup_axis.Y2)
        > mv.add_multiple_columns(['myColumnA', 'myColumnB', 'myColumnC'])
        > mv.create_file_and_write_header('myMultiVuFile.dat', 'Using Python')
        > mv.set_value('myY2Column', 2.718)
        > mv.set_value('myColumnA', 42)
        > mv.set_value('myColumnB', 3.14159)
        > mv.set_value('myColumnC', 9.274e-21)
        > mv.write_data()
        >
        > myDataFrame = data.parse_MVu_data_file('myMultiVuFile.dat')

    """
    def __init__(self):
        # references to enums
        self.scale = _Scale_T
        self.startup_axis = _Startup_Axis_T
        self.time_units = _Time_Units_T
        self.time_mode = _Time_Mode_T
        self.data_file = _MultiVuDataFile()

    def get_comment_col(self) -> str:
        return self.data_file.get_comment_col()

    def get_time_col(self) -> str:
        return self.data_file.get_time_col()

    def test_label(self, label) -> LabelResult:
        """
        Return the type of label.

        Parameters
        ----------
        label : string

        Returns
        -------
        LabelResult.success : LabelResults

        Example
        -------
        >>> test_label('Comment')
            success
        """
        return self.data_file.test_label(label)

    def add_column(self,
                   label: str,
                   startup_axis: _Startup_Axis_T = _Startup_Axis_T.none,
                   scale_type: _Scale_T = _Scale_T.linear_scale,
                   persistent: bool = False,
                   field_group: str = ''
                   ) -> None:
        """
        Add a column to be used with the datafile.

        Parameters
        ----------
        label : string
            Column name
        startup_axis : Startup_Axis_T, optional
            Used to specify which axis to use when plotting the column.
            .startup_axis.none (default)
            .startup_axis.X (default is the time axis)
            .startup_axis.Y1
            .startup_axis.Y2
            .startup_axis.Y3
            .startup_axis.Y4
        scale_type : Time_Units_T, optional
            .time_units.linear_scale (default)
            .time_units.log_scale
        Persistent : boolean, optional
            Columns marked True have the previous value saved each time data
            is written to the file.  Default is False
        field_group : string, optional

        Raises
        ------
        MultiVuFileException
            Can only write the header once.

        Returns
        -------
        None.

        Example
        -------
        >>> add_column('MyDataColumn')
        """
        start = _TStartupAxisType(startup_axis)
        scale = _TScaleType(scale_type)
        return self.data_file.add_column(label,
                                         start,
                                         scale,
                                         persistent,
                                         field_group,
                                         )

    def add_multiple_columns(self, column_names: list) -> None:
        """
        Add a column to be used with the datafile.

        Parameters
        ----------
        column_names : list
            List of strings that have column names

        Returns
        -------
        None.

        Example
        -------
        >>> add_multiple_columns(['MyDataColumn1', 'MyDataColumn2'])
        """
        return self.data_file.add_multiple_columns(column_names)

    def create_file_and_write_header(self,
                                     file_name: str,
                                     title: str,
                                     time_units: _Time_Units_T = _Time_Units_T.seconds,
                                     time_mode: _Time_Mode_T = _Time_Mode_T.relative
                                     ):
        units = _TTimeUnits(time_units)
        mode = _TTimeMode(time_mode)
        return self.data_file.create_file_and_write_header(file_name,
                                                           title,
                                                           units,
                                                           mode)

    def set_value(self, label: str, value: Union[str, int, float]):
        """
        Sets a value for a given column.  After calling this method, a call
        to write_data() will save this to the file.

        Parameters
        ----------
        label : string
            The name of the data column.
        value : string, int, or float
            The data that needs to be saved.

        Raises
        ------
        MultiVuFileException
            The label must have been written to the file.

        Returns
        -------
        None.

        Example
        -------
        >>> set_value('myColumn', 42)

        """
        return self.data_file.set_value(label, value)

    def get_value(self, label: str) -> Union[str, int, float]:
        """
        Returns the last value that was saved using set_value(label, value)

        Parameters
        ----------
        label : str
            Column name.

        Raises
        ------
        MultiVuFileException
            The label must have been written to the file.

        Returns
        -------
        str, int, or float
            The last value saved using set_value(label, value).

        Example
        -------
        >>> get_value('myColumn')
        >>> 42

        """
        return self.data_file.get_value(label)

    def get_fresh_status(self, label: str) -> bool:
        """
        After calling set_value(label, value), the value is considered Fresh
        and is waiting to be written to the MultiVu file using write_data()

        Parameters
        ----------
        label : str
            Column name.

        Raises
        ------
        MultiVuFileException
            The label must have been written to the file.

        Returns
        -------
        boolean
            True means the value has not yet been saved to the file

        Example
        -------
        >>> get_fresh_status('myColumn')
        >>> True

        """
        return self.data_file.get_fresh_status(label)

    def set_fresh_status(self, label: str, status: bool):
        """
        This allows one to manually set the Fresh status, which is used
        to decide if the data will be written to the file when calling
        write_data()

        Parameters
        ----------
        label : str
            Column name.
        status : boolean
            True (False) means the value in the column label
            will (not) be written.

        Raises
        ------
        MultiVuFileException
            The label must have been written to the file.

        Returns
        -------
        None.

        Example
        -------
        >>> set_fresh_status('myColumn', True)
        """
        return self.data_file.set_fresh_status(label, status)

    def write_data(self, get_time_now: bool = True):
        """
        Writes all fresh or persistent data to the MultiVu file.

        Parameters
        ----------
        get_time_now : boolean, optional
            By default, the time when this method is called will be
            written to the MultiVu file. The default is True.

        Raises
        ------
        MultiVuFileException
            create_file_and_write_header() must be called first.

        Returns
        -------
        None.

        Example
        -------
        >>> write_data()
        """
        return self.data_file.write_data(get_time_now)

    def write_data_using_list(self,
                              data_list: list,
                              get_time_now: bool = True):
        """
        Function to set values fromm list and then write them to data file
        Format of list is ColKey1, Value1, ColKey2, Value2, ...
        The list can contain values for all columns or a subset of columns,
        in any order

        Parameters
        ----------
        data_list : list
            A list of column names and values.
        get_time_now : boolean, optional
            By default, the time when this method is called will be
            written to the MultiVu file. The default is True.

        Raises
        ------
        MultiVuFileException
            The number of columns and data must be equal, which means
            that the list needs to have an even number of items.

        Returns
        -------
        None.

        Example
        -------
        >>> write_data_using_list(['myColumn1', 42, 'myColumn2', 3.14159])
        """
        return self.data_file.write_data_using_list(data_list, get_time_now)

    def parse_MVu_data_file(self,
                            file_path: Optional[str] = None) -> DataFrame:
        """
        Returns a pandas DataFrame of all data points in the given file

        Parameters
        ----------
        file_path : str
            Path to the MultiVu file.

        Returns
        -------
        pandas.DataFrame
            A DataFrame which includes all of the columns and data.

        Example
        -------
        >>> parse_MVu_data_file('myMvFile.dat')

        """
        if file_path is None:
            file_path = self.data_file.full_path
        try:
            _df = self.data_file.parse_MVu_data_file(file_path)
        except FileNotFoundError as e:
            raise BadFileError(e) from None
        else:
            return _df
