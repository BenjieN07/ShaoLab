# ShaoLab - Thorlabs ELL14K Rotation Mount Control

## Prerequisites

- Python 3.6 or higher
- PySerial package
- Windows operating system
- Thorlabs ELL14K rotation mount
- USB connection to the device

## Installation

1. Install the required Python package:
```bash
pip install pyserial
```

2. Connect your Thorlabs ELL14K device to your computer via USB

## Usage

### Basic Usage
Run the script directly:
```bash
python remoteTest.py
```

The script should:
1. Automatically detect the correct COM port
2. Connect to the device
3. Run a test sequence:
   - Home the device
   - Move to 90 degrees
   - Move by 45 degrees
   - Display current angles

### Available Commands

The `ELL14K` class provides the following methods:

- `home()`: Homes the device to its reference position
- `get_angle()`: Returns the current angle in degrees
- `move_to_angle(angle_deg)`: Moves to an absolute angle (0-360 degrees)
- `move_by_angle(delta_deg)`: Moves by a relative angle


### Common Issues

1. **Device Not Found**
   - Verify the device is properly connected
   - Check if the serial number matches your device
   - Ensure no other program is using the COM port

2. **Communication Errors**
   - Verify the USB connection
   - Try unplugging and replugging the device
   - Check Device Manager for correct COM port

3. **Invalid Response**
   - Ensure the device is powered on
   - Verify the baudrate (default: 9600)
   - Check for proper USB drivers

### Error Messages

- "Failed to open serial port": Check COM port and connection
- "No response received from device": Verify device power and connection
- "Checksum error in response": Communication protocol error
- "Invalid response format": Device response not in expected format

## Technical Details

- Baudrate: 9600
- Steps per revolution: 51200
- Command timeout: 0.5 seconds
- Default axis ID: 0

## Safety Notes

1. Always ensure the device is properly mounted before movement
2. Do not exceed the device's physical limits
3. Keep the device powered during operation
4. Close the connection properly after use

## Support

For issues with the script, please check:
1. Thorlabs documentation for your specific device
2. Verify all connections and power supply
3. Check Windows Device Manager for proper device recognition
