"""
A few helpful scripts used in the MultiPyVu module
"""

import re
import subprocess
from os import path
from sys import platform

from MultiPyVu.MultiVuClient import Client


def absolute_path(filename: str) -> str:
    """
    Finds the absolute path of a file based on its location
    relative to the gui module

    Parameters:
    -----------
    filename: str
        The file location based on its relative path from the gui module
    """
    abs_path = path.abspath(
        path.join(path.dirname(
            __file__), './'))
    return path.join(abs_path, filename)


def get_ip():
    """
    The IP address for the computer

    Returns:
    --------
    String with the IP address
    """
    ip_output_str = ''
    search_str = r'([0-9]{1,3}.[0-9]{1,3}.[0-9]{1,3}.[0-9]{1,3})'
    if platform == 'win32':
        ip_addr_script = 'whats_my_ip_address.cmd'
        ip_addr_script = absolute_path(ip_addr_script)
        proc = subprocess.run([ip_addr_script],
                              capture_output=True,
                              text=True)
        if proc.returncode != 0:
            print(proc.stderr)
            raise Exception(proc.stderr)
        ip_result = re.findall(search_str, proc.stdout)
        if len(ip_result) == 1:
            ip_address = ip_result[0]
    else:
        # using this suggestion:
        # https://apple.stackexchange.com/questions/20547/how-do-i-find-my-ip-address-from-the-command-line
        ifconfig_proc = subprocess.Popen(["ifconfig"],
                                         stdout=subprocess.PIPE,
                                         text=True)
        grep_proc = subprocess.Popen(["grep", "inet"],
                                     stdin=ifconfig_proc.stdout,
                                     stdout=subprocess.PIPE,
                                     text=True)
        ip_output_str, err = grep_proc.communicate()
        if err is not None:
            print(err)
            raise Exception(grep_proc.stderr)
        ip_result = re.findall(search_str, ip_output_str)
        if '127.0.0.1' in ip_result:
            ip_result.remove('127.0.0.1')
        if len(ip_result) >= 1:
            ip_address = ip_result[0]
    return ip_address


def run_status(ip: str, port: int):
    """
    Queries the server for its status.
    """
    ip_address = ip
    if ip_address == '0.0.0.0':
        ip_address = 'localhost'

    client = Client(host=ip_address,
                    port=port)
    response = client.get_server_status()
    print(f'Server status: {response}')


def is_running(ip: str, port: int):
    """
    Queries the server to see if it is running
    """
    ip_address = ip
    if ip_address == '0.0.0.0':
        ip_address = 'localhost'

    client = Client(host=ip_address,
                    port=port)
    response = client.is_server_running()
    if response:
        print(f'Server is running at {client.address}')
    else:
        print(f'Server not running at {client.address}')


def force_quit(ip: str, port: int) -> str:
    """
    Quits the server.
    """
    ip_address = ip
    if ip_address == '0.0.0.0':
        ip_address = 'localhost'

    client = Client(host=ip_address,
                    port=port)
    response = client.force_quit_server()
    if response:
        return response
    else:
        return f'Sent quit command to {client.address}'
