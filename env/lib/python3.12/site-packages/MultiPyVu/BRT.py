"""
BRT.py is an abstraction of the BRT module.
"""

import time
from typing import Tuple

from .sdo_object import SdoObject, val_type


class Brt():
    def __init__(self, client):
        """
        Container for BRT module temperature and resistance

        Parameters:
        -----------
        client: MultiPyVu.Client object
        """
        self.client = client
        self.stabilize_time = 5

    def _make_bridge_number_error(self, bridge_number: int) -> str:
        """
        This creates a simple error message saying that the
        selected bridge number is out of range

        Arguments:
            bridge_number

        Returns:
            error message
        """
        msg = 'bridge_number must be 1, 2, or 3 '
        # Note that python version 3.7 does not allow formatting
        # strings using {bridge_number = }
        msg += f'(bridge_number = {bridge_number})'
        return msg

    def bridge_setup(self,
                     bridge_number: int,
                     channel_on: bool,
                     current_limit_uA: float,
                     power_limit_uW: float,
                     voltage_limit_mV: float,
                     ) -> None:
        """
        Set the resistance option bridge settings.

        Parameters:
        -----------
        bridge_number: int
        channel_on: bool
            True turns on the bridge
        current_limit_uA: float
        power_limit_uW: float
        voltage_limi_mV: float
        """
        self.channel_on(bridge_number, channel_on)
        self.current_limit(bridge_number, current_limit_uA)
        self.power_limit(bridge_number, power_limit_uW)
        self.voltage_limit(bridge_number, voltage_limit_mV)
        # turn off constant current mode
        self._constant_current(bridge_number, False)

    def channel_on(self, bridge_number: int, enable: bool) -> None:
        """
        Enable the bridge for the BRT module.  This command works
        directly with the module rather than using MultiVu.

        Parameters:
        -----------
        bridge_number: int
            Indicate the bridge number to read.  This must be 1, 2, or 3.
        enable: bool
            Enable the channel (True)

        Returns:
        --------
        None.

        Raises:
        -------
        ValueError
            - Returned if bridge_number is out of bounds
        """
        enable_sdo = {}
        enable_sdo[1] = SdoObject(21, 0x6001, 0x3, val_type.ushort_t)
        enable_sdo[2] = SdoObject(21, 0x6002, 0x3, val_type.ushort_t)
        enable_sdo[3] = SdoObject(21, 0x6003, 0x3, val_type.ushort_t)

        sdo = enable_sdo.get(bridge_number, None)
        if sdo is None:
            raise ValueError(self._make_bridge_number_error(bridge_number))
        self.client._set_sdo(sdo, int(enable))
        # Pause to let the SDO go through.  The pause time is
        # somewhat arbitrary.
        time.sleep(self.stabilize_time)

    def _constant_current(self,
                          bridge_number: int,
                          const_current: bool
                          ) -> None:
        """
        Configure the bridge for constant current mode.  This command works
        directly with the module rather than using MultiVu.

        Parameters:
        -----------
        bridge_number: int
            Indicate the bridge number to read.  This must be 1, 2, or 3.
        const_current: bool
            Constant current mode (True)
            Use limits (False)

        Returns:
        --------
        None.

        Raises:
        -------
        ValueError
            - Returned if bridge_number is out of bounds
        """
        const_current_sdo = {}
        const_current_sdo[1] = SdoObject(21, 0x6001, 0x4, val_type.ushort_t)
        const_current_sdo[2] = SdoObject(21, 0x6002, 0x4, val_type.ushort_t)
        const_current_sdo[3] = SdoObject(21, 0x6003, 0x4, val_type.ushort_t)

        sdo = const_current_sdo.get(bridge_number, None)
        if sdo is None:
            raise ValueError(self._make_bridge_number_error(bridge_number))
        self.client._set_sdo(sdo, int(const_current))
        for timeout in range(0, 4):
            time.sleep(0.6)
            bridge_setting = self.client._get_sdo(sdo)
            if bool(bridge_setting) and const_current:
                break

    def get_resistance(self, bridge_number: int) -> Tuple[float, str]:
        """
        This is used to get the resistance from the BRT module.  This
        command gets it's value directly from the module rather than
        reading the value from MultiVu.

        Parameters:
        -----------
        bridge_number: int
            Indicate the bridge number to read.  This must be 1, 2, or 3.

        Returns:
        --------
        A tuple of (resistance, read_status).

        Raises:
        -------
        ValueError
            Returned if bridge_number is out of bounds
        """
        resistance = {}
        resistance[1] = SdoObject(21, 0x6001, 0x1, val_type.double_t)
        resistance[2] = SdoObject(21, 0x6002, 0x1, val_type.double_t)
        resistance[3] = SdoObject(21, 0x6003, 0x1, val_type.double_t)

        sdo = resistance.get(bridge_number, None)
        if sdo is None:
            raise ValueError(self._make_bridge_number_error(bridge_number))
        res, status = self.client._get_sdo(sdo)
        return float(res), status

    def get_current(self, bridge_number: int) -> Tuple[float, str]:
        """
        This is used to get the current from the BRT module.  This
        command gets it's value directly from the module rather than
        reading the value from MultiVu.

        Parameters:
        -----------
        bridge_number: int
            Indicate the bridge number to read.  This must be 1, 2, or 3.

        Returns:
        --------
        A tuple of (current, read_status).

        Raises:
        -------
        ValueError
            Returned if bridge_number is out of bounds
        """
        current = {}
        current[1] = SdoObject(21, 0x6001, 0x2, val_type.double_t)
        current[2] = SdoObject(21, 0x6002, 0x2, val_type.double_t)
        current[3] = SdoObject(21, 0x6003, 0x2, val_type.double_t)

        sdo = current.get(bridge_number, None)
        if sdo is None:
            raise ValueError(self._make_bridge_number_error(bridge_number))
        res, status = self.client._get_sdo(sdo)
        return float(res), status

    def set_current(self, bridge_number: int, current_uA: float) -> None:
        """
        This is used to set the current, in uA, for the BRT module.  This
        command works directly with the module rather than using MultiVu.

        Parameters:
        -----------
        bridge_number: int
            Indicate the bridge number to read.  This must be 1, 2, or 3.
        current_uA: float
            The desired current, in microAmps

        Returns:
        --------
        None.

        Raises:
        -------
        ValueError
            - Returned if bridge_number is out of bounds
            - Returned if the current is out of bounds
        """
        _upper_limit = 8000.0
        _lower_limit = 0.010
        if (current_uA < _lower_limit) or (current_uA > _upper_limit):
            msg = f'current out of bounds.  Must be between {_lower_limit} uA '
            msg += f'and {_upper_limit} uA.  Entered {current_uA}'
            raise ValueError(msg)

        current_sdo = {}
        current_sdo[1] = SdoObject(21, 0x6001, 0x5, val_type.double_t)
        current_sdo[2] = SdoObject(21, 0x6002, 0x5, val_type.double_t)
        current_sdo[3] = SdoObject(21, 0x6003, 0x5, val_type.double_t)

        sdo = current_sdo.get(bridge_number, None)
        if sdo is None:
            raise ValueError(self._make_bridge_number_error(bridge_number))
        self.client._set_sdo(sdo, current_uA)
        # Put in constant current mode
        self._constant_current(bridge_number, True)

    def current_limit(self, bridge_number: int, current_uA: float) -> None:
        """
        This is used to set the current limit, in uA, for the bridge.  This
        command works directly with the module rather than using MultiVu.

        Parameters:
        -----------
        bridge_number: int
            Indicate the bridge number to read.  This must be 1, 2, or 3.
        current_uA: float
            The desired current limit, in microAmps

        Returns:
        --------
        None.

        Raises:
        -------
        ValueError
            - Returned if bridge_number is out of bounds
            - Returned if the current is out of bounds
        """
        _upper_limit = 8000.0
        _lower_limit = 0.010
        if (current_uA < _lower_limit) or (current_uA > _upper_limit):
            msg = 'current limit out of bounds.  Must be between '
            msg += f'{_lower_limit} uA and {_upper_limit} uA.  '
            msg += f'Entered {current_uA}'
            raise ValueError(msg)

        current_sdo = {}
        current_sdo[1] = SdoObject(21, 0x6001, 0x6, val_type.double_t)
        current_sdo[2] = SdoObject(21, 0x6002, 0x6, val_type.double_t)
        current_sdo[3] = SdoObject(21, 0x6003, 0x6, val_type.double_t)

        sdo = current_sdo.get(bridge_number, None)
        if sdo is None:
            raise ValueError(self._make_bridge_number_error(bridge_number))
        self.client._set_sdo(sdo, current_uA)

    def power_limit(self, bridge_number: int, power_uW: float) -> None:
        """
        This is used to set the power limit, in uW, for the bridge.  This
        command works directly with the module rather than using MultiVu.

        Parameters:
        -----------
        bridge_number: int
            Indicate the bridge number to read.  This must be 1, 2, or 3.
        power_uW: float
            The desired power limit, in microWatts

        Returns:
        --------
        None.

        Raises:
        -------
        ValueError
            - Returned if bridge_number is out of bounds
            - Returned if the current is out of bounds
        """
        _upper_limit = 1000.0
        _lower_limit = 0.001
        if (power_uW < _lower_limit) or (power_uW > _upper_limit):
            msg = 'current limit out of bounds.  Must be between '
            msg += f'{_lower_limit} uA and {_upper_limit} uA.  '
            msg += f'Entered {power_uW}'
            raise ValueError(msg)

        current_sdo = {}
        current_sdo[1] = SdoObject(21, 0x6001, 0x7, val_type.double_t)
        current_sdo[2] = SdoObject(21, 0x6002, 0x7, val_type.double_t)
        current_sdo[3] = SdoObject(21, 0x6003, 0x7, val_type.double_t)

        sdo = current_sdo.get(bridge_number, None)
        if sdo is None:
            raise ValueError(self._make_bridge_number_error(bridge_number))
        self.client._set_sdo(sdo, power_uW)

    def voltage_limit(self, bridge_number: int, voltage_mV: float) -> None:
        """
        This is used to set the voltage limit, in mV, for the bridge.  This
        command works directly with the module rather than using MultiVu.

        Parameters:
        -----------
        bridge_number: int
            Indicate the bridge number to read.  This must be 1, 2, or 3.
        voltage_mV: float
            The desired voltage limit, in mV.

        Returns:
        --------
        None.

        Raises:
        -------
        ValueError
            - Returned if bridge_number is out of bounds
            - Returned if the current is out of bounds
        """
        _upper_limit = 4000.0
        _lower_limit = 1.0
        if (voltage_mV < _lower_limit) or (voltage_mV > _upper_limit):
            msg = 'current limit out of bounds.  Must be between '
            msg += f'{_lower_limit} uA and {_upper_limit} uA.  '
            msg += f'Entered {voltage_mV}'
            raise ValueError(msg)

        current_sdo = {}
        current_sdo[1] = SdoObject(21, 0x6001, 0x8, val_type.double_t)
        current_sdo[2] = SdoObject(21, 0x6002, 0x8, val_type.double_t)
        current_sdo[3] = SdoObject(21, 0x6003, 0x8, val_type.double_t)

        sdo = current_sdo.get(bridge_number, None)
        if sdo is None:
            raise ValueError(self._make_bridge_number_error(bridge_number))
        self.client._set_sdo(sdo, voltage_mV)

    # This works, but is not used for the resistivity option, so currently commented out
    # def get_temperature(self) -> Tuple[float, str]:
    #     """
    #     This is used to get the temperature, in Kelvin, from the
    #     BRT.  This command gets it's value directly from
    #     the module rather than reading the value from MultiVu.

    #     Returns:
    #     --------
    #     A tuple of (temperature, read_status).
    #     """
    #     channel_4_temperature = SdoObject(21, 0x6030, 0x1, val_type.double_t)
    #     temperature, status = self.client._get_sdo(channel_4_temperature)
    #     return float(temperature), status
