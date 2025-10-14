"""
CommandSdo.py is used to read and write SDOs

@author: djackson
"""

import re
from enum import IntFlag


class val_type(IntFlag):
    short_t = 0x0002    # VT_I2
    int_t = 0x0003      # VT_I4
    single_t = 0x0004   # VT_R4
    double_t = 0x0005   # VT_R8
    string_t = 0x0008   # VT_BSTR
    # bool_t = 0x000B     # VT_BOOL
    # byte_t = 0x0010     # VT_I1 (char)
    # ubyte_t = 0x0011    # VT_UI1
    ushort_t = 0x0012   # VT_UI2
    uint_t = 0x0013     # VT_UI4
    long_t = 0x0014     # VT_I8
    ulong_t = 0x0015    # VT_UI8
    # array_t = 0x2000    # VT_ARRAY
    # byte_array_t = 8208


# note: this can be used to find the type of my_variant given
# the first parameter of win32.VARIANT
# val_type(my_variant.varianttype ^ pythoncom.VT_BYREF).name


class SdoObject():
    """
    This class is used to hold sdo information.  Note that
    it can be represented as a string using str(sdo_object).
    The string can be converted into an sdo_object by calling
    .str_to_obj(string), which is a static method and returns
    an sdo_object.

    Parameters:
    -----------
    nodID: int
        The node number
    sdo_index: int
        This should be represented in hex.  For example, 0x1008.
    sub_index: int
        This should be represented in hex.  For example, 0x0.
    val_t: val_type
        Specify the type.
    """
    def __init__(self,
                 nodeID: int,
                 sdo_index: int,
                 sub_index: int,
                 val_t: val_type):
        if (nodeID > 63) or (nodeID < 0):
            msg = f'Invalid nodeID: {nodeID}'
            raise ValueError(msg)
        if (sdo_index > 0xFFFF) or (sdo_index < 0):
            msg = f'Invalid SDO index: {sdo_index}'
            raise ValueError(msg)
        if (sub_index > 0xFF) or (sub_index < 0):
            msg = f'Invalid SDO subindex: {sub_index}'
            raise ValueError(msg)
        self.node = nodeID
        self.index = sdo_index
        self.sub = sub_index
        self.val_type = val_t

    def __str__(self):
        s = f'node: {self.node}  '
        s += f'index: {hex(self.index)}  '
        s += f'sub_index: {hex(self.sub)}  '
        s += f'type: {self.val_type.name}'
        return s

    @staticmethod
    def str_to_obj(sdo_as_string: str):
        """
        Static method used to convert a string representation of
        an sdo_object into an sdo_object.

        Parameters:
        -----------
        sdo_as_string: str
            The string representation of an sdo_object.  This
            can be created using str(sdo_object).

        Returns:
        --------
        An sdo_object

        Raises:
        -------
        ValueError if the string is not formatted correctly
        """
        sdo_search = r'node: ([0-9]{1,2})  '
        sdo_search += r'index: (0x[0-9abcdefABCDEF]{1,4})  '
        sdo_search += r'sub_index: (0x[0-9abcdefABCDEF]{1,4})  '
        sdo_search += r'type: ([_a-zA-Z]*)'
        try:
            [sdo_found] = re.findall(sdo_search, sdo_as_string)
        except ValueError:
            msg = f'unrecognized input string:  {sdo_as_string}'
            raise ValueError(msg)
        node, index, sub_index, t = sdo_found
        n = int(node)
        i = int(index, 16)
        s = int(sub_index, 16)
        v_t = val_type[t]
        return SdoObject(n, i, s, v_t)

    def object_length(self) -> int:
        """
        Get the byte size
        """
        if self.val_type is val_type.short_t:
            return 1
        elif self.val_type is val_type.int_t:
            return 2
        elif self.val_type is val_type.single_t:
            return 2
        elif self.val_type is val_type.string_t:
            return 1
        elif self.val_type is val_type.ushort_t:
            return 1
        elif self.val_type is val_type.uint_t:
            return 2
        elif self.val_type is val_type.double_t:
            return 4
        elif self.val_type is val_type.long_t:
            return 4
        elif self.val_type is val_type.ulong_t:
            return 4
        else:
            raise ValueError('Unimplemented SDO type')
