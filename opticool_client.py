# opticool_client_gui.py
# Updated OptiCool client GUI following MultiPyVu best practices
# Compatible with MultiPyVu 3.2.0+

import MultiPyVu as mpv
import tkinter as tk
from tkinter import messagebox, ttk
import threading
import time
import logging

# --- Configuration ---
SERVER_HOST = '127.0.0.1'
SERVER_PORT = 5001

logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - CLIENT - %(levelname)s - %(message)s'
)

class OptiCoolClientApp:
    def __init__(self, master):
        self.master = master
        master.title("OptiCool Client – MultiPyVu GUI")

        self.client = None
        self.is_connected = False
        self.status_updater_thread = None
        self.running_command = threading.Lock()
        self.reconnect_attempts = 0
        self.max_reconnect_attempts = 3

        self._build_ui(master)
        self.connect_to_server()

    # ------------------- UI -------------------
    def _build_ui(self, master):
        style = ttk.Style()
        style.configure("TFrame", background="#f5f5f7")
        style.configure("TLabel", background="#f5f5f7", font=("Segoe UI", 10))
        style.configure("TButton", font=("Segoe UI", 10, "bold"))
        style.configure("Status.TLabel", font=("Segoe UI", 11, "bold"))

        root = ttk.Frame(master, padding=10)
        root.pack(fill='both', expand=True)

        # Connection Status
        conn = ttk.LabelFrame(root, text="Connection", padding=10)
        conn.grid(row=0, column=0, columnspan=3, sticky='ew', pady=(0,10))
        self.conn_label = ttk.Label(
            conn, 
            text="Disconnected", 
            foreground="red", 
            style="Status.TLabel"
        )
        self.conn_label.pack(side='left', padx=5)
        ttk.Button(conn, text="Reconnect", command=self.connect_to_server).pack(side='right')

        # Readbacks Panel
        cryostat = ttk.LabelFrame(root, text="Cryostat Status", padding=10)
        cryostat.grid(row=1, column=0, sticky='nsew', padx=(0,10), pady=(0,10))
        
        self.temp_read = ttk.Label(cryostat, text="Temperature: -- K", font=("Consolas", 10))
        self.temp_status = ttk.Label(cryostat, text="Status: --", font=("Consolas", 9))
        self.field_read = ttk.Label(cryostat, text="Field: -- Oe", font=("Consolas", 10))
        self.field_status = ttk.Label(cryostat, text="Status: --", font=("Consolas", 9))
        self.system_status = ttk.Label(
            cryostat, 
            text="System: UNKNOWN", 
            font=("Segoe UI", 10, "bold")
        )
        
        self.temp_read.grid(row=0, column=0, sticky='w', pady=2)
        self.temp_status.grid(row=1, column=0, sticky='w', pady=2, padx=(10,0))
        self.field_read.grid(row=2, column=0, sticky='w', pady=2)
        self.field_status.grid(row=3, column=0, sticky='w', pady=2, padx=(10,0))
        ttk.Separator(cryostat, orient='horizontal').grid(row=4, column=0, sticky='ew', pady=5)
        self.system_status.grid(row=5, column=0, sticky='w', pady=2)

        # Temperature Control Panel
        tpanel = ttk.LabelFrame(root, text="Temperature Control", padding=10)
        tpanel.grid(row=1, column=1, sticky='nsew', padx=(0,10), pady=(0,10))
        
        ttk.Label(tpanel, text="Setpoint (K):").grid(row=0, column=0, sticky='w', pady=2)
        self.t_sp = ttk.Entry(tpanel, width=12)
        self.t_sp.insert(0, "300.0")
        self.t_sp.grid(row=0, column=1, padx=6, pady=2, sticky='e')
        
        ttk.Label(tpanel, text="Rate (K/min):").grid(row=1, column=0, sticky='w', pady=2)
        self.t_rate = ttk.Entry(tpanel, width=12)
        self.t_rate.insert(0, "10.0")
        self.t_rate.grid(row=1, column=1, padx=6, pady=2, sticky='e')
        
        ttk.Label(tpanel, text="Approach:").grid(row=2, column=0, sticky='w', pady=2)
        self.t_approach = ttk.Combobox(
            tpanel, 
            state='readonly', 
            values=["Fast Settle", "No Overshoot"],
            width=12
        )
        self.t_approach.current(0)
        self.t_approach.grid(row=2, column=1, padx=6, pady=2, sticky='e')
        
        ttk.Button(
            tpanel, 
            text="Set Temperature", 
            command=self.set_temperature
        ).grid(row=3, column=0, columnspan=2, sticky='ew', pady=(10,4))
        
        ttk.Button(
            tpanel, 
            text="Warm to 300 K", 
            command=lambda: self.quick_temp(300.0, 10.0)
        ).grid(row=4, column=0, columnspan=2, sticky='ew', pady=2)
        
        ttk.Button(
            tpanel, 
            text="Cool to 4 K", 
            command=lambda: self.quick_temp(4.0, 5.0)
        ).grid(row=5, column=0, columnspan=2, sticky='ew', pady=2)

        # Magnetic Field Control Panel
        fpanel = ttk.LabelFrame(root, text="Magnetic Field Control", padding=10)
        fpanel.grid(row=1, column=2, sticky='nsew', pady=(0,10))
        
        ttk.Label(fpanel, text="Setpoint (Oe):").grid(row=0, column=0, sticky='w', pady=2)
        self.f_sp = ttk.Entry(fpanel, width=12)
        self.f_sp.insert(0, "0.0")
        self.f_sp.grid(row=0, column=1, padx=6, pady=2, sticky='e')
        
        ttk.Label(fpanel, text="Rate (Oe/s):").grid(row=1, column=0, sticky='w', pady=2)
        self.f_rate = ttk.Entry(fpanel, width=12)
        self.f_rate.insert(0, "100.0")
        self.f_rate.grid(row=1, column=1, padx=6, pady=2, sticky='e')
        
        ttk.Label(fpanel, text="Approach:").grid(row=2, column=0, sticky='w', pady=2)
        self.f_approach = ttk.Combobox(
            fpanel, 
            state='readonly', 
            values=["Linear", "No Overshoot"],
            width=12
        )
        self.f_approach.current(0)
        self.f_approach.grid(row=2, column=1, padx=6, pady=2, sticky='e')
        
        ttk.Button(
            fpanel, 
            text="Set Field", 
            command=self.set_field
        ).grid(row=3, column=0, columnspan=2, sticky='ew', pady=(10,4))
        
        ttk.Button(
            fpanel, 
            text="Zero Field", 
            command=lambda: self.quick_field(0.0, 100.0)
        ).grid(row=4, column=0, columnspan=2, sticky='ew', pady=2)

        # Action Buttons
        actions = ttk.Frame(root, padding=0)
        actions.grid(row=2, column=0, columnspan=3, sticky='ew')
        
        self.wait_btn = ttk.Button(
            actions, 
            text="Wait for Stability (30s timeout)", 
            command=self.wait_for_stability
        )
        self.wait_btn.pack(side='left', expand=True, fill='x', padx=(0,6))
        
        self.abort_btn = ttk.Button(
            actions, 
            text="Halt All Ramps", 
            command=self.abort_ramps
        )
        self.abort_btn.pack(side='left', expand=True, fill='x')

        # Configure grid weights
        for c in range(3):
            root.columnconfigure(c, weight=1)
        root.rowconfigure(1, weight=1)

        self.master.protocol("WM_DELETE_WINDOW", self.on_closing)

    # ------------------- Connection -------------------
    def connect_to_server(self):
        """Connect to MultiPyVu server using context manager pattern"""
        if self.is_connected:
            logging.info("Already connected")
            return
            
        def connection_worker():
            error_message = None
            try:
                logging.info(f"Connecting to server at {SERVER_HOST}:{SERVER_PORT}...")
                
                # Create client (socket_timeout may not be available in all versions)
                try:
                    self.client = mpv.Client(
                        host=SERVER_HOST, 
                        port=SERVER_PORT,
                        socket_timeout=5
                    )
                except TypeError:
                    # Fallback for older versions without socket_timeout parameter
                    self.client = mpv.Client(host=SERVER_HOST, port=SERVER_PORT)
                
                self.client.open()
                
                # Test connection with a simple get
                _, _ = self.client.get_temperature()
                
                self.is_connected = True
                self.reconnect_attempts = 0
                
                self.master.after(0, lambda: self.conn_label.config(
                    text=f"Connected to {SERVER_HOST}:{SERVER_PORT}", 
                    foreground="green"
                ))
                logging.info("Connected successfully")
                
                # Start status polling
                if self.status_updater_thread is None or not self.status_updater_thread.is_alive():
                    self.status_updater_thread = threading.Thread(
                        target=self._poll_status_loop, 
                        daemon=True
                    )
                    self.status_updater_thread.start()
                    
            except mpv.MultiPyVuError as e:
                error_message = str(e)
                logging.error(f"MultiPyVu connection error: {e}")
                self.reconnect_attempts += 1
                
                if self.reconnect_attempts < self.max_reconnect_attempts:
                    self.master.after(2000, self.connect_to_server)
                    self.master.after(0, lambda: self.conn_label.config(
                        text=f"Retrying... ({self.reconnect_attempts}/{self.max_reconnect_attempts})",
                        foreground="orange"
                    ))
                else:
                    err_msg = error_message  # Capture for lambda
                    self.master.after(0, lambda: messagebox.showerror(
                        "Connection Failed",
                        f"Could not connect after {self.max_reconnect_attempts} attempts.\n\n"
                        f"Please ensure:\n"
                        f"1. MultiPyVu server is running (python -m MultiPyVu or with -s flag)\n"
                        f"2. Port {SERVER_PORT} is not blocked by firewall\n"
                        f"3. MultiVu is running (or server is in scaffold mode)\n\n"
                        f"Error: {err_msg}"
                    ))
                    
            except Exception as e:
                error_message = str(e)
                logging.exception("Unexpected connection error")
                err_msg = error_message  # Capture for lambda
                self.master.after(0, lambda: messagebox.showerror(
                    "Connection Error", 
                    f"Unexpected error: {err_msg}"
                ))
        
        threading.Thread(target=connection_worker, daemon=True).start()

    def _poll_status_loop(self):
        """Continuously poll instrument status"""
        while self.is_connected:
            try:
                if not self.running_command.locked():
                    temp, temp_stat = self.client.get_temperature()
                    field, field_stat = self.client.get_field()
                    
                    self.master.after(0, lambda t=temp, ts=temp_stat, f=field, fs=field_stat: 
                        self._update_readouts(t, ts, f, fs))
                
                time.sleep(1.0)
                
            except mpv.MultiPyVuError as e:
                logging.error(f"Status polling error: {e}")
                self.master.after(0, lambda: self._handle_disconnect(str(e)))
                break
                
            except Exception as e:
                logging.warning(f"Transient polling error: {e}")
                time.sleep(1.0)

    def _update_readouts(self, temp, temp_status, field, field_status):
        """Update GUI with current readings"""
        # Format temperature display
        self.temp_read.config(text=f"Temperature: {temp:.3f} K")
        self.temp_status.config(text=f"Status: {temp_status}")
        
        # Format field display
        self.field_read.config(text=f"Field: {field:.2f} Oe")
        self.field_status.config(text=f"Status: {field_status}")
        
        # Determine overall system status
        temp_str = str(temp_status).lower()
        field_str = str(field_status).lower()
        
        if 'stable' in temp_str and 'stable' in field_str:
            status_text = "System: STABLE"
            status_color = "green"
        elif 'tracking' in temp_str or 'tracking' in field_str:
            status_text = "System: TRACKING"
            status_color = "blue"
        elif any(x in temp_str for x in ['approach', 'ramp']) or any(x in field_str for x in ['approach', 'ramp']):
            status_text = "System: RAMPING"
            status_color = "orange"
        else:
            status_text = "System: UNKNOWN"
            status_color = "gray"
            
        self.system_status.config(text=status_text, foreground=status_color)

    # ------------------- Commands -------------------
    def set_temperature(self):
        """Set temperature with approach mode"""
        if not self.is_connected:
            messagebox.showwarning("Not Connected", "Please connect to server first")
            return
            
        try:
            setpoint = float(self.t_sp.get())
            rate = float(self.t_rate.get())
            
            # Map UI selection to enum
            approach_name = self.t_approach.get()
            if approach_name == "Fast Settle":
                approach = self.client.temperature.approach_mode.fast_settle
            elif approach_name == "No Overshoot":
                approach = self.client.temperature.approach_mode.no_overshoot
            else:
                approach = self.client.temperature.approach_mode.fast_settle
            
            def worker():
                try:
                    with self.running_command:
                        self.client.set_temperature(setpoint, rate, approach)
                    
                    self.master.after(0, lambda: messagebox.showinfo(
                        "Command Sent",
                        f"Temperature set to {setpoint:.2f} K\n"
                        f"Rate: {rate:.2f} K/min\n"
                        f"Mode: {approach_name}"
                    ))
                    
                except mpv.MultiPyVuError as e:
                    logging.error(f"Set temperature failed: {e}")
                    self.master.after(0, lambda: messagebox.showerror(
                        "Command Failed", 
                        f"Failed to set temperature:\n{e}"
                    ))
            
            threading.Thread(target=worker, daemon=True).start()
            
        except ValueError:
            messagebox.showerror("Invalid Input", "Temperature and rate must be valid numbers")

    def set_field(self):
        """Set magnetic field with approach mode"""
        if not self.is_connected:
            messagebox.showwarning("Not Connected", "Please connect to server first")
            return
            
        try:
            setpoint = float(self.f_sp.get())
            rate = float(self.f_rate.get())
            
            # Map UI selection to enum
            approach_name = self.f_approach.get()
            if approach_name == "Linear":
                approach = self.client.field.approach_mode.linear
            elif approach_name == "No Overshoot":
                approach = self.client.field.approach_mode.no_overshoot
            else:
                approach = self.client.field.approach_mode.linear
            
            def worker():
                try:
                    with self.running_command:
                        self.client.set_field(setpoint, rate, approach)
                    
                    self.master.after(0, lambda: messagebox.showinfo(
                        "Command Sent",
                        f"Field set to {setpoint:.2f} Oe\n"
                        f"Rate: {rate:.2f} Oe/s\n"
                        f"Mode: {approach_name}"
                    ))
                    
                except mpv.MultiPyVuError as e:
                    logging.error(f"Set field failed: {e}")
                    self.master.after(0, lambda: messagebox.showerror(
                        "Command Failed", 
                        f"Failed to set field:\n{e}"
                    ))
            
            threading.Thread(target=worker, daemon=True).start()
            
        except ValueError:
            messagebox.showerror("Invalid Input", "Field and rate must be valid numbers")

    def quick_temp(self, setpoint, rate):
        """Quick temperature preset"""
        self.t_sp.delete(0, tk.END)
        self.t_sp.insert(0, str(setpoint))
        self.t_rate.delete(0, tk.END)
        self.t_rate.insert(0, str(rate))
        self.set_temperature()

    def quick_field(self, setpoint, rate):
        """Quick field preset"""
        self.f_sp.delete(0, tk.END)
        self.f_sp.insert(0, str(setpoint))
        self.f_rate.delete(0, tk.END)
        self.f_rate.insert(0, str(rate))
        self.set_field()

    def wait_for_stability(self):
        """Wait for temperature and field to stabilize"""
        if not self.is_connected:
            messagebox.showwarning("Not Connected", "Please connect to server first")
            return
            
        TIMEOUT = 30  # seconds
        
        def worker():
            self.master.after(0, lambda: self.wait_btn.config(
                state=tk.DISABLED, 
                text=f"Waiting... ({TIMEOUT}s timeout)"
            ))
            
            try:
                # Use waitfor bitmask as documented
                bitmask = self.client.temperature.waitfor | self.client.field.waitfor
                
                with self.running_command:
                    self.client.wait_for(
                        delay=0,  # No extra delay after stable
                        timeout=TIMEOUT,
                        bitmask=bitmask
                    )
                
                result_msg = "System is stable!"
                result_type = "info"
                
            except mpv.MultiPyVuError as e:
                if "timeout" in str(e).lower():
                    result_msg = f"Timeout after {TIMEOUT}s\nSystem has not stabilized yet"
                else:
                    result_msg = f"Wait failed: {e}"
                result_type = "warning"
                
            finally:
                self.master.after(0, lambda: self.wait_btn.config(
                    state=tk.NORMAL,
                    text="Wait for Stability (30s timeout)"
                ))
                
                if result_type == "info":
                    self.master.after(0, lambda: messagebox.showinfo("Wait Complete", result_msg))
                else:
                    self.master.after(0, lambda: messagebox.showwarning("Wait Result", result_msg))
        
        threading.Thread(target=worker, daemon=True).start()

    def abort_ramps(self):
        """
        Halt temperature and field ramps by setting current values as setpoints.
        MultiPyVu doesn't have a native abort, so we read current values and set them.
        """
        if not self.is_connected:
            messagebox.showwarning("Not Connected", "Please connect to server first")
            return
            
        def worker():
            try:
                with self.running_command:
                    # Get current values
                    temp, _ = self.client.get_temperature()
                    field, _ = self.client.get_field()
                    
                    # Set current values with fast rates to halt ramps
                    self.client.set_temperature(
                        temp, 
                        10.0,  # Fast rate
                        self.client.temperature.approach_mode.fast_settle
                    )
                    
                    self.client.set_field(
                        field,
                        200.0,  # Fast rate
                        self.client.field.approach_mode.linear
                    )
                
                self.master.after(0, lambda: messagebox.showinfo(
                    "Ramps Halted",
                    f"Temperature locked at {temp:.2f} K\n"
                    f"Field locked at {field:.2f} Oe"
                ))
                
            except mpv.MultiPyVuError as e:
                logging.error(f"Abort failed: {e}")
                self.master.after(0, lambda: messagebox.showerror(
                    "Abort Failed",
                    f"Could not halt ramps:\n{e}"
                ))
        
        threading.Thread(target=worker, daemon=True).start()

    # ------------------- Cleanup -------------------
    def _handle_disconnect(self, error_msg):
        """Handle disconnection from server"""
        self.is_connected = False
        self.conn_label.config(text="DISCONNECTED", foreground="red")
        
        try:
            if self.client:
                self.client.close_client()
        except:
            pass
        
        messagebox.showerror(
            "Connection Lost",
            f"Lost connection to server.\n\n{error_msg}\n\n"
            f"Click Reconnect to try again."
        )

    def on_closing(self):
        """Clean shutdown"""
        self.is_connected = False
        
        try:
            if self.client:
                self.client.close_client()
                logging.info("Client closed")
        except Exception as e:
            logging.error(f"Error closing client: {e}")
        finally:
            self.master.destroy()


if __name__ == '__main__':
    root = tk.Tk()
    root.geometry("900x450")
    root.resizable(True, True)
    
    app = OptiCoolClientApp(root)
    
    logging.info("OptiCool Client GUI started")
    root.mainloop()