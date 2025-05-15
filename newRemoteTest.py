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
    def __init__(self, port='COM4', serial_number='2024-11401210', baudrate=9600, timeout=1.0, 
                 bytesize=serial.EIGHTBITS, parity=serial.PARITY_NONE, stopbits=serial.STOPBITS_ONE):
        self.serial_number = serial_number
        self.baudrate = baudrate
        self.timeout = timeout
        # Default to '0' for single-axis setups
        self.axis_id = b'0'
        self.steps_per_rev = 51200  # From Thorlabs documentation
        
        # If port is not specified, try to find it automatically
        if port is None:
            port = self._find_port()
        
        try:
            # Open with explicit serial parameters
            self.ser = serial.Serial(
                port=port, 
                baudrate=self.baudrate, 
                timeout=self.timeout,
                bytesize=bytesize,
                parity=parity,
                stopbits=stopbits
            )
            # Clear any existing data in the buffer
            self.ser.reset_input_buffer()
            self.ser.reset_output_buffer()
            print(f"Connected to {port} with settings: {self.baudrate} baud, timeout {self.timeout}s")
        except serial.SerialException as e:
            raise Exception(f"Failed to open serial port: {e}")

    def _find_port(self):
        """Find the correct port for the device."""
        print("Searching for available ports...")
        ports = serial.tools.list_ports.comports()
        for port in ports:
            print(f"Found port: {port.device} - {port.description} - SN: {port.serial_number}")
            if self.serial_number in port.serial_number:
                return port.device
        raise Exception(f"Could not find device with serial number {self.serial_number}")

    def _calculate_checksum(self, command):
        """Calculate checksum for Thorlabs protocol."""
        return sum(command) & 0xFF

    def _send_command(self, command_bytes):
        """Send ASCII command to Elliptec and return text response."""
        try:
            # According to Thorlabs ELL protocol:
            # Format: [Axis ID][Command][Parameters][CR][LF]
            
            # Try both termination styles since documentation can vary
            full_command = self.axis_id + command_bytes
            
            # Debug info before sending
            print(f"Sending raw command: {full_command}")
            print(f"Hex representation: {full_command.hex()}")
            
            # Add CR+LF termination (common for Thorlabs devices)
            full_command_crlf = full_command + b'\r\n'
            self.ser.write(full_command_crlf)
            
            # Wait for device to process command
            time.sleep(0.2)
            
            # Read response with timeout
            response = b''
            start_time = time.time()
            while time.time() - start_time < self.timeout:
                if self.ser.in_waiting > 0:
                    new_data = self.ser.read(self.ser.in_waiting)
                    response += new_data
                    print(f"Read partial data: {new_data}")
                    # Break if we have a complete response
                    if b'\r\n' in response or b'\n' in response:
                        break
                time.sleep(0.05)
            
            # Debug information
            print(f"Full response: {response} (Length: {len(response)})")
            print(f"Hex response: {response.hex()}")
            
            if not response:
                print("WARNING: No response received from device")
                
            return response.strip()
            
        except serial.SerialException as e:
            raise Exception(f"Communication error: {e}")
        except Exception as e:
            print(f"Unexpected error in _send_command: {e}")
            return b''

    def home(self):
        """Home the device using the HO command."""
        try:
            print("\n--- HOMING DEVICE ---")
            command = b'HO'
            response = self._send_command(command)
            time.sleep(2)  # Wait for homing to complete
            return response
        except Exception as e:
            print(f"Error homing device: {e}")
            return None

    def get_angle(self):
        """Get current angle in degrees."""
        try:
            print("\n--- GETTING CURRENT ANGLE ---")
            response = self._send_command(b'GP')
            
            # Detailed response parsing with debug
            print(f"Raw position response: {response}")
            if not response:
                print("Empty response when getting angle")
                return None
                
            try:
                # Try to decode as ASCII first
                response_str = response.decode('ascii', errors='replace')
                print(f"Decoded response: {response_str}")
                
                # Look for position data in various formats
                # Some devices return 0PO[hex], others might use different formats
                if 'PO' in response_str:
                    # Try to extract the hex position after 'PO'
                    pos_index = response_str.find('PO') + 2
                    if pos_index < len(response_str):
                        hex_str = response_str[pos_index:pos_index+6]
                        print(f"Extracted hex position: {hex_str}")
                        try:
                            steps = int(hex_str, 16)
                            angle = steps * 360.0 / self.steps_per_rev
                            print(f"Calculated angle: {angle:.2f} degrees")
                            return angle
                        except ValueError:
                            print(f"Could not convert '{hex_str}' to integer")
            except Exception as e:
                print(f"Error parsing position: {e}")
            
            print(f"Could not parse position response: {response}")
            return None
        except Exception as e:
            print(f"Error getting angle: {e}")
            return None

    def move_to_angle(self, angle_deg):
        """Move to absolute angle."""
        try:
            print(f"\n--- MOVING TO {angle_deg} DEGREES ---")
            # Normalize angle to 0-360
            angle_deg %= 360
            
            # Convert angle to steps
            steps = int(angle_deg * self.steps_per_rev / 360)
            
            # Format according to Thorlabs protocol: 6-digit uppercase hex
            steps_hex = f"{steps:06X}"
            
            # Command format: [Axis ID]MA[position]
            command = f"MA{steps_hex}".encode('ascii')
            
            print(f"Move to angle: {angle_deg} = {steps} steps = hex {steps_hex}")
            response = self._send_command(command)
            
            # Give time for movement to complete
            time.sleep(1)
            
            return response
        except Exception as e:
            print(f"Error moving to angle: {e}")
            return None

    def move_by_angle(self, delta_deg):
        """Move by relative angle."""
        try:
            print(f"\n--- MOVING BY {delta_deg} DEGREES ---")
            # Convert angle to steps
            steps = int(delta_deg * self.steps_per_rev / 360)
            
            # Format based on direction
            if steps < 0:
                # Negative movement
                steps_hex = f"{abs(steps):06X}"
                command = f"MR-{steps_hex}".encode('ascii')
            else:
                # Positive movement
                steps_hex = f"{steps:06X}"
                command = f"MR+{steps_hex}".encode('ascii')
            
            print(f"Move by angle: {delta_deg} = {steps} steps = command {command}")
            response = self._send_command(command)
            
            # Give time for movement to complete
            time.sleep(1)
            
            return response
        except Exception as e:
            print(f"Error moving by angle: {e}")
            return None

    def close(self):
        """Safely close the serial connection."""
        if hasattr(self, 'ser') and self.ser.is_open:
            self.ser.close()
            print("Serial connection closed")

if __name__ == "__main__":
    
    mount = None  # Initialize mount outside try block
    try:
        # List all available ports for troubleshooting
        print("Available ports:")
        ports = list(serial.tools.list_ports.comports())
        for p in ports:
            print(f"{p.device} - {p.description} - SN: {p.serial_number}")
        
        # Try with explicit port instead of relying on serial number
        mount = ELL14K(port='COM4', timeout=2.0)
        
        print("\nInitial device status check...")
        current_angle = mount.get_angle()
        if current_angle is not None:
            print(f"Starting position: {current_angle:.2f} degrees")
        else:
            print("Could not determine starting position")
        
        print("\nHoming device...")
        home_response = mount.home()
        print(f"Home response: {home_response}")
        time.sleep(2)
        
        print("\nGetting current angle after homing...")
        current_angle = mount.get_angle()
        if current_angle is not None:
            print(f"Current Angle after homing: {current_angle:.2f} degrees")
        
        print("\nMoving to 90 degrees...")
        move_response = mount.move_to_angle(90)
        print(f"Move response: {move_response}")
        time.sleep(1)
        
        print("\nGetting angle after movement...")
        current_angle = mount.get_angle()
        if current_angle is not None:
            print(f"Current Angle after movement: {current_angle:.2f} degrees")
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        if mount is not None:
            mount.close()
