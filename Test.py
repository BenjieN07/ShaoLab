import serial

ser = serial.Serial('COM4', 115200, timeout=1)
ser.write(b'0ZZ')
ser.read(32)

