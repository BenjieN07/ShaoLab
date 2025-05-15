import serial
import time
import serial.tools.list_ports

# Changes for each function - notes for Ben 
# move_to_angle - Now properly formats the steps as a 6-digit hexadecimal string and uses uppercase 'MA' command as per Thorlabs protocol.
# move_by_angle - Fixed to properly handle negative angles and use hex formatting.
# home - Now uses the proper 'HO' command instead of trying to move to a specific angle.
# get_angle - Updated to use the _send_command method for consistency and properly parse the hexadecimal position response.

# Previous issues -
# Thorlabs ELL14K requires position values to be in hexadecimal format, not decimal
# Commands need to be uppercase (MA, MR, HO, GP) as per the protocol
# For proper communication, the functions should consistently use the _send_command method


class ELL14K:
    def __init__(self, port='COM4', serial_number='2024-11401210', baudrate=9600, timeout=0.5):
        self.serial_number = serial_number
        self.baudrate = baudrate
        self.timeout = timeout
        self.axis_id = b'0'
        self.steps_per_rev = 51200  # From Thorlabs documentation
        
        # If port is not specified, try to find it automatically
        if port is None:
            port = self._find_port()
        
        try:
            self.ser = serial.Serial(port=port, baudrate=self.baudrate, timeout=self.timeout)
            # Clear any existing data in the buffer
            self.ser.reset_input_buffer()
            self.ser.reset_output_buffer()
            print(f"Connected to {port}")
        except serial.SerialException as e:
            raise Exception(f"Failed to open serial port: {e}")

    def _find_port(self):
        """Find the correct port for the device."""
        ports = serial.tools.list_ports.comports()
        for port in ports:
            if self.serial_number in port.serial_number:
                return port.device
        raise Exception(f"Could not find device with serial number {self.serial_number}")

    def _calculate_checksum(self, command):
        """Calculate checksum for Thorlabs protocol."""
        return sum(command) & 0xFF

    def _send_command(self, command_bytes):
        """Send ASCII command to Elliptec and return text response."""
        try:
            full_command = self.axis_id + command_bytes + b'\n'
            self.ser.write(full_command)
            time.sleep(0.1)
            response = self.ser.readline()  # Reads until \n
            print(f"Sent: {full_command}, Received: {response}")
            if not response:
                raise Exception("No response received from device")
            return response.strip()  # Remove trailing \n
        except serial.SerialException as e:
            raise Exception(f"Communication error: {e}")

    #Doesn't work at all, always goes to 0 degrees
    def home(self):
        """Home the device using the HO command."""
        try:
            command = b'HO'
            response = self._send_command(command)
            time.sleep(2)  # Give it time to complete homing
            return response
        except Exception as e:
            print(f"Error homing device: {e}")
            return None

    def get_angle(self):
        """Get current angle in degrees."""
        try:
            response = self._send_command(b'GP')
            if len(response) >= 9 and response[1:3] == b'PO':
                # The position is in the response as a hex value
                hex_pos = response[3:9].decode('ascii')
                steps = int(hex_pos, 16)
                angle = steps * 360.0 / self.steps_per_rev
                return angle
            raise Exception(f"Invalid response format: {response}")
        except Exception as e:
            print(f"Error getting angle: {e}")
            return None

    # Move to always moves to 0 degrees no matter what degree we put in 
    def move_to_angle(self, angle_deg):
        """Move to absolute angle."""
        try:
            angle_deg %= 360
            steps = int(angle_deg * self.steps_per_rev / 360)
            # Format steps as a 6-digit hex string
            steps_hex = f"{steps:06X}"
            command = f"MA{steps_hex}".encode('ascii')
            response = self._send_command(command)
            time.sleep(0.5)
            return response
        except Exception as e:
            print(f"Error moving to angle: {e}")
            return None

    # doesnt work at all, no response
    def move_by_angle(self, delta_deg):
        """Move by relative angle."""
        try:
            steps = int(delta_deg * self.steps_per_rev / 360)
            # Format steps as a 6-digit hex string, preserving negative sign if present
            if steps < 0:
                steps_hex = f"{abs(steps):06X}"
                command = f"MR-{steps_hex}".encode('ascii')
            else:
                steps_hex = f"{steps:06X}"
                command = f"MR{steps_hex}".encode('ascii')
            response = self._send_command(command)
            time.sleep(0.5)
            return response
        except Exception as e:
            print(f"Error moving by angle: {e}")
            return None

    def close(self):
        """Safely close the serial connection."""
        if hasattr(self, 'ser') and self.ser.is_open:
            self.ser.close()

if __name__ == "__main__":
    
    mount = None  # Initialize mount outside try block
    try:
        # The port will be automatically detected based on serial number
        mount = ELL14K(serial_number='2024-11401210')
        
        print("Homing device...")
        mount.home()
        time.sleep(3)

        print("Getting current angle...")
        current_angle = mount.get_angle()
        print(f"Current Angle: {current_angle:.2f} degrees")

        print("Moving to 180 degrees...")
        mount.move_to_angle(180)
        time.sleep(2)
        current_angle = mount.get_angle()
        print(f"Current Angle: {current_angle:.2f} degrees")

        print("Moving by 45 degrees...")
        mount.move_by_angle(45)
        time.sleep(2)
        current_angle = mount.get_angle()
        print(f"Current Angle: {current_angle:.2f} degrees")

    except Exception as e:
        print(f"Error: {e}")
    finally:
        if mount is not None:
            mount.close()
