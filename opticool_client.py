# File: opticool_client_gui.py
# This script runs the graphical interface (GUI) client to connect to the MultiPyVu server.
# It should be run in a separate terminal while opticool_server.py is running with --scaffold.

import MultiPyVu as mpv
import tkinter as tk
from tkinter import messagebox, ttk
import threading
import time
import logging

# --- Configuration ---
# Must match the server configuration
SERVER_HOST = '127.0.0.1' # Localhost is correct when running both on your MacBook
SERVER_PORT = 5001        # Must match the current server port (5001)

# Configure logging for the client application
logging.basicConfig(level=logging.INFO, format='%(asctime)s - CLIENT - %(levelname)s - %(message)s')

class OptiCoolClientApp:
    def __init__(self, master):
        self.master = master
        master.title("OptiCool MultiPyVu Client (Scaffold Test)")

        self.client = None
        self.is_connected = False
        self.status_updater_thread = None
        self.running_command = threading.Lock()

        # --- GUI Setup ---
        self.setup_ui(master)

        # Attempt initial connection
        self.connect_to_server()

    def setup_ui(self, master):
        """Creates and arranges all GUI widgets."""
        
        # Style
        style = ttk.Style()
        style.configure("TFrame", background="#f0f0f0")
        style.configure("TLabel", background="#f0f0f0", font=('Arial', 10))
        style.configure("TButton", font=('Arial', 10, 'bold'))
        
        main_frame = ttk.Frame(master, padding="10")
        main_frame.pack(fill='both', expand=True)

        # Connection Status Section
        conn_frame = ttk.LabelFrame(main_frame, text="Connection Status", padding="10")
        conn_frame.grid(row=0, column=0, columnspan=2, pady=10, sticky="ew")
        
        self.conn_label = ttk.Label(conn_frame, text="Disconnected", foreground="red", font=('Arial', 12, 'bold'))
        self.conn_label.pack(fill='x')
        
        # Cryostat Status Section (Readback)
        status_frame = ttk.LabelFrame(main_frame, text="Current Readback", padding="10")
        status_frame.grid(row=1, column=0, pady=10, sticky="ew")
        
        self.temp_read_label = ttk.Label(status_frame, text="Temperature: N/A")
        self.field_read_label = ttk.Label(status_frame, text="Field: N/A")
        self.status_read_label = ttk.Label(status_frame, text="System Status: N/A")

        self.temp_read_label.pack(fill='x', pady=2)
        self.field_read_label.pack(fill='x', pady=2)
        self.status_read_label.pack(fill='x', pady=2)
        
        # Temperature Control Section
        temp_control_frame = ttk.LabelFrame(main_frame, text="Temperature Control (K)", padding="10")
        temp_control_frame.grid(row=2, column=0, padx=5, pady=10, sticky="ew")

        ttk.Label(temp_control_frame, text="Set Point (K):").grid(row=0, column=0, padx=5, pady=5, sticky='w')
        self.temp_sp_entry = ttk.Entry(temp_control_frame, width=8)
        self.temp_sp_entry.insert(0, "10.0")
        self.temp_sp_entry.grid(row=0, column=1, padx=5, pady=5, sticky='e')

        ttk.Label(temp_control_frame, text="Rate (K/min):").grid(row=1, column=0, padx=5, pady=5, sticky='w')
        self.temp_rate_entry = ttk.Entry(temp_control_frame, width=8)
        self.temp_rate_entry.insert(0, "5.0")
        self.temp_rate_entry.grid(row=1, column=1, padx=5, pady=5, sticky='e')

        self.temp_set_button = ttk.Button(temp_control_frame, text="SET TEMP", command=self.set_temperature)
        self.temp_set_button.grid(row=2, column=0, columnspan=2, pady=10, sticky="ew")

        # Field Control Section
        field_control_frame = ttk.LabelFrame(main_frame, text="Field Control (Oe)", padding="10")
        field_control_frame.grid(row=2, column=1, padx=5, pady=10, sticky="ew")

        ttk.Label(field_control_frame, text="Set Point (Oe):").grid(row=0, column=0, padx=5, pady=5, sticky='w')
        self.field_sp_entry = ttk.Entry(field_control_frame, width=8)
        self.field_sp_entry.insert(0, "5000")
        self.field_sp_entry.grid(row=0, column=1, padx=5, pady=5, sticky='e')

        ttk.Label(field_control_frame, text="Rate (Oe/s):").grid(row=1, column=0, padx=5, pady=5, sticky='w')
        self.field_rate_entry = ttk.Entry(field_control_frame, width=8)
        self.field_rate_entry.insert(0, "100")
        self.field_rate_entry.grid(row=1, column=1, padx=5, pady=5, sticky='e')

        self.field_set_button = ttk.Button(field_control_frame, text="SET FIELD", command=self.set_field)
        self.field_set_button.grid(row=2, column=0, columnspan=2, pady=10, sticky="ew")

        # Wait Button
        self.wait_button = ttk.Button(main_frame, text="Wait for Temp & Field Stability (5s timeout)", 
                                       command=self.wait_for_stability, style="TButton")
        self.wait_button.grid(row=3, column=0, columnspan=2, pady=10, sticky="ew")

        master.protocol("WM_DELETE_WINDOW", self.on_closing)

    def connect_to_server(self):
        """Attempts to connect the MultiPyVu client with retries."""
        max_retries = 3
        retry_delay = 1  # seconds
        
        for attempt in range(max_retries):
            try:
                logging.info(f"Attempting connection to server... (Attempt {attempt + 1}/{max_retries})")
                self.client = mpv.Client(host=SERVER_HOST, port=SERVER_PORT)
                self.client.open()
                
                # If open() succeeds, we are connected
                self.is_connected = True
                self.conn_label.config(text=f"Connected to {SERVER_HOST}:{SERVER_PORT}", foreground="green")
                logging.info("Successfully connected to MultiPyVu Server.")
                
                # Start the background status updater thread
                self.status_updater_thread = threading.Thread(target=self.update_status_loop, daemon=True)
                self.status_updater_thread.start()
                return

            except mpv.MultiPyVuError as e:
                # This catches connection refused, server not running, or server full
                logging.warning(f"Connection attempt failed: {e}")
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                else:
                    # After final failure, show error
                    messagebox.showerror("Connection Error", 
                                         f"Failed to connect to MultiPyVu Server on {SERVER_HOST}:{SERVER_PORT} after {max_retries} attempts.\n"
                                         f"Please ensure opticool_server.py is running with '--scaffold'.\nError: {e}")
            except Exception as e:
                messagebox.showerror("Fatal Error", f"An unexpected error occurred during connection: {e}")
                logging.critical(f"Unexpected error: {e}")
                break

    def update_status_loop(self):
        """Runs in a background thread to continuously fetch and display cryostat status."""
        while self.is_connected:
            try:
                # Use lock to prevent status readback during a heavy command operation
                if not self.running_command.locked():
                    temp, temp_status = self.client.get_temperature()
                    field, field_status = self.client.get_field()
                    
                    # Update GUI elements safely on the main thread
                    self.master.after(0, lambda t=temp, ts=temp_status, f=field, fs=field_status: 
                                      self.update_gui_readouts(t, ts, f, fs))
                
                time.sleep(1) # Poll every 1 second
            
            except mpv.MultiPyVuError as e:
                logging.error(f"Status read failed: {e}")
                self.master.after(0, lambda: self.handle_disconnect(e))
                break
            except Exception:
                # Silently catch exceptions during polling to prevent thread crash
                pass

    def update_gui_readouts(self, temp, temp_status, field, field_status):
        """Updates the labels on the GUI."""
        self.temp_read_label.config(text=f"Temperature: {temp:.3f} K ({temp_status})")
        self.field_read_label.config(text=f"Field: {field:.1f} Oe ({field_status})")
        
        # Combine statuses for a general system status display
        system_status = "STABLE" if "Stable" in temp_status and "Stable" in field_status else "RAMPING/WAITING"
        self.status_read_label.config(text=f"System Status: {system_status}")

    def set_temperature(self):
        """Handles the SET TEMP button click."""
        if not self.is_connected: return
        
        try:
            sp = float(self.temp_sp_entry.get())
            rate = float(self.temp_rate_entry.get())
            
            # Use a fast-settle approach mode
            approach = self.client.temperature.approach_mode.fast_settle

            def command_thread():
                with self.running_command:
                    self.client.set_temperature(sp, rate, approach)
                    self.master.after(0, lambda: messagebox.showinfo("Command Sent", f"Set Temp to {sp} K at {rate} K/min."))
            
            threading.Thread(target=command_thread, daemon=True).start()

        except ValueError:
            messagebox.showerror("Input Error", "Temperature and Rate must be valid numbers.")
        except mpv.MultiPyVuError as e:
            messagebox.showerror("Command Error", f"MultiPyVu Error sending command: {e}")

    def set_field(self):
        """Handles the SET FIELD button click."""
        if not self.is_connected: return
        
        try:
            sp = float(self.field_sp_entry.get())
            rate = float(self.field_rate_entry.get())
            
            # Use linear approach mode
            approach = self.client.field.approach_mode.linear

            def command_thread():
                with self.running_command:
                    self.client.set_field(sp, rate, approach)
                    self.master.after(0, lambda: messagebox.showinfo("Command Sent", f"Set Field to {sp} Oe at {rate} Oe/s."))

            threading.Thread(target=command_thread, daemon=True).start()
            
        except ValueError:
            messagebox.showerror("Input Error", "Field and Rate must be valid numbers.")
        except mpv.MultiPyVuError as e:
            messagebox.showerror("Command Error", f"MultiPyVu Error sending command: {e}")
            
    def wait_for_stability(self):
        """Handles the WAIT button click, using a short timeout for quick testing."""
        if not self.is_connected: return

        # Set a 5 second timeout for quick testing in simulation
        TIMEOUT_SEC = 5 
        
        # Bitmask to wait for both Temperature and Field
        bitmask = self.client.temperature.waitfor | self.client.field.waitfor

        def command_thread():
            self.wait_button.config(state=tk.DISABLED, text="WAITING... (Polling Status)")
            logging.info(f"Starting wait_for command with {TIMEOUT_SEC}s timeout...")
            
            try:
                with self.running_command:
                    # Delay=0, Timeout=TIMEOUT_SEC, Bitmask=Temp|Field
                    self.client.wait_for(0, TIMEOUT_SEC, bitmask)
                    result_msg = "Stabilization Achieved within timeout!"
            except mpv.MultiPyVuError as e:
                # In scaffolding, a timeout often occurs quickly.
                result_msg = f"Wait Timeout (Expected in Scaffold Mode): {e}"
            except Exception as e:
                result_msg = f"Unexpected error during wait: {e}"

            logging.info(f"Wait command finished. Result: {result_msg}")
            self.master.after(0, lambda: self.wait_button.config(state=tk.NORMAL, text="Wait for Temp & Field Stability (5s timeout)"))
            self.master.after(0, lambda: messagebox.showinfo("Wait Result", result_msg))

        threading.Thread(target=command_thread, daemon=True).start()

    def handle_disconnect(self, error):
        """Cleans up and updates the GUI on a server disconnect."""
        self.is_connected = False
        self.conn_label.config(text="DISCONNECTED (Server Error)", foreground="red")
        if self.client:
            self.client.close_client()
        messagebox.showerror("Connection Lost", f"Lost connection to the MultiPyVu server.\nError: {error}")

    def on_closing(self):
        """Handles application closing."""
        if self.is_connected and self.client:
            self.client.close_client()
            logging.info("Client connection closed.")
        self.is_connected = False
        self.master.destroy()

if __name__ == '__main__':
    root = tk.Tk()
    app = OptiCoolClientApp(root)
    root.mainloop()
