import asyncio
import tkinter as tk
from tkinter import ttk
import threading
from bleak import BleakScanner
from datetime import datetime
import json
import os

class GoveeThermometerGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Govee H5104 Multi-Thermometer Reader")
        self.root.geometry("900x700")
        
        # Fix DPI scaling issues for crisp display
        try:
            from ctypes import windll
            windll.shcore.SetProcessDpiAwareness(1)
        except:
            pass
        
        # Configure high DPI support
        self.root.tk.call('tk', 'scaling', 1.0)
        
        # Scanner state
        self.scanner = None
        self.scanning = False
        self.scan_task = None
        
        # Device data - dictionary to store multiple devices
        self.devices = {}  # key: device_address, value: device_data dict
        
        # Custom device names - dictionary to store user-assigned names
        self.device_names = {}  # key: device_address, value: custom_name
        
        # File to store device names persistently - force it to be in the same directory as the script
        script_dir = os.path.dirname(os.path.abspath(__file__))
        self.names_file = os.path.join(script_dir, "thermometer_names.json")
        
        # Load saved device names
        self.load_device_names()
        
        self.setup_ui()
        
    def load_device_names(self):
        """Load device names from file"""
        try:
            if os.path.exists(self.names_file):
                with open(self.names_file, 'r', encoding='utf-8') as f:
                    self.device_names = json.load(f)
                print(f"Loaded {len(self.device_names)} saved device names")
            else:
                print("No saved device names found")
        except Exception as e:
            print(f"Error loading device names: {e}")
            self.device_names = {}
    
    def save_device_names(self):
        """Save device names to file"""
        try:
            with open(self.names_file, 'w', encoding='utf-8') as f:
                json.dump(self.device_names, f, indent=2, ensure_ascii=False)
            print(f"Saved {len(self.device_names)} device names")
        except Exception as e:
            print(f"Error saving device names: {e}")
        
    def setup_ui(self):
        # Configure style for better appearance
        style = ttk.Style()
        style.theme_use('clam')  # Use a modern theme
        
        # Main frame with better padding
        main_frame = ttk.Frame(self.root, padding="25")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Title with better font
        title_label = ttk.Label(main_frame, text="Govee H5104 Multi-Thermometer Reader", 
                               font=("Segoe UI", 18, "bold"))
        title_label.grid(row=0, column=0, columnspan=2, pady=(0, 25))
        
        # Control buttons with better spacing
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=1, column=0, columnspan=2, pady=(0, 20))
        
        # Configure button style
        style.configure('Action.TButton', font=('Segoe UI', 10))
        
        self.scan_button = ttk.Button(button_frame, text="Start Scanning", 
                                     command=self.toggle_scanning, 
                                     style='Action.TButton', width=15)
        self.scan_button.grid(row=0, column=0, padx=(0, 15))
        
        self.refresh_button = ttk.Button(button_frame, text="Refresh Once", 
                                        command=self.refresh_once,
                                        style='Action.TButton', width=15)
        self.refresh_button.grid(row=0, column=1, padx=(0, 15))
        
        self.clear_button = ttk.Button(button_frame, text="Clear All", 
                                      command=self.clear_devices,
                                      style='Action.TButton', width=15)
        self.clear_button.grid(row=0, column=2, padx=(0, 15))
        
        self.names_button = ttk.Button(button_frame, text="Manage Names", 
                                      command=self.open_names_dialog,
                                      style='Action.TButton', width=15)
        self.names_button.grid(row=0, column=3)
        
        # Status label with better font
        self.status_label = ttk.Label(main_frame, text="Click 'Start Scanning' to begin", 
                                     font=("Segoe UI", 11), foreground="gray")
        self.status_label.grid(row=2, column=0, columnspan=2, pady=(0, 15))
        
        # Devices frame with scrollbar - improved styling
        devices_frame = ttk.LabelFrame(main_frame, text="Detected Devices", padding="15")
        devices_frame.grid(row=3, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 15))
        
        # Create canvas and scrollbar for scrollable content with better styling
        canvas_frame = ttk.Frame(devices_frame)
        canvas_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        self.canvas = tk.Canvas(canvas_frame, bg="#f8f9fa", highlightthickness=0, bd=0)
        scrollbar = ttk.Scrollbar(canvas_frame, orient="vertical", command=self.canvas.yview)
        self.scrollable_frame = ttk.Frame(self.canvas)
        
        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )
        
        self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=scrollbar.set)
        
        self.canvas.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        
        canvas_frame.columnconfigure(0, weight=1)
        canvas_frame.rowconfigure(0, weight=1)
        devices_frame.columnconfigure(0, weight=1)
        devices_frame.rowconfigure(0, weight=1)
        
        # No devices message with better styling
        self.no_devices_label = ttk.Label(self.scrollable_frame, 
                                         text="No devices detected yet...", 
                                         font=("Segoe UI", 12), foreground="#6c757d")
        self.no_devices_label.grid(row=0, column=0, pady=80)
        
        # Summary frame with better styling
        summary_frame = ttk.LabelFrame(main_frame, text="Summary", padding="15")
        summary_frame.grid(row=4, column=0, columnspan=2, sticky=(tk.W, tk.E))
        
        self.summary_label = ttk.Label(summary_frame, text="Devices found: 0", 
                                      font=("Segoe UI", 11, "bold"))
        self.summary_label.grid(row=0, column=0, sticky=tk.W)
        
        # Configure grid weights
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(3, weight=1)
        
        # Bind mouse wheel to canvas
        self.canvas.bind("<MouseWheel>", self._on_mousewheel)
        
    def _on_mousewheel(self, event):
        self.canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        
    def callback(self, device, advertisement_data):
        if "GVH5104" in (device.name or ""):
            # Extract data
            manufacturer_data = advertisement_data.manufacturer_data
            if 1 in manufacturer_data:
                raw = manufacturer_data[1]
                
                # Extract 3 bytes: index 2,3,4 for temp+humidity
                packed = int.from_bytes(raw[2:5], byteorder='big')
                temperature = (packed // 1000) / 10
                humidity = (packed % 1000) / 10
                battery = raw[5]
                
                # Create/update device data
                device_data = {
                    'name': device.name or 'Unknown',
                    'address': device.address,
                    'temperature': temperature,
                    'humidity': humidity,
                    'battery': battery,
                    'last_update': datetime.now(),
                    'rssi': advertisement_data.rssi if hasattr(advertisement_data, 'rssi') else 'N/A',
                    'display_name': self.get_display_name(device.address)
                }
                
                # Store device data
                self.devices[device.address] = device_data
                
                # Update GUI in main thread
                self.root.after(0, self.update_display)
    
    def update_display(self):
        # Clear existing device widgets
        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()
            
        if not self.devices:
            self.no_devices_label = ttk.Label(self.scrollable_frame, 
                                             text="No devices detected yet...", 
                                             font=("Arial", 12), foreground="gray")
            self.no_devices_label.grid(row=0, column=0, pady=50)
        else:
            # Display each device
            for i, (address, data) in enumerate(self.devices.items()):
                self.create_device_widget(i, data)
        
        # Update summary
        self.summary_label.config(text=f"Devices found: {len(self.devices)}")
        
        # Update status
        if self.scanning:
            self.status_label.config(text=f"Scanning... Found {len(self.devices)} device(s)", 
                                   foreground="green")
        else:
            self.status_label.config(text=f"Scanning stopped. {len(self.devices)} device(s) in memory", 
                                   foreground="gray")
            
        # Update canvas scroll region
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))
    
    def create_device_widget(self, row, data):
        # Main device frame with custom name if available
        display_name = data['display_name']
        device_frame = ttk.LabelFrame(self.scrollable_frame, 
                                     text=f"📡 {display_name}", 
                                     padding="20")
        device_frame.grid(row=row, column=0, sticky=(tk.W, tk.E), pady=8, padx=10)
        
        # Device info row with better fonts
        info_frame = ttk.Frame(device_frame)
        info_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 15))
        
        ttk.Label(info_frame, text=f"Address: {data['address']}", 
                 font=("Consolas", 10)).grid(row=0, column=0, sticky=tk.W)
        ttk.Label(info_frame, text=f"Signal: {data['rssi']} dBm", 
                 font=("Segoe UI", 10)).grid(row=0, column=1, sticky=tk.E, padx=(30, 0))
        
        # Add rename button
        rename_btn = ttk.Button(info_frame, text="✏️ Rename", 
                               command=lambda addr=data['address']: self.rename_device(addr),
                               style='Action.TButton')
        rename_btn.grid(row=0, column=2, sticky=tk.E, padx=(10, 0))
        
        # Readings row with improved layout
        readings_frame = ttk.Frame(device_frame)
        readings_frame.grid(row=1, column=0, sticky=(tk.W, tk.E))
        
        # Temperature with better styling
        temp_frame = ttk.Frame(readings_frame)
        temp_frame.grid(row=0, column=0, padx=(0, 30))
        
        ttk.Label(temp_frame, text="🌡️ Temperature", 
                 font=("Segoe UI", 11, "bold")).grid(row=0, column=0)
        ttk.Label(temp_frame, text=f"{data['temperature']:.1f}°C", 
                 font=("Segoe UI", 22, "bold"), foreground="#dc3545").grid(row=1, column=0)
        
        # Humidity with better styling
        humid_frame = ttk.Frame(readings_frame)
        humid_frame.grid(row=0, column=1, padx=(30, 30))
        
        ttk.Label(humid_frame, text="💧 Humidity", 
                 font=("Segoe UI", 11, "bold")).grid(row=0, column=0)
        ttk.Label(humid_frame, text=f"{data['humidity']:.1f}%", 
                 font=("Segoe UI", 22, "bold"), foreground="#007bff").grid(row=1, column=0)
        
        # Battery with better styling
        battery_frame = ttk.Frame(readings_frame)
        battery_frame.grid(row=0, column=2, padx=(30, 0))
        
        # Battery icon based on level
        battery_icon = "🔋" if data['battery'] > 20 else "🪫"
        ttk.Label(battery_frame, text=f"{battery_icon} Battery", 
                 font=("Segoe UI", 11, "bold")).grid(row=0, column=0)
        
        battery_color = "#28a745" if data['battery'] > 20 else "#ffc107" if data['battery'] > 10 else "#dc3545"
        ttk.Label(battery_frame, text=f"{data['battery']}%", 
                 font=("Segoe UI", 22, "bold"), foreground=battery_color).grid(row=1, column=0)
        
        # Last update with better styling
        update_frame = ttk.Frame(device_frame)
        update_frame.grid(row=2, column=0, sticky=(tk.W, tk.E), pady=(15, 0))
        
        time_str = data['last_update'].strftime("%H:%M:%S")
        ttk.Label(update_frame, text=f"⏰ Last update: {time_str}", 
                 font=("Segoe UI", 10), foreground="#6c757d").grid(row=0, column=0, sticky=tk.W)
        
        # Configure column weights
        device_frame.columnconfigure(0, weight=1)
        info_frame.columnconfigure(1, weight=1)
        self.scrollable_frame.columnconfigure(0, weight=1)
    
    def get_display_name(self, address):
        """Get the display name for a device (custom name if set, otherwise default name)"""
        return self.device_names.get(address, f"Thermometer ({address[-5:]})")
    
    def rename_device(self, address):
        """Open a dialog to rename a specific device"""
        current_name = self.device_names.get(address, "")
        
        dialog = tk.Toplevel(self.root)
        dialog.title("Rename Device")
        dialog.geometry("400x200")
        dialog.resizable(False, False)
        dialog.transient(self.root)
        dialog.grab_set()
        
        # Center the dialog
        dialog.geometry("+%d+%d" % (self.root.winfo_rootx() + 50, self.root.winfo_rooty() + 50))
        
        # Dialog content
        main_frame = ttk.Frame(dialog, padding="20")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        ttk.Label(main_frame, text=f"Device Address: {address}", 
                 font=("Consolas", 10)).grid(row=0, column=0, columnspan=2, pady=(0, 15))
        
        ttk.Label(main_frame, text="Custom Name:", 
                 font=("Segoe UI", 11)).grid(row=1, column=0, sticky=tk.W, pady=(0, 10))
        
        name_var = tk.StringVar(value=current_name)
        name_entry = ttk.Entry(main_frame, textvariable=name_var, font=("Segoe UI", 11), width=30)
        name_entry.grid(row=2, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 20))
        name_entry.focus()
        
        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=3, column=0, columnspan=2)
        
        def save_name():
            new_name = name_var.get().strip()
            if new_name:
                self.device_names[address] = new_name
            else:
                # Remove custom name if empty
                self.device_names.pop(address, None)
            
            # Save to file immediately
            self.save_device_names()
            
            # Update the device data display name
            if address in self.devices:
                self.devices[address]['display_name'] = self.get_display_name(address)
            
            self.update_display()
            dialog.destroy()
        
        def cancel():
            dialog.destroy()
        
        ttk.Button(button_frame, text="Save", command=save_name).grid(row=0, column=0, padx=(0, 10))
        ttk.Button(button_frame, text="Cancel", command=cancel).grid(row=0, column=1)
        
        # Bind Enter key to save
        dialog.bind('<Return>', lambda e: save_name())
        dialog.bind('<Escape>', lambda e: cancel())
    
    def open_names_dialog(self):
        """Open a dialog to manage all device names"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Manage Device Names")
        dialog.geometry("600x400")
        dialog.transient(self.root)
        dialog.grab_set()
        
        # Center the dialog
        dialog.geometry("+%d+%d" % (self.root.winfo_rootx() + 100, self.root.winfo_rooty() + 50))
        
        # Dialog content
        main_frame = ttk.Frame(dialog, padding="20")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        ttk.Label(main_frame, text="Device Name Management", 
                 font=("Segoe UI", 14, "bold")).grid(row=0, column=0, columnspan=3, pady=(0, 20))
        
        # Headers
        ttk.Label(main_frame, text="Device Address", 
                 font=("Segoe UI", 11, "bold")).grid(row=1, column=0, sticky=tk.W, padx=(0, 20))
        ttk.Label(main_frame, text="Custom Name", 
                 font=("Segoe UI", 11, "bold")).grid(row=1, column=1, sticky=tk.W, padx=(0, 20))
        ttk.Label(main_frame, text="Action", 
                 font=("Segoe UI", 11, "bold")).grid(row=1, column=2, sticky=tk.W)
        
        # Separator
        separator = ttk.Separator(main_frame, orient='horizontal')
        separator.grid(row=2, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(5, 15))
        
        # List all known devices (both detected and named)
        all_addresses = set(self.devices.keys()) | set(self.device_names.keys())
        
        if not all_addresses:
            ttk.Label(main_frame, text="No devices found yet. Start scanning to detect devices.", 
                     font=("Segoe UI", 11), foreground="#6c757d").grid(row=3, column=0, columnspan=3, pady=20)
        else:
            for i, address in enumerate(sorted(all_addresses), start=3):
                # Address
                ttk.Label(main_frame, text=address, 
                         font=("Consolas", 10)).grid(row=i, column=0, sticky=tk.W, padx=(0, 20), pady=5)
                
                # Current name
                current_name = self.device_names.get(address, "(default)")
                ttk.Label(main_frame, text=current_name, 
                         font=("Segoe UI", 10)).grid(row=i, column=1, sticky=tk.W, padx=(0, 20), pady=5)
                
                # Edit button
                edit_btn = ttk.Button(main_frame, text="Edit", 
                                     command=lambda addr=address: self.rename_device_from_manager(addr, dialog))
                edit_btn.grid(row=i, column=2, sticky=tk.W, pady=2)
        
        # Close button
        ttk.Button(main_frame, text="Close", 
                  command=dialog.destroy).grid(row=20, column=0, columnspan=3, pady=(20, 0))
        
        # Configure weights
        dialog.columnconfigure(0, weight=1)
        dialog.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
    
    def rename_device_from_manager(self, address, manager_dialog):
        """Rename device from the manager dialog"""
        manager_dialog.destroy()  # Close manager first
        self.rename_device(address)  # Open rename dialog
        # Reopen manager after rename dialog closes
        self.root.after(100, self.open_names_dialog)
    
    def toggle_scanning(self):
        if not self.scanning:
            self.start_scanning()
        else:
            self.stop_scanning()
    
    def start_scanning(self):
        self.scanning = True
        self.scan_button.config(text="Stop Scanning")
        self.refresh_button.config(state="disabled")
        
        # Start scanning in a separate thread
        def run_scanner():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(self.scan_continuously())
            except Exception as e:
                print(f"Scanner error: {e}")
            finally:
                loop.close()
        
        self.scan_thread = threading.Thread(target=run_scanner, daemon=True)
        self.scan_thread.start()
        
        self.update_display()
    
    def stop_scanning(self):
        self.scanning = False
        self.scan_button.config(text="Start Scanning")
        self.refresh_button.config(state="normal")
        self.update_display()
    
    async def scan_continuously(self):
        self.scanner = BleakScanner(self.callback)
        await self.scanner.start()
        
        # Keep scanning while the flag is True
        while self.scanning:
            await asyncio.sleep(1)
        
        await self.scanner.stop()
    
    def refresh_once(self):
        if not self.scanning:
            self.status_label.config(text="Scanning once...", foreground="orange")
            
            def run_single_scan():
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    loop.run_until_complete(self.scan_once())
                except Exception as e:
                    print(f"Single scan error: {e}")
                    self.root.after(0, lambda: self.status_label.config(
                        text="Scan failed", foreground="red"))
                finally:
                    loop.close()
            
            thread = threading.Thread(target=run_single_scan, daemon=True)
            thread.start()
    
    async def scan_once(self):
        scanner = BleakScanner(self.callback)
        await scanner.start()
        await asyncio.sleep(5)  # Scan for 5 seconds
        await scanner.stop()
        
        # Update status
        self.root.after(0, lambda: self.status_label.config(
            text="Single scan completed", foreground="gray"))
    
    def clear_devices(self):
        self.devices.clear()
        self.update_display()

def main():
    root = tk.Tk()
    app = GoveeThermometerGUI(root)
    
    # Handle window closing
    def on_closing():
        if app.scanning:
            app.stop_scanning()
        # Save device names one final time before closing
        app.save_device_names()
        root.destroy()
    
    root.protocol("WM_DELETE_WINDOW", on_closing)
    root.mainloop()

if __name__ == "__main__":
    main()