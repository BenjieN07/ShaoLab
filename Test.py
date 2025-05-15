import serial
import time

def send_command(ser, command):
    """
    Sends a command to the motor via serial communication.
    Returns the response or None if the COM port is unavailable.
    """
    if ser.isOpen():
        # Clear any existing data in the buffers
        ser.reset_input_buffer()
        ser.reset_output_buffer()
        
        # Send the command
        ser.write(command.encode('utf-8'))
        ser.write(b'\r\n')
        
        # Wait for response
        time.sleep(0.2)  # Increased wait time
        
        # Read response with timeout
        response = b''
        start_time = time.time()
        while (time.time() - start_time) < 1.0:  # 1 second timeout
            if ser.in_waiting:
                response += ser.read(ser.in_waiting)
                time.sleep(0.1)  # Small delay between reads
            else:
                time.sleep(0.05)  # Small delay if no data
        
        if response:
            return (response, response.decode('utf-8', errors='ignore').strip())
        else:
            print(f"No response received for command: {command}")
            return None
    else:
        print("Serial connection is not open.")
        return None

if __name__ == "__main__":
    port = 'COM4'      # Adjust if needed
    baudrate = 9600    # IMPORTANT: matches the manual and the GitHub repo
    timeout = 1        # seconds

    try:
        ser = serial.Serial(port, baudrate, timeout=timeout)
        print(f"Opened {port} at {baudrate} baud")

        # Test basic commands
        print("\nTesting basic commands:")
        
        # Test identity command (0ZZ)
        print("\nTesting identity command:")
        response = send_command(ser, '0ZZ')
        print(f"Response: {response}")

        # Test home command (0ho0)
        print("\nTesting home command:")
        response = send_command(ser, '0ho0')
        print(f"Response: {response}")

        # Test get position command (0gp)
        print("\nTesting get position command:")
        response = send_command(ser, '0gp')
        print(f"Response: {response}")

        # Test get status command (0gs)
        print("\nTesting get status command:")
        response = send_command(ser, '0gs')
        print(f"Response: {response}")

        # Test get firmware version (0in)
        print("\nTesting get firmware version:")
        response = send_command(ser, '0in')
        print(f"Response: {response}")

    except serial.SerialException as e:
        print(f"Serial error: {e}")
    except Exception as e:
        print(f"General error: {e}")
    finally:
        if 'ser' in locals() and ser.is_open:
            ser.close()
            print("Closed serial port")

