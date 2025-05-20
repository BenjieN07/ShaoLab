import serial
import time

def degrees_to_hex(degrees):
    # Convert degrees to the correct hex format
    steps = int(round(degrees * 398.2))  # 392.2 steps per degree
    return f"{steps:08X}"

def hex_to_degrees(hex_str):
    """
    Converts a full 0maXXXXXXXX command back to degrees.
    Assumes 398.2 steps per degree.
    """
    if not hex_str.startswith("0ma") or len(hex_str) != 11:
        raise ValueError("Invalid response format for conversion")

    hex_part = hex_str[3:]  # Get the 8 hex digits
    steps = int(hex_part, 16)  # Convert hex to int
    degrees = steps / 398.2
    return degrees

def move_to(ser, angle, motor_num='0'):
    """
    Moves the motor to a specified angle in degrees.
    
    Parameters:
    -----------
    ser : serial.Serial
        Serial connection to the motor
    angle : float
        Target angle in degrees
    motor_num : str
        Motor number (default '0')
    """
    # Convert angle to hex format
    hex_steps = degrees_to_hex(angle)
    
    # Send move absolute command
    command = f'{motor_num}ma{hex_steps}'
    print(f"Moving to {angle} degrees (hex: {hex_steps})")
    
    response = send_command(ser, command)
    print("command", command)  # print the command being used
    
    if response:
        print(f"Move command response: {response}")
        
        # Wait for movement to complete
        while True:
            status = send_command(ser, f'{motor_num}gs')
            if status and 'GS00' in status:  # GS00 indicates movement complete
                break
            time.sleep(0.1)
        
        # Get final position
        pos_response = send_command(ser, f'{motor_num}gp')
        if pos_response:
            print(f"Final position: {pos_response}")
    else:
        print("Failed to send move command")

def send_command(ser, command):
    # Sends a command to the motor via serial communication.
    # Returns the response or None if the COM port is unavailable.

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
        '''print("\nTesting home command:")
        response = send_command(ser, '0ho0')
        print(f"Response: {response}")'''

        # Test get position command (0gp)
        print("\nTesting get position command:")
        response = send_command(ser, '0ma0000558E')
        print(f"Response: {response}")

        # Test get status command (0gs)
        print("\nTesting get status command:")
        response = send_command(ser, '0gs')
        print(f"Response: {response}")

        # Test get firmware version (0in)
        print("\nTesting get firmware version:")
        response = send_command(ser, '0in')
        print(f"Response: {response}")

        '''# Test move_to function
        print("\nTesting move_to function:")
        move_to(ser, 45)  # Move to 45 degrees
        time.sleep(2)
        move_to(ser, 90)  # Move to 90 degrees
        time.sleep(2)
        move_to(ser, 0)   # Move back to 0 degrees'''

    except serial.SerialException as e:
        print(f"Serial error: {e}")
    except Exception as e:
        print(f"General error: {e}")
    finally:
        if 'ser' in locals() and ser.is_open:
            ser.close()
            print("Closed serial port")

