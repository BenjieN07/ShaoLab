import sys
import serial
import time
from PyQt5.QtWidgets import (
    QApplication, QFrame, QLabel, QPushButton, QLineEdit,
    QDoubleSpinBox, QVBoxLayout, QHBoxLayout, QGridLayout, QMessageBox, QSlider
)
from PyQt5.QtCore import Qt, QTimer

# --- Serial control logic from your original code ---

def degrees_to_hex(degrees):
    steps = int(round(degrees * 398.2))
    return f"{steps:08X}"

def hex_to_degrees(hex_str):
    if not hex_str.startswith("0ma") or len(hex_str) != 11:
        raise ValueError("Invalid response format for conversion")
    steps = int(hex_str[3:], 16)
    return steps / 398.2

def send_command(ser, command):
    if ser.isOpen():
        ser.reset_input_buffer()
        ser.reset_output_buffer()
        ser.write(command.encode('utf-8'))
        ser.write(b'\r\n')
        time.sleep(0.2)
        response = b''
        start = time.time()
        while time.time() - start < 1.0:
            if ser.in_waiting:
                response += ser.read(ser.in_waiting)
                time.sleep(0.1)
            else:
                time.sleep(0.05)
        return (response, response.decode('utf-8', errors='ignore').strip()) if response else None
    return None

def move_to(ser, angle, motor_num='0'):
    hex_steps = degrees_to_hex(angle)
    command = f'{motor_num}ma{hex_steps}'
    send_command(ser, command)
    while True:
        status = send_command(ser, f'{motor_num}gs')
        if status and 'GS00' in status[1]:
            break
        time.sleep(0.1)

# --- UI class ---

class ELL14K(QFrame):
    def __init__(self):
        super().__init__()
        self.ser = None
        self.connected = False
        self.setWindowTitle("ELL14K Controller")
        self.setGeometry(700, 400, 350, 250)
        self.initUI()

    def initUI(self):
        grid = QGridLayout()
        self.setLayout(grid)

        self.serial_label = QLabel("Port (e.g. COM4):")
        self.serial_input = QLineEdit("COM4")
        self.connect_btn = QPushButton("Connect")
        self.connect_btn.clicked.connect(self.connect_device)
        self.status_label = QLabel("🔴 Disconnected")

        grid.addWidget(self.serial_label, 0, 0)
        grid.addWidget(self.serial_input, 0, 1)
        grid.addWidget(self.connect_btn, 0, 2)
        grid.addWidget(self.status_label, 1, 0, 1, 3)

        # Angle spinbox
        self.angle_spin = QDoubleSpinBox()
        self.angle_spin.setRange(0, 360)
        self.angle_spin.setDecimals(2)
        self.angle_spin.setSingleStep(1)
        self.angle_spin.setEnabled(False)
        grid.addWidget(QLabel("Set Angle:"), 2, 0)
        grid.addWidget(self.angle_spin, 2, 1)

        # Move button
        self.move_btn = QPushButton("Move")
        self.move_btn.setEnabled(False)
        self.move_btn.clicked.connect(self.move_motor)
        grid.addWidget(self.move_btn, 2, 2)

        # Get position
        self.get_pos_btn = QPushButton("Get Pos")
        self.get_pos_btn.setEnabled(False)
        self.get_pos_btn.clicked.connect(self.update_position)
        grid.addWidget(self.get_pos_btn, 3, 0)

        self.current_pos = QLineEdit("")
        self.current_pos.setReadOnly(True)
        grid.addWidget(self.current_pos, 3, 1, 1, 2)

    def connect_device(self):
        port = self.serial_input.text()
        try:
            self.ser = serial.Serial(port=port, baudrate=9600, timeout=1)
            time.sleep(2)
            resp = send_command(self.ser, '0in')
            if resp:
                self.connected = True
                self.status_label.setText("🟢 Connected")
                self.angle_spin.setEnabled(True)
                self.move_btn.setEnabled(True)
                self.get_pos_btn.setEnabled(True)
            else:
                raise Exception("No response from device.")
        except Exception as e:
            QMessageBox.critical(self, "Connection Failed", str(e))
            self.status_label.setText("🔴 Disconnected")

    def move_motor(self):
        if self.connected:
            angle = self.angle_spin.value()
            move_to(self.ser, angle)

    def update_position(self):
        if self.connected:
            response = send_command(self.ser, '0gp')
            if response:
                try:
                    degrees = hex_to_degrees('0ma' + response[1][3:].strip())
                    self.current_pos.setText(f"{degrees:.2f}°")
                except Exception:
                    self.current_pos.setText("Error parsing")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = ELL14K()
    window.show()
    sys.exit(app.exec_())
