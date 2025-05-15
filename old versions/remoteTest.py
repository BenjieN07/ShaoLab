import serial
import time
import serial.tools.list_ports



### run using remoteTest.py 

class ELL14K:
    def __init__(self, port=None, serial_number='11401210', baudrate=9600, timeout=0.5):
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
        """Send command and wait for response with proper Thorlabs protocol."""
        try:
            # Format command according to Thorlabs protocol
            full_command = self.axis_id + command_bytes + b'\r'
            checksum = self._calculate_checksum(full_command)
            full_command += bytes([checksum])
            
            self.ser.write(full_command)
            time.sleep(0.1)  # Wait for device to process
            
            # Read response
            response = self.ser.read_until(b'\r')
            if not response:
                raise Exception("No response received from device")
            
            # Verify response checksum
            if len(response) > 1:
                received_checksum = response[-1]
                calculated_checksum = self._calculate_checksum(response[:-1])
                if received_checksum != calculated_checksum:
                    raise Exception("Checksum error in response")
            
            return response[:-1]  # Remove checksum from response
        except serial.SerialException as e:
            raise Exception(f"Communication error: {e}")

    def home(self):
        """Home the device and wait for completion."""
        response = self._send_command(b'OR')
        time.sleep(2)  # Wait for homing to complete
        return response

    def get_angle(self):
        """Get current angle with improved error handling."""
        try:
            response = self._send_command(b'GP')
            if len(response) >= 6 and response[1:3] == b'PO':
                # Convert response to steps and then to degrees
                steps = int.from_bytes(response[3:6], 'big')
                return steps * 360.0 / self.steps_per_rev
            raise Exception(f"Invalid response format: {response}")
        except Exception as e:
            print(f"Error getting angle: {e}")
            return None

    def move_to_angle(self, angle_deg):
        """Move to absolute angle with error checking."""
        try:
            angle_deg %= 360
            steps = int(angle_deg * self.steps_per_rev / 360)
            step_bytes = steps.to_bytes(3, 'big')
            response = self._send_command(b'MA' + step_bytes)
            time.sleep(0.5)  # Wait for movement to complete
            return response
        except Exception as e:
            print(f"Error moving to angle: {e}")
            return None

    def move_by_angle(self, delta_deg):
        """Move by relative angle with error checking."""
        try:
            steps = int(delta_deg * self.steps_per_rev / 360)
            step_bytes = abs(steps).to_bytes(3, 'big')
            if steps < 0:
                response = self._send_command(b'MR' + step_bytes + b'-')
            else:
                response = self._send_command(b'MR' + step_bytes)
            time.sleep(0.5)  # Wait for movement to complete
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
        
        '''print("Homing device...")
        mount.home()
        time.sleep(3)'''

        print("Moving to 90 degrees...")
        mount.move_to_angle(90)
        time.sleep(1)
        print("Current Angle:", mount.get_angle())

        '''print("Moving by 45 degrees...")
        mount.move_by_angle(45)
        time.sleep(1)
        print("New Angle:", mount.get_angle())'''

    except Exception as e:
        print(f"Error: {e}")
    finally:
        if mount is not None:
            mount.close()
