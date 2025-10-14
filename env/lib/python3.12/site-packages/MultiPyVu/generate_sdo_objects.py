#!/usr/bin/env python3
"""
This script is used to generate sdo_objects from reading a
cop file.

The script can either import a cop file by adding the path
as an argument when calling the script, or the script will
ask for the path to a file.  The python file will be saved
in the same location as the cop file and will have the same
name with the .py ending.
"""

import os.path
import re
from sys import argv, exit

from MultiPyVu.CommandSdo import SdoObject, val_type


if len(argv) > 1:
    cop_file = argv[1]
else:
    cop_file = input('Enter the path to the cop file:  ')

if not os.path.basename(cop_file).endswith('.cop'):
    msg = 'FAILED:  Wrong file type (must be a .cop file):  '
    msg += cop_file
    print(msg)
    exit(0)

if not os.path.exists(cop_file):
    print('FAILED:  File does not exist:  {cop_file}')
    exit(0)

# define the reg-ex search string
sdo_search = r'^(?:True|False),'                # enabled
sdo_search += r'([0-9]{1,2})?,'                 # node
sdo_search += r'([ \w\d]*),'                    # name
sdo_search += r'(0x[0-9abcdefABCDEF]{1,4})?,'   # index
sdo_search += r'(0x[0-9abcdefABCDEF]{1,4})?,'   # subindex
sdo_search += r'([-\w0-9]*)?,'                  # type
sdo_search += r'[0]?,'                          # byte offset
sdo_search += r'(RO|RW|WO)?'                    # read/write

sdo_dict = {}
with open(cop_file, 'r') as cop:
    for line in cop:
        sdo = re.findall(sdo_search, line)
        if len(sdo) == 0:
            continue
        if len(sdo[0]) == 6:
            node, name, index, sub_index, t, rw = sdo[0]
            if node == '' and index == '' and sub_index == '' and \
                        t == '' and rw == '':
                sdo_dict[name] = None
                continue
            n = int(node)
            i = int(index, 16)
            s = int(sub_index, 16)
            # translate the type
            if t == 'Signed-8':
                v_t = val_type.short_t
            elif t == 'Unsigned-8':
                v_t = val_type.ushort_t
            elif t == 'Signed-16':
                v_t = val_type.int_t
            elif t == 'Unsigned-16':
                v_t = val_type.uint_t
            elif t == 'Signed-32':
                v_t = val_type.long_t
            elif t == 'Unsigned-32':
                v_t = val_type.ulong_t
            elif t == 'Float-32':
                v_t = val_type.double_t
            elif t == 'String':
                v_t = val_type.string_t
            else:
                raise ValueError(f'Type not implemented ({t})')
            name = name.lower().replace(' ', '_')
            if name not in sdo_dict:
                sdo_dict[name] = SdoObject(n, i, s, v_t)
            else:
                msg = 'Duplicate SDO name:  \n'
                msg += f'{name}\n'
                msg += f'{n = }, {i = }, {s = }, {v_t = }'
                print(msg)

# create the python file name
[sdo_file, _] = cop_file.split('.')
sdo_file += '.py'
exists = os.path.exists(sdo_file)
while exists:
    msg = f'The file, {sdo_file} exists or is invalid.  Enter a '
    msg += 'new name (leave blank to cancel).'
    print(msg)
    sdo_file = input('New name:    ')
    if sdo_file == '':
        print('cancelling')
        exit(0)
    elif not os.path.basename(sdo_file).endswith('.py'):
        msg = 'File name must end with ".py"'
        continue
    elif os.path.exists(sdo_file):
        continue
    else:
        break

# write the file
with open(sdo_file, 'w') as s_file:
    s_file.write(f""""\nSDO Dictionary generated using {cop_file}\n\n"""")
    s_file.write('\nfrom MultiPyVu.sdo_object import SdoObject, val_type\n\n\n')
    for n, s in sdo_dict.items():
        if s is None:
            s_file.write(f'\n# {n}\n')
            continue
        line = f'{n} = SdoObject('
        line += f'{s.node}, '
        line += f'{hex(s.index)}, '
        line += f'{hex(s.sub)}, '
        line += f'val_type.{s.val_type.name})\n'
        s_file.write(line)

print(f'Sdo dictionary saved here:  {sdo_file}')
