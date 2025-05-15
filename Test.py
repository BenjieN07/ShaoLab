import serial
import time

try:
    ser = serial.Serial('COM4', 115200, timeout=1)
    ser.reset_input_buffer()
    ser.reset_output_buffer()

    print("Sending identity request: 0ZZ")
    ser.write(b'0ZZ')
    time.sleep(0.1)  # Small delay to wait for response

    response = ser.read(32)
    print(f"Raw response: {response}")
    print(f"Decoded: {response.decode(errors='ignore')}")

except serial.SerialException as e:
    print(f"Serial error: {e}")
except Exception as e:
    print(f"General error: {e}")
finally:
    if 'ser' in locals() and ser.is_open:
        ser.close()
