# -*- coding: utf-8 -*-
"""
ParseInputs.py contains the Input class, which is a tool to parse the
command-line inputs

"""

import ntpath
import re
import sys
from typing import List

from .instrument import InstrumentList
from .project_vars import HOST_SERVER, PORT


class ParsedInputs():
    """
    This holds the information contained in command line inputs to MultiPyVu.
    Converting this class into a string will result in showing the command
    line arguments.
    """
    instrument_str = ''
    scaffolding_mode = False
    host = ''
    port = 0
    verbose = False

    def __init__(self,
                 instrument_str: str = '',
                 scaffolding_mode: bool = False,
                 host: str = HOST_SERVER,
                 port: int = PORT,
                 verbose: bool = False,
                 ):
        self.instrument_str = instrument_str
        self.scaffolding_mode = scaffolding_mode
        self.host = host
        self.port = port
        self.verbose = verbose
        self.get_host_ip = False
        self.status = False
        self.running = False
        self.quit = False

    def __str__(self):
        parsed_str = f'--ip={self.host} --port={self.port}'
        parsed_str += ' -v' if self.verbose else ''
        parsed_str += ' -s' if self.scaffolding_mode else ''
        parsed_str += self.instrument_str
        return parsed_str


def path_leaf(path):
    """
    Used to split a path up to get the path to a filename.

    Parameters
    ----------
    path : str
        The path and file location.

    Returns
    -------
    str
        Path to file.

    """
    head, tail = ntpath.split(path)
    return tail or ntpath.basename(head)


def inputs_from_command_line(flags: List[str]) -> ParsedInputs:
    """
    Interprets the lit of command line arguments.

    Parameters:
    -----------
    flags : [str]
        Input flags such as -h or -s and PPMS flavor.

    Returns:
    --------
    ParsedInputs class
    """
    return parse_input(flags)


def parse_input(input_args_list: List[str]) -> ParsedInputs:
    """
    Parses the input_args_list text

    Parameters:
    -----------
    input_args_list : list
            Arguments flags are:
        -h(elp) to display the help text
        -s for scaffolding in order to simulate the script
        -ip=<host address> to specify the host IP
            address (default = '0.0.0.0' which accepts all incoming
            connections)
        -p(ort)=.port number. to specify the port (default is 5000)
        -v(erbose) to turn on the verbose text when the server
            sends/receives info
        -get_ip
        -status to get the server status
        -running to see if the server is running
        -q(uit) to force quit the server

        An argument without a flag is the instrument.

    Returns:
    --------
    dict
        ParsedInputs class with attributes: 'instrument_str',
        'scaffolding_mode', 'host', 'port', 'verbose'.

    Exceptions:
    -----------
    A UserWarning exception is thrown if displaying the help text. This
    can also be thrown if the instrument name does not match a valid
    MultiVu flavor (or if the flag is unknown).
    """
    parsed_inputs = dict()
    # convert the input_args_list into a string.
    input_args = ' '.join(input_args_list)

    # reg-ex for finding flags in the input
    # help: -h
    help_args = re.compile(r'-[-]?(h(elp)?)', re.IGNORECASE)
    # scaffolding: -s
    sim_args = re.compile(r'-[-]?(s)(?:\s|$)', re.IGNORECASE)
    # verbose: -v
    verbose_args = re.compile(r'-[-]?(v)', re.IGNORECASE)
    # ip address: -ip=
    ip_re = r'-[-]?(ip)[=]?(\d{1,3}.\d{1,3}.\d{1,3}.\d{1,3}|localhost)'
    ip_args = re.compile(ip_re, re.IGNORECASE)
    # port number: -p=
    p_re = r'-[-]?(p|(?:port)?)[=](\d{4,5}){1}[ |\n]?'
    port_args = re.compile(p_re, re.IGNORECASE)
    # instrument name: <just type the name!
    instrument_re = r'\w*(?<!-|[a-zA-Z])([a-zA-Z]+3?)'
    instrument_args = re.compile(instrument_re, re.IGNORECASE)
    # get computer's IP address:
    get_ip_args = re.compile(r'-(get_ip)', re.IGNORECASE)
    # server status: -status
    status_args = re.compile(r'-(status)', re.IGNORECASE)
    # is server running?: -running
    running_args = re.compile(r'-(running)', re.IGNORECASE)
    # force quit server: -q
    quit_args = re.compile(r'-[-]?(q(uit)?)')

    parsed_inputs = ParsedInputs()

    show_help = True
    additional_help_info = f'{input_args} is not a valid flag.'

    if input_args == '':
        return parsed_inputs

    # check for help string
    if help_args.search(input_args):
        additional_help_info = ''
    if sim_args.search(input_args):
        parsed_inputs.scaffolding_mode = True
        show_help = False
    if verbose_args.search(input_args):
        parsed_inputs.verbose = True
        show_help = False
    if ip_args.search(input_args):
        _, parsed_inputs.host = ip_args.findall(input_args)[0]
        show_help = False
    if port_args.search(input_args):
        _, parsed_inputs.port = port_args.findall(input_args)[0]
        # cast the string as an integer
        try:
            parsed_inputs.port = int(parsed_inputs.port)
            show_help = False
        except ValueError:
            additional_help_info = 'The specified port must be '
            additional_help_info += 'an integer (received '
            additional_help_info += f'"{parsed_inputs.port})"'
    if instrument_args.search(input_args):
        instrument_list = instrument_args.findall(input_args)
        if len(instrument_list) > 1:
            additional_help_info = 'Can only accept one instrument. '
            additional_help_info += f'Found {instrument_list}'
        else:
            instrument_str = instrument_list[0]
            # Check to see if the input is a valid instrument_str
            if (instrument_str.upper() not in InstrumentList._member_names_
                    or instrument_str == InstrumentList.na):
                additional_help_info = 'The specified instrument,'
                additional_help_info += f'"{instrument_str}", is not '
                additional_help_info += 'a valid MultiVu flavor.  See '
                additional_help_info += 'the above help for information.'
            else:
                show_help = False
                parsed_inputs.instrument_str = instrument_str
    if get_ip_args.search(input_args):
        show_help = False
        parsed_inputs.get_host_ip = True
    if status_args.search(input_args):
        show_help = False
        parsed_inputs.status = True
    if running_args.search(input_args):
        show_help = False
        parsed_inputs.running = True
    if quit_args.search(input_args):
        show_help = False
        parsed_inputs.quit = True

    if show_help:
        msg = help_text(additional_help_info)
        raise UserWarning(msg)

    return parsed_inputs


def help_text(additional_help_info='') -> str:
    """
    Returns a string containing help information about the module.
    """
    program_name = path_leaf(sys.argv[0])
    if program_name == '__main__.py':
        program_name = '-m MultiPyVu'
    help_text = f"""
INPUT OPTIONS:
To display this help text:
    $ python {program_name} -h
To run the scaffolding (python is simulating MultiVu)
and test the server (must also specify the MultiVu flavor):
    $ python {program_name} -s
To specify the host IP address (default = '0.0.0.0'):
    $ python {program_name} -ip=<host IP address>
To specify the port (default = 5000):
    $ python {program_name} -p=<port number>
    Note that non-privileged ports are 1023 < 65535
To run in verbose mode and have the server print to the
command line all of the data it sends/receives:
    $ python {program_name} -v

There are also a few commands that can be run from the module
level, python -m:
To run the gui:
    $ python -m MultiPyVu
For help:
    $ python -m MultiPyVu -h
To get the computer's IP address:
    $ python -m MultiPyVu -get_ip
To see if the server is running:
    $ python -m MultiPyVu -running
To get the server status:
    $ python -m MultiPyVu -status
To force quit the server:
    $ python -m MultiPyVu -quit
Note that the IP address and port can be specified using the -ip=
and -p= commands as described above.

MultiVu must be running before starting the server.  Usually
MultiVu.Server will figure out which MultiVu flavor to run
and the specific flavor does not need to be specified.  However,
if the flavor must be specified, then use one of the following
options:"""

    for i in InstrumentList.__members__.values():
        if i.name != InstrumentList.na.name:
            instr_name = i.name.capitalize()
            help_text += f'\n\t$ python {program_name} {instr_name}'

    help_text += """

Once the server is started, a python script can control the cryostat
by using MultiPyVu.Client.
"""

    if additional_help_info != '':
        help_text += '\n\n------------------------------------------\n\n'
        help_text += additional_help_info
    return help_text
