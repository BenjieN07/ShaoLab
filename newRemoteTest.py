import serial
import time
import serial.tools.list_ports

class ELL14K:
    def __init__(self, port='COM4', serial_number='11401210', baudrate=9600, timeout=1.0):
        self.serial_number = serial_number
        self.baudrate = baudrate
        self.timeout = timeout
        self.axis_id = b'0'  # Elliptec default axis ID is '0'
        self.steps_per_rev = 51200  # 51200 steps per revolution

        if port is None:
            port = self._find_port()

        try:
            self.ser = serial.Serial(
                port=port,
                baudrate=self.baudrate,
                timeout=self.timeout,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE
            )
            self.ser.reset_input_buffer()
            self.ser.reset_output_buffer()
            print(f"Connected to {port}")
        except serial.SerialException as e:
            raise Exception(f"Failed to open serial port: {e}")

    def _find_port(self):
        ports = serial.tools.list_ports.comports()
        for port in ports:
            if self.serial_number and self.serial_number in str(port.serial_number):
                return port.device
        raise Exception(f"Could not find port for serial number: {self.serial_number}")

    def _send_command(self, command_bytes, read_length=32):
        try:
            self.ser.write(command_bytes)
            time.sleep(0.1)
            response = self.ser.read(read_length)
            print(f"Sent: {command_bytes}, Received: {response}")
            return response.strip()
        except Exception as e:
            print(f"Error sending command {command_bytes}: {e}")
            return b''

    def home(self):
        print("\n--- HOMING DEVICE ---")
        return self._send_command(b'0HO')

    def get_angle(self):
        print("\n--- GETTING CURRENT ANGLE ---")
        response = self._send_command(b'0GP')
        if response and response.startswith(b'0PO'):
            try:
                hex_steps = response[3:9].decode('ascii')
                steps = int(hex_steps, 16)
                angle = (steps * 360.0) / self.steps_per_rev
                print(f"Raw steps: {steps}, Angle: {angle:.2f}°")
                return angle
            except Exception as e:
                print(f"Failed to parse angle: {e}")
        else:
            print("Invalid or empty response.")
        return None

    def move_to_angle(self, angle_deg):
        print(f"\n--- MOVING TO {angle_deg} DEGREES ---")
        angle_deg %= 360  # normalize
        steps = int(angle_deg * self.steps_per_rev / 360)
        hex_steps = f"{steps:06X}".encode('ascii')
        cmd = b'0MA' + hex_steps
        return self._send_command(cmd)

    def move_by_angle(self, delta_deg):
        print(f"\n--- MOVING BY {delta_deg} DEGREES ---")
        steps = int(delta_deg * self.steps_per_rev / 360)
        if steps < 0:
            steps = (1 << 24) + steps  # 2's complement
        hex_steps = f"{steps:06X}".encode('ascii')
        cmd = b'0MR' + hex_steps
        return self._send_command(cmd)

    def close(self):
        if hasattr(self, 'ser') and self.ser.is_open:
            self.ser.close()
            print("Serial connection closed")

if __name__ == "__main__":
    mount = None
    try:
        print("Scanning available ports:")
        for p in serial.tools.list_ports.comports():
            print(f"{p.device} - {p.description} - SN: {p.serial_number}")

        mount = ELL14K(port='COM4')

        print("\nInitial position:")
        angle = mount.get_angle()
        if angle is not None:
            print(f"Current Angle: {angle:.2f}°")
        else:
            print("Failed to read angle.")

        print("\nHoming...")
        mount.home()
        time.sleep(3)

        print("\nAngle after homing:")
        angle = mount.get_angle()
        if angle is not None:
            print(f"Angle: {angle:.2f}°")

        print("\nMoving to 90°...")
        mount.move_to_angle(90)
        time.sleep(2)

        print("\nNew angle:")
        angle = mount.get_angle()
        if angle is not None:
            print(f"Angle: {angle:.2f}°")

    except Exception as e:
        print(f"ERROR: {e}")
    finally:
        if mount:
            mount.close()
