"""
Command_factory.py is used to instantiate the 'real' or
simulated ICommand classes.
"""

from typing import Union

from . import CommandChamber as chamber
from . import CommandField as field
from . import CommandFieldSetPoints as field_setpoints
from . import CommandRotator as rotator
from . import CommandSdo as sdo
from . import CommandTemperature as temperature
from . import CommandTempSetPoints as temp_setpoints
from . import CommandWaitFor as wait_for
from .CommandMultiVu import CommandMultiVuImp, CommandMultiVuSim


def create_command_mv(mvu_flavor,
                      win32_dispatch=None,
                      ):
    """
    Create a CommandMultiVu Object

    Parameters:
    -----------
    mvu_flavor: str
        The name of the MultiVu flavor
    win32_dispatch (optional): win32com.client.CDispatch or None
        This is the object used to communicate with MultiVu.
        Default is None, which will load CommandMultiVuSim

    Returns:
    --------
    A CommandMultiVu object.  If win32_dispatch is None, it returns
    a simulated object.
    """
    cmd_dict = {'TEMP': create_command_temp(mvu_flavor, win32_dispatch),
                'TEMP_SETPOINTS': create_command_temp_setpoints(mvu_flavor,
                                                                win32_dispatch),
                'FIELD_SETPOINTS': create_command_field_setpoints(mvu_flavor,
                                                                  win32_dispatch),
                'FIELD': create_command_field(mvu_flavor, win32_dispatch),
                'CHAMBER': create_command_chamber(mvu_flavor, win32_dispatch),
                'SDO': create_command_sdo(win32_dispatch),
                'WAITFOR': create_command_wait_for(mvu_flavor, win32_dispatch),
                'POSITION': create_command_position(mvu_flavor, win32_dispatch),
                }
    if win32_dispatch:
        return CommandMultiVuImp(cmd_dict)
    else:
        return CommandMultiVuSim(cmd_dict)


def create_command_temp(
        mvu_flavor: str = '',
        win32_dispatch=None,
        ) -> Union[temperature.CommandTemperatureSim,
                   temperature.CommandTemperatureImp]:
    """
    Create a CommandTemperature object

    Parameters:
    -----------
    mvu_flavor: str
        The name of the MultiVu flavor (the instrument name)
    win32_dispatch (optional): win32com.client.CDispatch or None
        This is the object used to communicate with MultiVu.
        Default is None, which will load CommandTemperatureSim

    Returns:
    --------
    CommandTemperature object
    """
    if win32_dispatch:
        return temperature.CommandTemperatureImp(win32_dispatch, mvu_flavor)
    else:
        return temperature.CommandTemperatureSim()


def create_command_temp_setpoints(
        mvu_flavor: str = '',
        win32_dispatch=None,
        ) -> Union[temp_setpoints.CommandTempSetpointsSim,
                   temp_setpoints.CommandTempSetpointsImp]:
    """
    Create a CommandTempSetPoints object

    Parameters:
    -----------
    mvu_flavor: str
        The name of the MultiVu flavor (the instrument name)
    win32_dispatch (optional): win32com.client.CDispatch or None
        This is the object used to communicate with MultiVu.
        Default is None, which will load CommandTemperatureSim

    Returns:
    --------
    CommandTemperature object
    """
    if win32_dispatch:
        return temp_setpoints.CommandTempSetpointsImp(mvu_flavor, win32_dispatch)
    else:
        return temp_setpoints.CommandTempSetpointsSim()


def create_command_field(
        mvu_flavor: str = '',
        win32_dispatch=None,
        ) -> Union[field.CommandFieldSim,
                   field.CommandFieldImp]:
    """
    Create a CommandField object

    Parameters:
    -----------
    mvu_flavor: str
        The name of the MultiVu flavor (the instrument name)
    win32_dispatch (optional): win32com.client.CDispatch or None
        This is the object used to communicate with MultiVu.
        Default is None, which will load CommandFieldSim

    Returns:
    --------
    CommandField object
    """
    if win32_dispatch:
        return field.CommandFieldImp(win32_dispatch, mvu_flavor)
    else:
        return field.CommandFieldSim(mvu_flavor)


def create_command_field_setpoints(
        mvu_flavor: str = '',
        win32_dispatch=None,
        ) -> Union[field_setpoints.CommandFieldSetPointsSim,
                   field_setpoints.CommandFieldSetPointsImp]:
    """
    Create a CommandFieldSetPoints object

    Parameters:
    -----------
    mvu_flavor: str
        The name of the MultiVu flavor (the instrument name)
    win32_dispatch (optional): win32com.client.CDispatch or None
        This is the object used to communicate with MultiVu.
        Default is None, which will load CommandTemperatureSim

    Returns:
    --------
    CommandTemperature object
    """
    if win32_dispatch:
        return field_setpoints.CommandFieldSetPointsImp(mvu_flavor, win32_dispatch)
    else:
        return field_setpoints.CommandFieldSetPointsSim(mvu_flavor)


def create_command_chamber(
        mvu_flavor: str = '',
        win32_dispatch=None,
        ) -> Union[chamber.CommandChamberSim,
                   chamber.CommandChamberImp]:
    """
    Create a CommandChamber object

    Parameters:
    -----------
    mvu_flavor: str
        The name of the MultiVu flavor (the instrument name)
    win32_dispatch (optional): win32com.client.CDispatch or None
        This is the object used to communicate with MultiVu.
        Default is None, which will load CommandChamberSim

    Returns:
    --------
    CommandChamber object
    """
    if win32_dispatch:
        return chamber.CommandChamberImp(win32_dispatch, mvu_flavor)
    else:
        return chamber.CommandChamberSim(mvu_flavor)


def create_command_sdo(
        win32_dispatch=None
        ) -> Union[sdo.CommandSdoSim,
                   sdo.CommandSdoImp]:
    """
    Create a CommandSdo object

    Parameters:
    -----------
    win32_dispatch (optional): win32com.client.CDispatch or None
        This is the object used to communicate with MultiVu.
        Default is None, which will load CommandSdoSim

    Returns:
    --------
    CommandSdo object
    """
    if win32_dispatch:
        return sdo.CommandSdoImp(win32_dispatch)
    else:
        return sdo.CommandSdoSim()


def create_command_wait_for(
        mvu_flavor,
        win32_dispatch=None,
        ) -> Union[wait_for.CommandWaitForSim,
                   wait_for.CommandWaitForImp]:
    """
    Create a CommandWaitFor object

    Parameters:
    -----------
    mvu_flavor: str
        The name of the MultiVu flavor (the instrument name)
    win32_dispatch (optional): win32com.client.CDispatch or None
        This is the object used to communicate with MultiVu.
        Default is None, which will load CommandWaitForSim

    Returns:
    --------
    CommandWaitFor object
    """
    if win32_dispatch:
        icmd_t = temperature.CommandTemperatureImp(win32_dispatch, mvu_flavor)
        icmd_h = field.CommandFieldImp(win32_dispatch,  mvu_flavor)
        icmd_c = chamber.CommandChamberImp(win32_dispatch, mvu_flavor)
        return wait_for.CommandWaitForImp(win32_dispatch,
                                          mvu_flavor,
                                          icmd_t,
                                          icmd_h,
                                          icmd_c,
                                          )
    else:
        return wait_for.CommandWaitForSim(mvu_flavor,
                                          temperature.SimulateTemperatureChange(),
                                          field.SimulateFieldChange(),
                                          chamber.SimulateChamberChange()
                                          )


def create_command_position(
        mvu_flavor: str = '',
        win32_dispatch=None,
        ) -> Union[rotator.CommandRotatorImp,
                   rotator.CommandRotatorSim]:
    """
    Create a CommandRotator object

    Parameters:
    -----------
    mvu_flavor: str
        The name of the MultiVu flavor (the instrument name)
    win32_dispatch (optional): win32com.client.CDispatch or None
        This is the object used to communicate with MultiVu.
        Default is None, which will load CommandRotatorSim

    Returns:
    --------
    CommandRotator object
    """
    if win32_dispatch:
        return rotator.CommandRotatorImp(win32_dispatch, mvu_flavor)
    else:
        return rotator.CommandRotatorSim(mvu_flavor)
