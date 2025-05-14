import serial
import time
import serial.tools.list_ports



### run using remoteTest.py 

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

    def home(self):
        """Snap to 0 degrees to simulate homing."""
        print("Simulated homing: moving to 0 degrees...")
        return self.move_to_angle(180)

    def get_angle(self):
        """Get current angle in degrees."""
        try:
            self.ser.write(self.axis_id + b'GP\n')
            time.sleep(0.05)
            response = self.ser.read(6)
            print(f"GP response: {response}")
            if len(response) == 6 and response[1:3] == b'PO':
                steps = int.from_bytes(response[3:6], 'big')
                return steps * 360.0 / self.steps_per_rev
            raise Exception(f"Invalid response format: {response}")
        except Exception as e:
            print(f"Error getting angle: {e}")
            return None

    def move_to_angle(self, angle_deg):
        """Move to absolute angle."""
        try:
            angle_deg %= 360
            steps = int(angle_deg * self.steps_per_rev / 360)
            command = f"ma{steps}".encode('ascii')
            response = self._send_command(command)
            time.sleep(0.5)
            return response
        except Exception as e:
            print(f"Error moving to angle: {e}")
            return None

    def move_by_angle(self, delta_deg):
        """Move by relative angle."""
        try:
            steps = int(delta_deg * self.steps_per_rev / 360)
            command = f"mr{steps}".encode('ascii')  # negative or positive
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

        '''print("Moving to 180 degrees...")
        mount.move_to_angle(180)
        time.sleep(1)
        print("Current Angle:", mount.get_angle() / 360)'''

        '''print("Moving by 45 degrees...")
        mount.move_by_angle(45)
        time.sleep(1)
        print("New Angle:", mount.get_angle() / 360)'''

    except Exception as e:
        print(f"Error: {e}")
    finally:
        if mount is not None:
            mount.close()
