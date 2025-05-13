import serial
import time

class ELL14K:
    def __init__(self, port='COM4', serial_number='2024-11401210', baudrate=9600, timeout=0.5):
        self.port = port
        self.serial_number = serial_number
        self.baudrate = baudrate
        self.timeout = timeout
        self.axis_id = b'0'
        self.steps_per_rev = 51200  # From Thorlabs documentation
        self.ser = serial.Serial(port=self.port, baudrate=self.baudrate, timeout=self.timeout)

    def _send_command(self, command_bytes):
        self.ser.write(self.axis_id + command_bytes)
        time.sleep(0.05)
        return self.ser.read_all()

    def home(self):
        return self._send_command(b'OR')  # Origin

    def get_angle(self):
        response = self._send_command(b'GP')
        print("Raw GP response:", response)  # Optional debug
        if len(response) == 6 and response[1:3] == b'PO':
            steps = int.from_bytes(response[3:6], 'big')
            return steps * 360.0 / self.steps_per_rev
        return None

    def move_to_angle(self, angle_deg):
        angle_deg %= 360
        steps = int(angle_deg * self.steps_per_rev / 360)
        step_bytes = steps.to_bytes(3, 'big')
        return self._send_command(b'MA' + step_bytes)

    def move_by_angle(self, delta_deg):
        steps = int(delta_deg * self.steps_per_rev / 360)
        step_bytes = abs(steps).to_bytes(3, 'big')
        if steps < 0:
            return self._send_command(b'MR' + step_bytes + b'-')
        else:
            return self._send_command(b'MR' + step_bytes)

    def close(self):
        self.ser.close()


if __name__ == "__main__":
    mount = ELL14K(port='COM4', serial_number='2024-11401210')
    mount.home()
    time.sleep(3)

    mount.move_to_angle(90)
    time.sleep(1)
    print("Current Angle:", mount.get_angle())

    mount.move_by_angle(45)
    time.sleep(1)
    print("New Angle:", mount.get_angle())

    mount.close()
