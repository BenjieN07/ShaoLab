import serial
import time

def send_command(ser, cmd, read_length=32, delay=0.1):
    """
    Send a command to the Elliptec device and read the response.
    """
    ser.reset_input_buffer()
    ser.reset_output_buffer()
    ser.write(cmd)
    time.sleep(delay)
    response = ser.read(read_length)
    return response

if __name__ == "__main__":
    port = 'COM4'      # Adjust if needed
    baudrate = 9600    # IMPORTANT: matches the manual and the GitHub repo
    timeout = 1        # seconds

    try:
        ser = serial.Serial(port, baudrate, timeout=timeout)
        print(f"Opened {port} at {baudrate} baud")

        # The identity command from the manual is '0ZZ' (axis 0, command ZZ)
        cmd = b'0ZZ'
        print(f"Sending command: {cmd.decode()}")

        # Try a few times in case device is slow to respond
        for attempt in range(3):
            response = send_command(ser, cmd)
            if response:
                print(f"Response (raw): {response}")
                print(f"Response (decoded): {response.decode(errors='ignore')}")
                break
            else:
                print(f"No response, retrying... ({attempt + 1}/3)")
                time.sleep(0.2)
        else:
            print("Failed to get a response after 3 tries.")

    except serial.SerialException as e:
        print(f"Serial error: {e}")
    except Exception as e:
        print(f"General error: {e}")
    finally:
        if 'ser' in locals() and ser.is_open:
            ser.close()
            print("Closed serial port")
