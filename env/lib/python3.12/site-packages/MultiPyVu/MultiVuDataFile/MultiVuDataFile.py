'''
Created on Tue Sep  8 14:23:28 2020

MultiVuDataFile.py is a module that allows for reading and writing MultiVu
files.  This code was ported from MultiVuDataFile.vb.

@author: Quantum Design, Inc.
'''


import os
import time
import re
import pandas as pd
from threading import Lock
from enum import Enum, auto, IntEnum
from datetime import datetime
from typing import Union, Dict

from .is_pathname_valid import is_pathname_valid

LINE_TERM = '\r\n'
COMMENT_COL_HEADER = 'Comment'
TIME_COL_HEADER = 'Time Stamp (sec)'


class TScaleType(Enum):
    mv_linear_scale = auto()
    mv_log_scale = auto()


class TStartupAxisType(IntEnum):
    mv_startup_axis_none = 0
    mv_startup_axis_X = 1
    mv_startup_axis_Y1 = 2
    mv_startup_axis_Y2 = 4
    mv_startup_axis_Y3 = 8
    mv_startup_axis_Y4 = 16


class TTimeUnits(Enum):
    mv_minutes = auto()
    mv_seconds = auto()


class TTimeMode(Enum):
    mv_relative = auto()
    mv_absolute = auto()


class DataColumn():
    def __init__(self):
        self.index: int = 0
        self.label: str = ''
        self.value = 0
        self.scale_type = TScaleType.mv_linear_scale
        self.startup_axis = TStartupAxisType.mv_startup_axis_none
        self.field_group: str = ''
        self.persistent: bool = False
        self.is_fresh: bool = False


class LabelResult(Enum):
    success = auto()
    blank = auto()
    only_spaces = auto()
    contains_quotes = auto()


class MultiVuDataFile():
    '''
    This class is used to save data in the proper MultiVu file format.
    An example for how to use this class may be:
        > import pandas as pd
        >
        > mv = MultiVuDataFile()
        > mv.add_column('myY2Column', mv.startup_axis.mv_startup_axis_Y2)
        > mv.add_multiple_columns(['myColumnA', 'myColumnB', 'myColumnC'])
        > mv.create_file_and_write_header('myMultiVuFile.dat', 'Using Python')
        > mv.set_value('myY2Column', 2.718)
        > mv.set_value('myColumnA', 42)
        > mv.set_value('myColumnB', 3.14159)
        > mv.set_value('myColumnC', 9.274e-21)
        > mv.write_data()
        >
        > pd.myDataFrame = mv.parse_MVu_data_file('myMultiVuFile.dat')

    '''

    def __init__(self):
        # Make it so that we can add columns
        self.__have_written_header: bool = False
        self.file_name: str = ''
        self.full_path: str = ''
        # Add default columns
        self._column_list: list = []
        self.add_column(COMMENT_COL_HEADER)
        self.add_column(TIME_COL_HEADER, TStartupAxisType.mv_startup_axis_X)

    def get_comment_col(self) -> str:
        return COMMENT_COL_HEADER

    def get_time_col(self) -> str:
        return TIME_COL_HEADER

    def _create_file(self, file_name: str) -> bool:
        '''
        Create the MultiVu file, if it doesn't already exist'

        Parameters
        ----------
        file_name : string
            Path the to file name.

        Returns
        -------
        new_file : boolean
            True if the file already exists, False if it did not exist

        Example
        -------
        >>> _create_file('myFile.dat')
            False
        '''
        self.full_path = os.path.abspath(file_name)
        dir_name, file_name = os.path.split(self.full_path)
        try:
            if not dir_name:
                err_msg = f'Invalid file path: {file_name}. Please '
                err_msg += 'use a valid path.'
                raise NotADirectoryError(err_msg)
        except NotADirectoryError:
            if not is_pathname_valid(file_name):
                raise NotADirectoryError(f'File path {file_name} is invalid.')

        # Make sure we have the folder which is supposed to hold the
        # file in question.  If the folder already exists, move on,
        # if the folder does not exist, then create it.
        if not os.path.exists(dir_name):
            try:
                os.mkdir(dir_name)
            except PermissionError:
                err_msg = f'Failed to create directory {dir_name}. Verify '
                err_msg += 'that you have permission to create this directory.'
                raise PermissionError(err_msg)
        self.file_name = file_name
        # return FALSE if file already existed, TRUE if this was a new creation
        new_file = not os.path.isfile(self.full_path)
        # open the file, which will create it if it doesn't already exist
        if new_file:
            self.__open_file()
            self.__close_file()
        return new_file

    def __open_file(self):
        num_tries = 10
        while (num_tries > 0):
            try:
                self.__FS = open(self.full_path, 'w')
                num_tries = -1
            except PermissionError:
                # we might have had a race condition trying to open the
                # file - we'll just try again
                num_tries -= 1
                self.__close_file()
                time.sleep(0.100)  # milliseconds
        if (num_tries == 0):
            err_msg = 'Failed to open MultiVu data file after '
            err_msg += '{num_tries} attempts. Verify that you have '
            err_msg += f'permission to write to {self.full_path}.'
            raise PermissionError(err_msg)

    def __close_file(self):
        self.__FS.close()

    def test_label(self, label) -> LabelResult:
        '''
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
        '''
        m = re.compile('^ +$')

        # Check if label is a string
        if not label:
            return LabelResult.blank
        if m.search(label):
            return LabelResult.only_spaces
        if '"' in label:
            return LabelResult.contains_quotes
        return LabelResult.success

    def bit_not(self, n: int, num_bits: int = 4) -> int:
        '''
        bytewise NOT

        Parameters
        ----------
        n : int
        num_bits : int, optional

        Returns
        -------
        bit_not : int

        Example
        -------
        >>> bin(bit_not(1))
            0b1110
        '''
        return (1 << num_bits) - 1 - n

    def add_column(self,
                   label: str,
                   startup_axis: TStartupAxisType = TStartupAxisType.mv_startup_axis_none,
                   scale_type: TScaleType = TScaleType.mv_linear_scale,
                   persistent: bool = False,
                   field_group: str = '') -> None:
        '''
        Add a column to be used with the datafile.

        Parameters
        ----------
        label : string
            Column name
        startup_axis : TStartupAxisType, optional
            Used to specify which axis to use when plotting the column.
            TStartupAxisType.mv_startup_axis_none (default)
            TStartupAxisType.mv_startup_axis_X (default is the time axis)
            TStartupAxisType.mv_startup_axis_Y1
            TStartupAxisType.mv_startup_axis_Y2
            TStartupAxisType.mv_startup_axis_Y3
            TStartupAxisType.mv_startup_axis_Y4
        scale_type : TScaleType, optional
            TScaleType.mv_linear_scale (default)
            TScaleType.mv_log_scale
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
        '''

        result = self.test_label(label)
        if result != LabelResult.success:
            err_msg = f'Error in column label: {result.ToString}'
            raise MultiVuFileException(err_msg)

        if self.__have_written_header is True:
            err_msg = f"Not adding column '{label}' because the file "
            err_msg += "header has already been written to file "
            err_msg += f"'{self.full_path}'."
            raise MultiVuFileException(err_msg)

        # If we already have a column with the same name, remove
        # it before adding the new one
        for i, col in enumerate(self._column_list):
            if label == col.label:
                self._column_list.pop(i)
                break

        x_axis = TStartupAxisType.mv_startup_axis_X
        if ((startup_axis & x_axis) != 0):
            # Unset all others because we can have only one x-axis
            temp_list = []
            for item in self._column_list:
                if ((item.startup_axis & x_axis) != 0):
                    temp_list.append(item)
            for item in temp_list:
                check_axis = self.bit_not(x_axis.value)
                item.startup_axis = TStartupAxisType(item.startup_axis.value &
                                                     check_axis)

        dc = DataColumn()
        dc.label = label
        # make sure that comment/time columns are always the
        # first two columns in the data file
        if (label == COMMENT_COL_HEADER):
            dc.index = 1
        elif (label == TIME_COL_HEADER):
            dc.index = 2
        else:
            max_index = 0
            for item in self._column_list:
                max_index = max(max_index, item.index)
            dc.index = max_index + 1

        # Set the startup axes to the requested values (can be
        # added for multiple axes per column)
        dc.startup_axis = startup_axis
        dc.scale_type = scale_type
        dc.persistent = persistent
        dc.field_group = field_group
        dc.is_fresh = False
        dc.value = None

        self._column_list.append(dc)

    def add_multiple_columns(self, column_names: list) -> None:
        '''
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
        '''
        for name in column_names:
            self.add_column(name)

    def __get_index(self, e: DataColumn) -> int:
        '''

        Parameters
        ----------
        e : DataColumn class
            Used to sort a list of DataColumns by index number.

        Returns
        -------
        DataColumn.index
        '''
        return e.index

    def create_file_and_write_header(self,
                                     file_name: str,
                                     title: str,
                                     time_units=TTimeUnits.mv_seconds,
                                     time_mode=TTimeMode.mv_relative):
        '''
        Create the file if it doesn't already exist.  If it already exists,
        exit the function so we don't write the header again. If it does not
        already exist, write the header.

        Parameters
        ----------
        file_name : string
            The path for where to save the MultiVu file
        title : string
            MultiVu file title.
        time_units : TTimeUnits, optional
            TTimeUnits.mv_minutes
            TTimeUnits.mv_seconds (default)
        time_mode : TTimeMode, optional
            TTimeMode.mv_relative (default)
            TTimeMode.mv_absolute

        Raises
        ------
        MultiVuFileException

        Returns
        -------
        None.

        Example
        -------
        >>> create_file_and_write_header('myMvFile', 'my sample')
        '''
        file_exists = self._create_file(file_name)
        if not file_exists:
            # parse the existing headers so that we can verify that we have
            # all the columns we need and set their order to the order in
            # the data file
            in_headers = True
            column_headers = ''
            with open(file_name) as f:
                for raw_line in f:
                    line = raw_line.rstrip()
                    if in_headers:
                        in_headers = (line != '[Data]')
                    else:
                        column_headers = line
                        break

            if (column_headers != ''):
                column_headers = column_headers.lstrip('"')
                column_headers = column_headers.rstrip('"')
                existing_col_headers = column_headers.split('","')
                if (len(self._column_list) != len(existing_col_headers)):
                    err_msg = "Failed to append to existing file "
                    err_msg += f"'{file_name}' - mismatch in number of "
                    err_msg += "columns."
                    raise MultiVuFileException(err_msg)
                else:
                    # Column count is correct. See if the columns match. If
                    # so, append to the file. If not, throw an exception
                    col_count = len(sorted(self._column_list,
                                           key=self.__get_index))
                    for i in range(col_count):
                        col_name = self._column_list[i].label
                        if col_name != existing_col_headers[i]:
                            err_msg = "Failed to append to existing file "
                            err_msg += f"'{file_name}' - mismatch in column "
                            err_msg += f"titles:{LINE_TERM} New title: "
                            err_msg += f"'{self._column_list[i].label}' "
                            err_msg += f"{LINE_TERM} Existing title: "
                            err_msg += f"'{existing_col_headers[i - 1]}'"
                            raise MultiVuFileException(err_msg)
                        else:
                            self.__have_written_header = True
                    return

            # Make sure we don't add any more columns after this
            self.__have_written_header = True
            return
        # Make sure we don't add any more columns after this
        self.__have_written_header = True

        # Standard header items
        with open(file_name, "a") as f:
            f.write('[Header]\n')
            f.write('; Copyright (c) 2003-2013, Quantum Design, Inc. ')
            f.write('All rights reserved.\n')
            file_time = datetime.now()
            f.write(f"FILEOPENTIME, {file_time.timestamp()}, ")
            f.write(f"{file_time.strftime('%m/%d/%Y, %H:%M:%S %p')}\n")
            f.write('BYAPP, MultiVuDataFile Python class\n')
            f.write(f'TITLE, {title}\n')
            f.write('DATATYPE, COMMENT,1\n')
            f.write('DATATYPE, TIME,2\n')
            time_units_string = ''
            if time_units == TTimeUnits.mv_minutes:
                time_units_string = 'MINUTES'
            else:
                time_units_string = 'SECONDS'
            time_mode_string = ''
            if time_mode == TTimeMode.mv_absolute:
                time_mode_string = 'ABSOLUTE'
            else:
                time_mode_string = 'RELATIVE'
            f.write(f'TIMEMODE, {time_units_string}, {time_mode_string}\n')

        # Generate list of field_groups
        field_groups = []
        for col in self._column_list:
            if col.field_group != '':
                field_groups.append(str(col.field_group))

        # Write out field_groups
        # Columns where the field_group is set are added to their
        # specific field_group
        # Columns where the field_group is not set (blank string) are
        # added to ALL field_groups (they are global)
        with open(file_name, "a") as f:
            for fg in field_groups:
                # Safer to use local variable rather than iteration variable
                # in the conditional test below
                current_field_group = fg
                field_group_col_num = []
                for field_group_col in self._column_list:
                    if (field_group_col.field_group == current_field_group
                            or field_group_col.field_group == ''):
                        field_group_col_num.append(str(field_group_col.index))

                f.write(', '.join(['FIELDGROUP',
                                   current_field_group,
                                   ', '.join(field_group_col_num)]) + '\n')
            f.write('STARTUPGROUP, All\n')

        # Find the first item that wants to be the x axis
        with open(file_name, "a") as f:
            for x_col in sorted(self._column_list, key=self.__get_index):
                startup_axis = (x_col.startup_axis &
                                TStartupAxisType.mv_startup_axis_X)
                if (startup_axis) != 0:
                    write_str = f'STARTUPAXIS, X, {x_col.index}, '
                    write_str += f'{self.__scale_type_str(x_col.scale_type)}, '
                    write_str += 'AUTO\n'
                    f.write(write_str)
                    # We can only have one x column so we bail after
                    # setting the first one (there really shouldn't be more
                    # than one anyway due to our add_column() checks)
                    break

        # Find up to four items that want to be y-axes
        with open(file_name, "a") as f:
            num_Y_axes_found = 0
            for y_col in sorted(self._column_list, key=self.__get_index):
                if (y_col.startup_axis > TStartupAxisType.mv_startup_axis_X):
                    for j in range(1, 5):
                        if (y_col.startup_axis & (1 << j)) != 0:
                            num_Y_axes_found += 1
                            write_str = f'STARTUPAXIS, Y{j}, {y_col.index}, '
                            scale_t = self.__scale_type_str(y_col.scale_type)
                            write_str += f'{scale_t}, AUTO\n'
                            f.write(write_str)
                            if num_Y_axes_found >= 4:
                                # We've got 4 y-axes, so it's time to
                                # stop looking for more
                                break
                    if num_Y_axes_found >= 4:
                        break

        with open(file_name, "a") as f:
            f.write('[Data]\n')

            all_column_headers = []
            for col in sorted(self._column_list, key=self.__get_index):
                all_column_headers.append(f'"{col.label}"')

            # Write out the column headers
            f.write(','.join(all_column_headers) + '\n')

    def __scale_type_str(self, scale_type: TScaleType) -> str:
        '''
        Private method to convert the scale type into a string

        Parameters
        ----------
        scale_type : TScaleType
            TScaleType.mv_linear_scale
            TScaleType.mv_log_scale

        Returns
        -------
        scale_type_str : str

        Example
        -------
        >>> __scale_type_str(TScaleType.mv_linear_scale)

        '''
        scale_type_str = 'LINEAR'
        if scale_type == TScaleType.mv_log_scale:
            scale_type_str = 'LOG'
        return scale_type_str

    def set_value(self, label: str, value: Union[str, int, float]):
        '''
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

        '''
        label_in_list = False
        for item in self._column_list:
            if item.label == label:
                if (label == COMMENT_COL_HEADER) or (type(value) == str):
                    # Sanitize comments by replacing all commas with
                    # semicolons in order not to break the file
                    # structure. Multivu does not handle
                    # commas, even if you put strings in quotes!
                    value = value.replace(',', ';')
                else:
                    value = str(value)

                item.value = value
                item.is_fresh = True
                return
        if not label_in_list:
            err_msg = f"Error writing value '{value}' to "
            err_msg += f"column '{label}'. Column not found."
            raise MultiVuFileException(err_msg)

    def get_value(self, label: str) -> Union[str, int, float]:
        '''
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

        '''
        label_in_list = False
        for item in self._column_list:
            if item.label == label:
                return item.value

        if not label_in_list:
            err_msg = f"Error getting value from column '{label}'. "
            err_msg += "Column not found."
            raise MultiVuFileException(err_msg)

    def get_fresh_status(self, label: str) -> bool:
        '''
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

        '''
        label_in_list = False
        for item in self._column_list:
            if item.label == label:
                return item.is_fresh

        if not label_in_list:
            err_msg = f"Error getting value from column '{label}'."
            err_msg += ' Column not found.'
            raise MultiVuFileException(err_msg)

    def set_fresh_status(self, label: str, status: bool):
        '''
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
        '''
        label_in_list = False
        for item in self._column_list:
            if item.label == label:
                item.is_fresh = status
                label_in_list = True

        if not label_in_list:
            err_msg = f"Error setting value for column '{label}'."
            err_msg += ' Column not found.'
            raise MultiVuFileException(err_msg)

    def write_data(self, get_time_now: bool = True):
        '''
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
        '''
        if not self.__have_written_header:
            err_msg = 'Must write the header file before writing data. '
            err_msg += 'Call the create_file_and_write_header() method first.'
            raise MultiVuFileException(err_msg)

        lock = Lock()
        lock.acquire()
        if get_time_now:
            self.set_value(TIME_COL_HEADER, datetime.now().timestamp())

        # Add data for those columns where there is valid data
        # present and it is (fresh or persistent)
        current_values = []
        for item in sorted(self._column_list, key=self.__get_index):
            if item.value != '' and (item.persistent or item.is_fresh):
                current_values.append(item.value)
            else:
                current_values.append('')

        with open(self.full_path, "a") as f:
            f.write(','.join(current_values))
            f.write('\n')

        # Mark all data as no longer being fresh
        for item in self._column_list:
            item.is_fresh = False
        lock.release()

    def write_data_using_list(self, data_list: list, get_time_now: bool = True):
        '''
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
        '''
        i = 0

        num_entries = len(data_list)

        if (num_entries % 2) != 0:
            err_msg = 'Error in write_data_using_list(). data_list'
            err_msg += f' contains {num_entries} entries. It should'
            err_msg += ' contain an even number of entries'
            raise MultiVuFileException(err_msg)
        for i in range(0, len(data_list), 2):
            self.set_value(data_list[i], data_list[i + 1])
        self.write_data(get_time_now)

    def parse_MVu_data_file(self, file_path: str) -> pd.DataFrame:
        '''
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

        '''
        allLines = []
        # parse the existing headers so that we can verify that we have
        # all the columns we need and set their order to the order in
        # the data file
        in_headers = True
        column_headers = ''
        with open(file_path) as f:
            for raw_line in f:
                line = raw_line.rstrip()
                if in_headers:
                    in_headers = not (line == '[Data]')
                else:
                    if (column_headers == ''):
                        column_headers = line
                    else:
                        data_dict = self.__parse_MVu_data_file_line(
                            line,
                            column_headers
                            )
                        allLines.append(data_dict)
        return pd.DataFrame(allLines)

    def __parse_MVu_data_file_line(self,
                                   line: str,
                                   column_headers: str
                                   ) -> Dict:
        '''
        Parse an individual data line from a MultiVu file into a dictionary
        keyed by the header titles.  A private method.

        Parameters
        ----------
        line : str
            An individual line of data from a MultiVu file.
        column_headers : str
            The column names found in a MultiVu file.

        Raises
        ------
        MultiVuFileException
            The column names and the number of data points mus be equal.

        Returns
        -------
        dict()
            A dictionary of the data.  The key is the column name.

        Example
        -------
        >>> __parse_MVu_data_file_line('"",
                                       1620.012,42',
                                       'Comment,
                                       Time Stamp (sec),
                                       myColumn',
                                       )
        '''
        header_array = self.__parse_CSV_line(column_headers)

        data_array = self.__parse_CSV_line(line)

        if len(data_array) != len(header_array):
            err_msg = 'Error in __parse_MVu_data_file_line(). Line contains'
            err_msg += ' a different number of values than the header.'
            raise MultiVuFileException(err_msg)

        column_dict = dict()
        for i, d in enumerate(data_array):
            try:
                value = float(d)
            except ValueError:
                value = d
            column_dict[header_array[i].replace('"', '')] = value

        return column_dict

    def __parse_CSV_line(self, line: str) -> list:
        '''
        Takes a comma-separated line of data from a MultiVu file and
        converts it to a list

        Parameters
        ----------
        line : str
            comma-separated string of data.

        Raises
        ------
        MultiVuFileException
            The line of data must be in the proper format.

        Returns
        -------
        list
            A list of data found in a line of MultiVu data.

        Example
        -------
        >>> __parse_CSV_line('"",1620348924.0125,42')
        >>> ['',1620348924.0125,42]

        '''
        try:
            return line.split(',')
        except MultiVuFileException:
            err_msg = 'Malformed line in file. Unable to '
            err_msg += f'process: {LINE_TERM} {line}'
            raise MultiVuFileException(err_msg)


class MultiVuFileException(Exception):
    '''
    MultiVu File Exception Error
    '''
    # Constructor or Initializer
    def __init__(self, message):
        self.value = message
        super().__init__(self.value)
