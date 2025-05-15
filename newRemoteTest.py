import serial
import serial.tools.list_ports
import time

class ELL14K:
    def __init__(self, port='COM4', serial_number='2024-11401210', baudrate=115200, timeout=1.0, 
                 bytesize=serial.EIGHTBITS, parity=serial.PARITY_NONE, stopbits=serial.STOPBITS_ONE):
        self.serial_number = serial_number
        self.baudrate = baudrate
        self.timeout = timeout
        self.axis_id = b'1'
        self.steps_per_rev = 51200

        if port is None:
            port = self._find_port()

        try:
            self.ser = serial.Serial(
                port=port,
                baudrate=self.baudrate,
                timeout=self.timeout,
                bytesize=bytesize,
                parity=parity,
                stopbits=stopbits
            )
            self.ser.reset_input_buffer()
            self.ser.reset_output_buffer()
            print(f"Connected to {port} with settings: {self.baudrate} baud, timeout {self.timeout}s")
        except serial.SerialException as e:
            raise Exception(f"Failed to open serial port: {e}")

    def _find_port(self):
        print("Searching for available ports...")
        try:
            ports = serial.tools.list_ports.comports()
        except Exception as e:
            raise Exception(f"Failed to list COM ports: {e}")  # <--- ADDED

        for port in ports:
            print(f"Found port: {port.device} - {port.description} - SN: {port.serial_number}")
            if self.serial_number in port.serial_number:
                return port.device
        raise Exception(f"Could not find device with serial number {self.serial_number}")

    def _send_command(self, command_bytes):
        try:
            print(f"Sending raw command: {command_bytes}")
            print(f"Hex representation: {command_bytes.hex()}")

            full_command_crlf = command_bytes + b'\r\n'
            self.ser.write(full_command_crlf)
            time.sleep(0.2)

            response = b''
            start_time = time.time()
            while time.time() - start_time < self.timeout:
                try:
                    if self.ser.in_waiting > 0:
                        new_data = self.ser.read(self.ser.in_waiting)
                        response += new_data
                        print(f"Read partial data: {new_data}")
                        if b'\r\n' in response or b'\n' in response:
                            break
                except Exception as e:
                    print(f"Error while reading from serial: {e}")  # <--- ADDED
                time.sleep(0.05)

            print(f"Full response: {response} (Length: {len(response)})")
            print(f"Hex response: {response.hex()}")

            if not response:
                print("WARNING: No response received. Retrying with axis ID...")
                full_command_with_id = self.axis_id + command_bytes + b'\r\n'
                self.ser.write(full_command_with_id)
                time.sleep(0.2)

                response = b''
                start_time = time.time()
                while time.time() - start_time < self.timeout:
                    try:
                        if self.ser.in_waiting > 0:
                            new_data = self.ser.read(self.ser.in_waiting)
                            response += new_data
                            print(f"Read partial data with ID: {new_data}")
                            if b'\r\n' in response or b'\n' in response:
                                break
                    except Exception as e:
                        print(f"Error while reading with ID: {e}")
                    time.sleep(0.05)

                print(f"Response with ID: {response} (Length: {len(response)})")

            return response.strip()

        except serial.SerialException as e:
            raise Exception(f"Serial communication error: {e}")
        except Exception as e:
            print(f"Unexpected error in _send_command: {e}")
            return b''

    def home(self):
        print("\n--- HOMING DEVICE ---")
        commands = [b'HO', b'HOME', b'0HO']
        for cmd in commands:
            try:
                print(f"Trying home command: {cmd}")
                response = self._send_command(cmd)
                if response:
                    print(f"Home command {cmd} got response: {response}")
                    time.sleep(2)
                    return response
            except Exception as e:
                print(f"Error during home command {cmd}: {e}")  # <--- ADDED
            time.sleep(0.5)
        return None

    def get_angle(self):
        print("\n--- GETTING CURRENT ANGLE ---")
        commands = [b'GP', b'GETPOS', b'0GP']
        for cmd in commands:
            try:
                print(f"Trying get position command: {cmd}")
                response = self._send_command(cmd)
                if response:
                    try:
                        response_str = response.decode('ascii', errors='replace')
                        print(f"Decoded response: {response_str}")
                        if 'PO' in response_str:
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
                                    print(f"Could not convert '{hex_str}' to int")
                    except Exception as e:
                        print(f"Failed decoding/parsing response: {e}")
            except Exception as e:
                print(f"Error during get_angle command {cmd}: {e}")
            time.sleep(0.5)
        print("No valid response from any get position command")
        return None

    def move_to_angle(self, angle_deg):
        print(f"\n--- MOVING TO {angle_deg} DEGREES ---")
        angle_deg %= 360
        steps = int(angle_deg * self.steps_per_rev / 360)
        steps_hex = f"{steps:06X}"

        commands = [
            f"MA{steps_hex}".encode('ascii'),
            f"0MA{steps_hex}".encode('ascii'),
            f"MOVEABS{steps_hex}".encode('ascii')
        ]

        for cmd in commands:
            try:
                print(f"Trying move command: {cmd}")
                response = self._send_command(cmd)
                if response:
                    print(f"Move command {cmd} got response: {response}")
                    time.sleep(1)
                    return response
            except Exception as e:
                print(f"Error during move_to_angle command {cmd}: {e}")
            time.sleep(0.5)
        return None

    def move_by_angle(self, delta_deg):
        print(f"\n--- MOVING BY {delta_deg} DEGREES ---")
        steps = int(delta_deg * self.steps_per_rev / 360)
        if steps < 0:
            steps_hex = f"{abs(steps):06X}"
            commands = [
                f"MR-{steps_hex}".encode('ascii'),
                f"0MR-{steps_hex}".encode('ascii'),
                f"MOVEREL-{steps_hex}".encode('ascii')
            ]
        else:
            steps_hex = f"{steps:06X}"
            commands = [
                f"MR+{steps_hex}".encode('ascii'),
                f"0MR+{steps_hex}".encode('ascii'),
                f"MOVEREL+{steps_hex}".encode('ascii')
            ]

        for cmd in commands:
            try:
                print(f"Trying relative move command: {cmd}")
                response = self._send_command(cmd)
                if response:
                    print(f"Relative move command {cmd} got response: {response}")
                    time.sleep(1)
                    return response
            except Exception as e:
                print(f"Error during move_by_angle command {cmd}: {e}")
            time.sleep(0.5)
        return None

    def close(self):
        if hasattr(self, 'ser') and self.ser.is_open:
            self.ser.close()
            print("Serial connection closed")

if __name__ == "__main__":
    mount = None
    try:
        print("Available ports:")
        try:
            ports = list(serial.tools.list_ports.comports())
            for p in ports:
                print(f"{p.device} - {p.description} - SN: {p.serial_number}")
        except Exception as e:
            print(f"Failed to list ports: {e}")

        mount = ELL14K(port='COM4', baudrate=115200, timeout=2.0)

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
        print(f"ERROR: {e}")
    finally:
        if mount is not None:
            mount.close()
