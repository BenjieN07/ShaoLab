#!/usr/bin/env python3
"""
This allows people to start the MultiPyVu Server gui using
the -m flag and the module name.

> python -m MultiPyVu

One can run this in scaffolding mode by adding adding flags
when calling this script.

For example:
> python -m MultiPyVu -s opticool

@author: djackson
"""

from sys import argv

from MultiPyVu.gui.Controller import Controller
from MultiPyVu.ParseInputs import parse_input
from MultiPyVu.scripts.helper_scripts import (get_ip,
                                              run_status,
                                              is_running,
                                              force_quit)


def run_gui():
    # capture command-line arguments
    gui = Controller(argv[1:])
    gui.start_gui()


if __name__ == '__main__':
    try:
        inputs = parse_input(argv[1:])
    except UserWarning as e:
        print(str(e))
    else:
        if inputs.status:
            run_status(inputs.host, inputs.port)
        elif inputs.running:
            is_running(inputs.host, inputs.port)
        elif inputs.quit:
            print(force_quit(inputs.host, inputs.port))
        elif inputs.get_host_ip:
            print(f"This computer's IP address:  {get_ip()}")
        else:
            run_gui()
