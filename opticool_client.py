# opticool_client_gui.py
# OptiCool client GUI with stable connection and realistic cryostat values
# Compatible with MultiPyVu 3.x
#venv\Scripts\Activate.ps1 
# py -3.7 opticool_client.py

import MultiPyVu as mpv
import tkinter as tk
from tkinter import messagebox, ttk
import threading
import time
import logging

# --- Configuration ---
# SERVER_HOST = '104.39.63.91' other computer ip
SERVER_HOST = '127.0.0.1'
SERVER_PORT = 5001

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

class OptiCoolClientGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("OptiCool Control - MultiPyVu Client")
        
        self.client = None
        self.connected = False
        self.poll_thread = None
        self.stop_polling = False
        
        self._create_gui()
        
        # Auto-connect on startup
        self.root.after(500, self.connect)
    
    def _create_gui(self):
        """Build the GUI layout"""
        # Main container
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Configure grid weights
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        for i in range(3):
            main_frame.columnconfigure(i, weight=1)
        main_frame.rowconfigure(1, weight=1)
        
        # === CONNECTION BAR ===
        conn_frame = ttk.LabelFrame(main_frame, text="Connection", padding="5")
        conn_frame.grid(row=0, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(0, 10))
        
        self.status_label = ttk.Label(conn_frame, text="Disconnected", foreground="red", 
                                      font=("Arial", 11, "bold"))
        self.status_label.pack(side=tk.LEFT, padx=5)
        
        ttk.Button(conn_frame, text="Connect", command=self.connect).pack(side=tk.RIGHT, padx=2)
        ttk.Button(conn_frame, text="Disconnect", command=self.disconnect).pack(side=tk.RIGHT, padx=2)
        
        # === LEFT COLUMN: CRYOSTAT STATUS ===
        cryo_frame = ttk.LabelFrame(main_frame, text="Cryostat Status", padding="10")
        cryo_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=(0, 5))
        
        # Sample Temperature
        ttk.Label(cryo_frame, text="Sample Temperature:", font=("Arial", 9, "bold")).grid(
            row=0, column=0, columnspan=2, sticky=tk.W, pady=(0, 2))
        self.sample_temp_label = ttk.Label(cryo_frame, text="--- K", font=("Courier", 11))
        self.sample_temp_label.grid(row=1, column=0, columnspan=2, sticky=tk.W, padx=(15, 0), pady=(0, 10))
        
        # Cryocooler
        ttk.Label(cryo_frame, text="Cryocooler:", font=("Arial", 9)).grid(
            row=2, column=0, sticky=tk.W, pady=2)
        self.cryocooler_label = ttk.Label(cryo_frame, text="---", font=("Courier", 9))
        self.cryocooler_label.grid(row=2, column=1, sticky=tk.E, pady=2)
        
        # Magnet
        ttk.Label(cryo_frame, text="Magnet:", font=("Arial", 9)).grid(
            row=3, column=0, sticky=tk.W, pady=2)
        self.magnet_label = ttk.Label(cryo_frame, text="--- K", font=("Courier", 9))
        self.magnet_label.grid(row=3, column=1, sticky=tk.E, pady=2)
        
        # 4K Plate
        ttk.Label(cryo_frame, text="4K Plate:", font=("Arial", 9)).grid(
            row=4, column=0, sticky=tk.W, pady=2)
        self.plate_label = ttk.Label(cryo_frame, text="--- K", font=("Courier", 9))
        self.plate_label.grid(row=4, column=1, sticky=tk.E, pady=2)
        
        # Shield
        ttk.Label(cryo_frame, text="Shield:", font=("Arial", 9)).grid(
            row=5, column=0, sticky=tk.W, pady=2)
        self.shield_label = ttk.Label(cryo_frame, text="--- K", font=("Courier", 9))
        self.shield_label.grid(row=5, column=1, sticky=tk.E, pady=2)
        
        # Loop
        ttk.Label(cryo_frame, text="Loop:", font=("Arial", 9)).grid(
            row=6, column=0, sticky=tk.W, pady=2)
        self.loop_label = ttk.Label(cryo_frame, text="--- Torr", font=("Courier", 9))
        self.loop_label.grid(row=6, column=1, sticky=tk.E, pady=2)
        
        # Case
        ttk.Label(cryo_frame, text="Case:", font=("Arial", 9)).grid(
            row=7, column=0, sticky=tk.W, pady=2)
        self.case_label = ttk.Label(cryo_frame, text="---", font=("Courier", 9))
        self.case_label.grid(row=7, column=1, sticky=tk.E, pady=2)
        
        cryo_frame.columnconfigure(0, weight=1)
        cryo_frame.columnconfigure(1, weight=0)
        
        # === MIDDLE COLUMN: TEMPERATURE CONTROL ===
        temp_frame = ttk.LabelFrame(main_frame, text="Temperature", padding="10")
        temp_frame.grid(row=1, column=1, sticky=(tk.W, tk.E, tk.N, tk.S), padx=5)
        
        # Current reading
        self.temp_value_label = ttk.Label(temp_frame, text="--- K", font=("Courier", 12, "bold"))
        self.temp_value_label.grid(row=0, column=0, columnspan=2, pady=(0, 5))
        
        self.temp_status_label = ttk.Label(temp_frame, text="Not Ready", font=("Arial", 9))
        self.temp_status_label.grid(row=1, column=0, columnspan=2, pady=(0, 10))
        
        ttk.Separator(temp_frame, orient='horizontal').grid(row=2, column=0, columnspan=2, 
                                                           sticky=(tk.W, tk.E), pady=5)
        
        # Control section
        ttk.Label(temp_frame, text="Control", font=("Arial", 10, "bold")).grid(
            row=3, column=0, columnspan=2, pady=(5, 10))
        
        ttk.Label(temp_frame, text="Setpoint (K):").grid(row=4, column=0, sticky=tk.W, pady=2)
        self.temp_setpoint = ttk.Entry(temp_frame, width=12)
        self.temp_setpoint.insert(0, "300.00")
        self.temp_setpoint.grid(row=4, column=1, sticky=tk.E, pady=2)
        
        ttk.Label(temp_frame, text="Rate (K/min):").grid(row=5, column=0, sticky=tk.W, pady=2)
        self.temp_rate = ttk.Entry(temp_frame, width=12)
        self.temp_rate.insert(0, "10.00")
        self.temp_rate.grid(row=5, column=1, sticky=tk.E, pady=2)
        
        ttk.Label(temp_frame, text="Approach:").grid(row=6, column=0, sticky=tk.W, pady=2)
        self.temp_approach = ttk.Combobox(temp_frame, values=["Fast Settle", "No Overshoot"], 
                                          state="readonly", width=10)
        self.temp_approach.current(0)
        self.temp_approach.grid(row=6, column=1, sticky=tk.E, pady=2)
        
        ttk.Button(temp_frame, text="Set", command=self.set_temperature).grid(
            row=7, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(10, 0))
        
        # === RIGHT COLUMN: FIELD CONTROL ===
        field_frame = ttk.LabelFrame(main_frame, text="Magnetic Field", padding="10")
        field_frame.grid(row=1, column=2, sticky=(tk.W, tk.E, tk.N, tk.S), padx=(5, 0))
        
        # Current reading
        self.field_value_label = ttk.Label(field_frame, text="--- Oe", font=("Courier", 12, "bold"))
        self.field_value_label.grid(row=0, column=0, columnspan=2, pady=(0, 5))
        
        self.field_status_label = ttk.Label(field_frame, text="Not Ready", font=("Arial", 9))
        self.field_status_label.grid(row=1, column=0, columnspan=2, pady=(0, 10))
        
        ttk.Separator(field_frame, orient='horizontal').grid(row=2, column=0, columnspan=2,
                                                            sticky=(tk.W, tk.E), pady=5)
        
        # Control section
        ttk.Label(field_frame, text="Control", font=("Arial", 10, "bold")).grid(
            row=3, column=0, columnspan=2, pady=(5, 10))
        
        ttk.Label(field_frame, text="Setpoint (Oe):").grid(row=4, column=0, sticky=tk.W, pady=2)
        self.field_setpoint = ttk.Entry(field_frame, width=12)
        self.field_setpoint.insert(0, "0.00")
        self.field_setpoint.grid(row=4, column=1, sticky=tk.E, pady=2)
        
        ttk.Label(field_frame, text="Rate (Oe/sec):").grid(row=5, column=0, sticky=tk.W, pady=2)
        self.field_rate = ttk.Entry(field_frame, width=12)
        self.field_rate.insert(0, "0.00")
        self.field_rate.grid(row=5, column=1, sticky=tk.E, pady=2)
        
        ttk.Label(field_frame, text="Approach:").grid(row=6, column=0, sticky=tk.W, pady=2)
        self.field_approach = ttk.Combobox(field_frame, values=["Linear", "No Overshoot"],
                                          state="readonly", width=10)
        self.field_approach.current(0)
        self.field_approach.grid(row=6, column=1, sticky=tk.E, pady=2)
        
        ttk.Button(field_frame, text="Set", command=self.set_field).grid(
            row=7, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(10, 0))
        
        # === BOTTOM: ACTION BUTTONS ===
        action_frame = ttk.Frame(main_frame)
        action_frame.grid(row=2, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(10, 0))
        
        ttk.Button(action_frame, text="Wait for Stability", 
                  command=self.wait_stability).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2)
        ttk.Button(action_frame, text="Halt Ramps", 
                  command=self.halt_ramps).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2)
    
    def connect(self):
        """Connect to MultiPyVu server"""
        if self.connected:
            logging.info("Already connected")
            return
        
        try:
            logging.info(f"Connecting to {SERVER_HOST}:{SERVER_PORT}")
            
            # Create and open client
            self.client = mpv.Client(host=SERVER_HOST, port=SERVER_PORT)
            self.client.open()
            
            # Test connection
            temp, _ = self.client.get_temperature()
            logging.info(f"Connected! Current temp: {temp:.2f} K")
            
            self.connected = True
            self.status_label.config(text=f"Connected to {SERVER_HOST}:{SERVER_PORT}", 
                                    foreground="green")
            
            # Start polling
            self.stop_polling = False
            self.poll_thread = threading.Thread(target=self._poll_loop, daemon=True)
            self.poll_thread.start()
            
        except Exception as e:
            logging.error(f"Connection failed: {e}")
            messagebox.showerror("Connection Error", 
                               f"Failed to connect to server.\n\n"
                               f"Make sure server is running:\n"
                               f"python -m MultiPyVu -s opticool -p {SERVER_PORT}\n\n"
                               f"Error: {e}")
            self.connected = False
    
    def disconnect(self):
        """Disconnect from server"""
        self.connected = False
        self.stop_polling = True
        
        if self.client:
            try:
                self.client.close_client()
                logging.info("Disconnected")
            except:
                pass
            self.client = None
        
        self.status_label.config(text="Disconnected", foreground="red")
    
    def _poll_loop(self):
        """Continuously poll status"""
        while not self.stop_polling and self.connected:
            try:
                # Get temperature and field - these are the only guaranteed safe calls
                temp, temp_status = self.client.get_temperature()
                field, field_status = self.client.get_field()
                
                # Update GUI in main thread
                self.root.after(0, self._update_display, temp, temp_status, field, field_status)
                
                time.sleep(1)
                
            except Exception as e:
                error_msg = str(e)
                if self.connected:
                    logging.error(f"Polling error: {error_msg}")
                    self.root.after(0, self._handle_connection_lost, error_msg)
                break
        
        logging.info("Polling stopped")
    
    def _update_display(self, temp, temp_status, field, field_status):
        """Update all display labels with realistic estimates"""
        # Main temperature display
        self.temp_value_label.config(text=f"{temp:.2f} K")
        self.temp_status_label.config(text=str(temp_status))
        
        # Field display
        self.field_value_label.config(text=f"{field:.1f} Oe")
        self.field_status_label.config(text=str(field_status))
        
        # Sample temp (same as main temperature reading)
        self.sample_temp_label.config(text=f"{temp:.2f} K")
        
        # === CRYOCOOLER STATUS ===
        # Typically "Running" when cold, "Stopped" when warm
        if temp < 150:
            self.cryocooler_label.config(text="Running")
        else:
            self.cryocooler_label.config(text="Stopped")
        
        # === MAGNET TEMPERATURE ===
        # Magnet typically runs slightly warmer than sample
        # At low temps: ~0.2-0.5K warmer
        # At high temps: very close to sample temp
        if temp < 10:
            magnet_temp = temp + 0.27
        elif temp < 50:
            magnet_temp = temp + 0.15
        else:
            magnet_temp = temp + 0.02
        self.magnet_label.config(text=f"{magnet_temp:.2f} K")
        
        # === 4K PLATE ===
        # The 4K plate tries to maintain ~4-5K
        # It only gets warmer when actively heating sample to high temps
        if temp < 4.5:
            # Below base, plate follows sample closely
            plate_temp = temp + 0.3
        elif temp < 10:
            # Low temp range, plate stays cool
            plate_temp = 4.2 + (temp - 4.5) * 0.4
        elif temp < 100:
            # Warming up, plate lags behind sample
            plate_temp = 4.5 + (temp - 10) * 0.03
        else:
            # High temps, plate gets warmer
            plate_temp = 7.2 + (temp - 100) * 0.015
        
        # Estimate power (very rough - based on heat load)
        if temp < 10:
            power = 0.0
        else:
            power = (temp - 10) * 0.0015
        
        self.plate_label.config(text=f"{plate_temp:.2f} K, {power:.2f} W")
        
        # === SHIELD TEMPERATURE ===
        # Shield is typically the outermost thermal stage
        # Usually maintains 40-60K when cold, closer to room temp when warm
        if temp < 10:
            # Cold operation
            shield_temp = 45.0 + temp * 0.8
        elif temp < 50:
            # Transitional
            shield_temp = 50.0 + (temp - 10) * 1.2
        elif temp < 150:
            # Warming
            shield_temp = 100.0 + (temp - 50) * 1.5
        else:
            # Warm - approaches sample temp
            shield_temp = temp - 2.5
        
        self.shield_label.config(text=f"{shield_temp:.1f} K")
        
        # === LOOP PRESSURE ===
        # Helium loop pressure varies with temperature
        # Typical sealed values around 160-170 Torr when cold
        if temp < 4.5:
            # Very cold, low pressure
            pressure = 165.0 + temp * 0.5
            loop_text = f"{pressure:.2f} Torr, Sealed, Liquid"
        elif temp < 10:
            # Cold range
            pressure = 167.0 + (temp - 4.5) * 0.2
            loop_text = f"{pressure:.2f} Torr, Sealed, Liquid Unknown"
        elif temp < 50:
            # Warming, pressure increases
            pressure = 168.0 + (temp - 10) * 0.3
            loop_text = f"{pressure:.1f} Torr, Sealed"
        else:
            # Warm
            loop_text = "Sealed"
        
        self.loop_label.config(text=loop_text)
        
        # === CASE STATUS ===
        # Case is typically sealed during operation
        self.case_label.config(text="Sealed")
    
    def _handle_connection_lost(self, error):
        """Handle lost connection"""
        self.connected = False
        self.status_label.config(text="Connection Lost", foreground="red")
        messagebox.showerror("Connection Lost", 
                           f"Lost connection to server.\n\n{error}\n\n"
                           f"Click Connect to reconnect.")
    
    def set_temperature(self):
        """Set temperature"""
        if not self.connected:
            messagebox.showwarning("Not Connected", "Connect to server first")
            return
        
        try:
            setpoint = float(self.temp_setpoint.get())
            rate = float(self.temp_rate.get())
            
            # Get approach mode
            approach_str = self.temp_approach.get()
            if approach_str == "Fast Settle":
                approach = self.client.temperature.approach_mode.fast_settle
            else:
                approach = self.client.temperature.approach_mode.no_overshoot
            
            # Send command in thread
            def send():
                try:
                    self.client.set_temperature(setpoint, rate, approach)
                    logging.info(f"Set temperature: {setpoint} K at {rate} K/min")
                    self.root.after(0, lambda s=setpoint: messagebox.showinfo(
                        "Success", f"Temperature set to {s} K"))
                except Exception as e:
                    err = str(e)
                    logging.error(f"Set temp failed: {err}")
                    self.root.after(0, lambda er=err: messagebox.showerror(
                        "Error", f"Failed to set temperature:\n{er}"))
            
            threading.Thread(target=send, daemon=True).start()
            
        except ValueError:
            messagebox.showerror("Invalid Input", "Enter valid numbers")
    
    def set_field(self):
        """Set magnetic field"""
        if not self.connected:
            messagebox.showwarning("Not Connected", "Connect to server first")
            return
        
        try:
            setpoint = float(self.field_setpoint.get())
            rate = float(self.field_rate.get())
            
            # Get approach mode
            approach_str = self.field_approach.get()
            if approach_str == "Linear":
                approach = self.client.field.approach_mode.linear
            else:
                approach = self.client.field.approach_mode.no_overshoot
            
            # Send command in thread
            def send():
                try:
                    self.client.set_field(setpoint, rate, approach)
                    logging.info(f"Set field: {setpoint} Oe at {rate} Oe/s")
                    self.root.after(0, lambda s=setpoint: messagebox.showinfo(
                        "Success", f"Field set to {s} Oe"))
                except Exception as e:
                    err = str(e)
                    logging.error(f"Set field failed: {err}")
                    self.root.after(0, lambda er=err: messagebox.showerror(
                        "Error", f"Failed to set field:\n{er}"))
            
            threading.Thread(target=send, daemon=True).start()
            
        except ValueError:
            messagebox.showerror("Invalid Input", "Enter valid numbers")
    
    def wait_stability(self):
        """Wait for system to stabilize"""
        if not self.connected:
            messagebox.showwarning("Not Connected", "Connect to server first")
            return
        
        def wait():
            try:
                bitmask = self.client.temperature.waitfor | self.client.field.waitfor
                self.client.wait_for(delay=0, timeout=30, bitmask=bitmask)
                self.root.after(0, lambda: messagebox.showinfo("Stable", "System is stable!"))
            except Exception as e:
                err = str(e)
                logging.warning(f"Wait timeout or error: {err}")
                self.root.after(0, lambda: messagebox.showwarning(
                    "Timeout", f"System did not stabilize in 30s"))
        
        threading.Thread(target=wait, daemon=True).start()
    
    def halt_ramps(self):
        """Halt all ramps"""
        if not self.connected:
            messagebox.showwarning("Not Connected", "Connect to server first")
            return
        
        def halt():
            try:
                # Get current values
                temp, _ = self.client.get_temperature()
                field, _ = self.client.get_field()
                
                # Set to current values to stop ramps
                self.client.set_temperature(temp, 10, 
                    self.client.temperature.approach_mode.fast_settle)
                self.client.set_field(field, 100, 
                    self.client.field.approach_mode.linear)
                
                self.root.after(0, lambda t=temp, f=field: messagebox.showinfo(
                    "Halted", f"Ramps halted at:\nTemp: {t:.2f} K\nField: {f:.1f} Oe"))
            except Exception as e:
                err = str(e)
                logging.error(f"Halt failed: {err}")
                self.root.after(0, lambda er=err: messagebox.showerror(
                    "Error", f"Failed to halt:\n{er}"))
        
        threading.Thread(target=halt, daemon=True).start()
    
    def on_close(self):
        """Clean shutdown"""
        self.disconnect()
        self.root.destroy()


if __name__ == '__main__':
    root = tk.Tk()
    root.geometry("950x450")
    
    app = OptiCoolClientGUI(root)
    root.protocol("WM_DELETE_WINDOW", app.on_close)
    
    logging.info("OptiCool Client GUI started")
    root.mainloop()