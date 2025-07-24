#!/usr/bin/python3

import tkinter as tk
from tkinter import messagebox, ttk, filedialog
import asyncio
import threading
from datetime import datetime
import sys
import json
from concurrent.futures import ThreadPoolExecutor
import queue
import ctypes
import platform
import csv
import os

# Import from the original script
from govee_h5075 import GoveeThermometerHygrometer, Measurement, Alias, MyLogger

class GoveeUI(tk.Tk):
    def __init__(self):
        super().__init__()
        
        # Make the application DPI aware for crisp text on high-DPI displays
        self.make_dpi_aware()
        
        self.title("Govee H5075 BLE Monitor")
        self.geometry("1200x800")
        
        # Configure high-quality fonts
        self.configure_fonts()
        
        self.alias = Alias()
        self.devices = {}  # Store latest advertisement data for each device
        self.scanning = False
        self.monitoring = False
        self.measurement_log = []
        self.executor = ThreadPoolExecutor(max_workers=2)
        
        # Queue for thread-safe GUI updates
        self.update_queue = queue.Queue()
        
        # Configure the application style
        self.configure_style()
        
        self.create_widgets()
        self.setup_menu()
        
        # Start the queue processor with faster polling
        self.process_queue()
    
    def make_dpi_aware(self):
        """Make the application DPI aware for crisp text on high-DPI displays"""
        if platform.system() == "Windows":
            try:
                # Try the new Windows 10+ API first
                ctypes.windll.shcore.SetProcessDpiAwareness(2)  # PROCESS_PER_MONITOR_DPI_AWARE
            except (AttributeError, OSError):
                try:
                    # Fallback for older Windows versions
                    ctypes.windll.user32.SetProcessDPIAware()
                except (AttributeError, OSError):
                    pass  # DPI awareness not available
    
    def configure_fonts(self):
        """Configure high-quality fonts for the application"""
        # Get system default font with good size
        if platform.system() == "Windows":
            self.default_font = ("Segoe UI", 9)
            self.mono_font = ("Consolas", 9)
            self.header_font = ("Segoe UI", 10, "bold")
        elif platform.system() == "Darwin":  # macOS
            self.default_font = ("SF Pro Text", 13)
            self.mono_font = ("SF Mono", 12)
            self.header_font = ("SF Pro Text", 14, "bold")
        else:  # Linux
            self.default_font = ("Ubuntu", 10)
            self.mono_font = ("Ubuntu Mono", 10)
            self.header_font = ("Ubuntu", 11, "bold")
        
        # Configure default font for all tkinter widgets
        self.option_add("*Font", self.default_font)
    
    def configure_style(self):
        """Configure the ttk style for better appearance"""
        style = ttk.Style()
        
        # Use a modern theme if available
        available_themes = style.theme_names()
        if "vista" in available_themes:
            style.theme_use("vista")
        elif "clam" in available_themes:
            style.theme_use("clam")
        
        # Configure specific widget styles
        style.configure("Heading.TLabel", font=self.header_font)
        style.configure("Treeview.Heading", font=self.header_font)
        style.configure("Treeview", font=self.default_font, rowheight=25)
        
        # Configure button style
        style.configure("TButton", font=self.default_font, padding=(10, 5))

    def setup_menu(self):
        menubar = tk.Menu(self)
        self.config(menu=menubar)
        
        # File menu
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="Export JSON", command=self.export_json)
        file_menu.add_command(label="Export CSV", command=self.export_csv)
        file_menu.add_command(label="Save Log", command=self.save_log)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.quit)
        
        # View menu
        view_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="View", menu=view_menu)
        view_menu.add_command(label="Clear Output", command=self.clear_output)
        view_menu.add_command(label="Clear Log", command=self.clear_log)

    def create_widgets(self):
        # Configure the main window
        self.configure(bg='#f0f0f0')
        
        # Main frame with padding
        main_frame = ttk.Frame(self, padding="15")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Title label
        title_label = ttk.Label(main_frame, text="Govee H5075 BLE Monitor", 
                               style="Heading.TLabel")
        title_label.pack(pady=(0, 15))
        
        # Control frame
        control_frame = ttk.Frame(main_frame)
        control_frame.pack(fill=tk.X, pady=(0, 15))
        
        # Create buttons with better styling
        button_frame = ttk.Frame(control_frame)
        button_frame.pack(side=tk.LEFT)
        
        self.scan_btn = ttk.Button(button_frame, text="Scan Devices", 
                                  command=self.scan_devices, style="TButton")
        self.scan_btn.pack(side=tk.LEFT, padx=(0, 10))
        
        self.status_btn = ttk.Button(button_frame, text="Get Status", 
                                    command=self.get_status, style="TButton")
        self.status_btn.pack(side=tk.LEFT, padx=(0, 10))
        
        self.info_btn = ttk.Button(button_frame, text="Device Info (Slow)", 
                                  command=self.get_device_info, style="TButton")
        self.info_btn.pack(side=tk.LEFT, padx=(0, 10))
        
        # Continuous monitoring button
        self.monitor_btn = ttk.Button(button_frame, text="Start Monitoring", 
                                     command=self.toggle_monitoring, style="TButton")
        self.monitor_btn.pack(side=tk.LEFT, padx=(0, 10))
        
        # Progress bar with better styling
        progress_frame = ttk.Frame(control_frame)
        progress_frame.pack(side=tk.RIGHT)
        
        ttk.Label(progress_frame, text="Status:", font=self.default_font).pack(side=tk.LEFT, padx=(0, 5))
        self.progress = ttk.Progressbar(progress_frame, mode='indeterminate', length=200)
        self.progress.pack(side=tk.LEFT)
        
        # Device list frame with better styling
        list_frame = ttk.LabelFrame(main_frame, text="Discovered Devices", padding="5")
        list_frame.pack(fill=tk.BOTH, expand=False, pady=(0, 15))
        
        # Create treeview with better configuration
        columns = ('Address/Alias', 'Name', 'Temperature', 'Humidity', 'Battery', 'Last Update')
        self.device_tree = ttk.Treeview(list_frame, columns=columns, show='headings', height=8)
        
        # Configure column widths and alignments
        column_widths = {'Address/Alias': 180, 'Name': 120, 'Temperature': 120, 
                        'Humidity': 100, 'Battery': 80, 'Last Update': 150}
        
        for col in columns:
            self.device_tree.heading(col, text=col, anchor='w')
            self.device_tree.column(col, width=column_widths.get(col, 100), 
                                   anchor='center' if col != 'Address/Alias' else 'w')
        
        # Scrollbar for treeview - directly in the list_frame
        tree_scroll = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.device_tree.yview)
        self.device_tree.configure(yscrollcommand=tree_scroll.set)
        
        # Pack treeview and scrollbar together without intermediate frame
        self.device_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        tree_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Notebook for tabbed interface
        notebook = ttk.Notebook(main_frame)
        notebook.pack(fill=tk.BOTH, expand=True, pady=(0, 15))
        
        # Output tab
        output_frame = ttk.Frame(notebook, padding="10")
        notebook.add(output_frame, text="Output")
        
        # Text widget with better font and scrollbar
        text_frame = ttk.Frame(output_frame)
        text_frame.pack(fill=tk.BOTH, expand=True)
        
        self.output = tk.Text(text_frame, wrap=tk.WORD, font=self.mono_font,
                             bg='white', fg='black', selectbackground='#0078d4',
                             relief='flat', borderwidth=1, highlightthickness=1,
                             highlightcolor='#0078d4', highlightbackground='#d0d0d0')
        
        output_scroll = ttk.Scrollbar(text_frame, orient=tk.VERTICAL, command=self.output.yview)
        self.output.configure(yscrollcommand=output_scroll.set)
        
        self.output.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        output_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Monitoring log tab
        log_frame = ttk.Frame(notebook, padding="10")
        notebook.add(log_frame, text="Monitoring Log")
        
        # Create monitoring log treeview
        log_columns = ('Timestamp', 'Device', 'Temperature', 'Humidity', 'Dew Point', 'Battery')
        self.log_tree = ttk.Treeview(log_frame, columns=log_columns, show='headings', height=15)
        
        log_column_widths = {'Timestamp': 150, 'Device': 180, 'Temperature': 120,
                            'Humidity': 100, 'Dew Point': 120, 'Battery': 80}
        
        for col in log_columns:
            self.log_tree.heading(col, text=col, anchor='w')
            self.log_tree.column(col, width=log_column_widths.get(col, 100), anchor='center')
        
        log_scroll = ttk.Scrollbar(log_frame, orient=tk.VERTICAL, command=self.log_tree.yview)
        self.log_tree.configure(yscrollcommand=log_scroll.set)
        
        self.log_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        log_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Statistics frame
        stats_frame = ttk.LabelFrame(main_frame, text="Monitoring Statistics", padding="10")
        stats_frame.pack(fill=tk.X, pady=(0, 15))
        
        # Statistics labels
        stats_inner = ttk.Frame(stats_frame)
        stats_inner.pack(fill=tk.X)
        
        self.total_measurements_var = tk.StringVar(value="Total Measurements: 0")
        ttk.Label(stats_inner, textvariable=self.total_measurements_var).pack(side=tk.LEFT, padx=(0, 20))
        
        self.monitoring_duration_var = tk.StringVar(value="Duration: 00:00:00")
        ttk.Label(stats_inner, textvariable=self.monitoring_duration_var).pack(side=tk.LEFT, padx=(0, 20))
        
        self.devices_monitored_var = tk.StringVar(value="Devices: 0")
        ttk.Label(stats_inner, textvariable=self.devices_monitored_var).pack(side=tk.LEFT)
        
        # Status bar with better styling
        status_frame = ttk.Frame(main_frame)
        status_frame.pack(fill=tk.X, pady=(15, 0))
        
        self.status_var = tk.StringVar(value="Ready")
        status_bar = ttk.Label(status_frame, textvariable=self.status_var, 
                              relief=tk.SUNKEN, padding="5", font=self.default_font)
        status_bar.pack(fill=tk.X)
        
        # Initialize monitoring start time
        self.monitoring_start_time = None

    def process_queue(self):
        """Process GUI updates from background threads - faster polling"""
        try:
            while True:
                action, data = self.update_queue.get_nowait()
                
                if action == "device_found":
                    address, name, battery, measurement = data
                    label = self.alias.aliases.get(address, (address,))[0] if address in self.alias.aliases else address
                    
                    # Store the device data
                    device_data = {
                        'address': address,
                        'name': name,
                        'measurement': measurement,
                        'battery': battery,
                        'last_update': datetime.now()
                    }
                    
                    # Update or add to treeview
                    existing_item = None
                    for item in self.device_tree.get_children():
                        if self.devices.get(item, {}).get('address') == address:
                            existing_item = item
                            break
                    
                    timestamp = datetime.now().strftime("%H:%M:%S")
                    values = (
                        label,
                        name,
                        f"{measurement.temperatureC:.1f}°C",
                        f"{measurement.relHumidity:.1f}%",
                        f"{battery}%",
                        timestamp
                    )
                    
                    if existing_item:
                        self.device_tree.item(existing_item, values=values)
                        self.devices[existing_item] = device_data
                    else:
                        item_id = self.device_tree.insert('', tk.END, values=values)
                        self.devices[item_id] = device_data
                
                elif action == "device_found_silent":
                    # Same as device_found but without any output - used during monitoring
                    address, name, battery, measurement = data
                    label = self.alias.aliases.get(address, (address,))[0] if address in self.alias.aliases else address
                    
                    # Store the device data
                    device_data = {
                        'address': address,
                        'name': name,
                        'measurement': measurement,
                        'battery': battery,
                        'last_update': datetime.now()
                    }
                    
                    # Update or add to treeview
                    existing_item = None
                    for item in self.device_tree.get_children():
                        if self.devices.get(item, {}).get('address') == address:
                            existing_item = item
                            break
                    
                    timestamp = datetime.now().strftime("%H:%M:%S")
                    values = (
                        label,
                        name,
                        f"{measurement.temperatureC:.1f}°C",
                        f"{measurement.relHumidity:.1f}%",
                        f"{battery}%",
                        timestamp
                    )
                    
                    if existing_item:
                        self.device_tree.item(existing_item, values=values)
                        self.devices[existing_item] = device_data
                    else:
                        item_id = self.device_tree.insert('', tk.END, values=values)
                        self.devices[item_id] = device_data
                    
                elif action == "measurement_logged":
                    timestamp, address, name, battery, measurement = data
                    label = self.alias.aliases.get(address, (address,))[0] if address in self.alias.aliases else address
                    
                    # Add to measurement log
                    log_entry = {
                        'timestamp': timestamp,
                        'address': address,
                        'name': name,
                        'measurement': measurement,
                        'battery': battery
                    }
                    self.measurement_log.append(log_entry)
                    
                    # Add to log treeview
                    self.log_tree.insert('', 0, values=(  # Insert at top
                        timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                        f"{label} ({name})",
                        f"{measurement.temperatureC:.1f}°C",
                        f"{measurement.relHumidity:.1f}%",
                        f"{measurement.dewPointC:.1f}°C",
                        f"{battery}%"
                    ))
                    
                    # Update statistics
                    self.update_statistics()
                
                elif action == "measurement_with_output":
                    # This action logs the measurement AND prints to output
                    timestamp, address, name, battery, measurement = data
                    label = self.alias.aliases.get(address, (address,))[0] if address in self.alias.aliases else address
                    
                    # Add to measurement log
                    log_entry = {
                        'timestamp': timestamp,
                        'address': address,
                        'name': name,
                        'measurement': measurement,
                        'battery': battery
                    }
                    self.measurement_log.append(log_entry)
                    
                    # Add to log treeview
                    self.log_tree.insert('', 0, values=(  # Insert at top
                        timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                        f"{label} ({name})",
                        f"{measurement.temperatureC:.1f}°C",
                        f"{measurement.relHumidity:.1f}%",
                        f"{measurement.dewPointC:.1f}°C",
                        f"{battery}%"
                    ))
                    
                    # Print to output box directly - NO queue recursion
                    output_line = f"[{timestamp.strftime('%H:%M:%S')}] {label} ({name}): {measurement.temperatureC:.1f}°C, {measurement.relHumidity:.1f}%, {battery}% battery"
                    self.output.insert(tk.END, output_line + "\n")
                    self.output.see(tk.END)
                    
                    # Update statistics
                    self.update_statistics()
                    
                elif action == "status_update":
                    self.status_var.set(data)
                    
                elif action == "output_text":
                    self.output.insert(tk.END, data + "\n")
                    self.output.see(tk.END)
                    
                elif action == "clear_output":
                    self.output.delete("1.0", tk.END)
                    
                elif action == "scan_complete":
                    self.scanning = False
                    self.scan_btn.config(state='normal')
                    self.progress.stop()
                    self.status_var.set(f"Scan complete. Found {len(self.devices)} devices.")
                    
                elif action == "operation_complete":
                    self.info_btn.config(state='normal')
                    self.progress.stop()
                    
                elif action == "monitoring_started":
                    self.monitoring = True
                    self.monitor_btn.config(text="Stop Monitoring")
                    self.monitoring_start_time = datetime.now()
                    self.progress.start()
                    self.status_var.set("Continuous monitoring active...")
                    
                elif action == "monitoring_stopped":
                    self.monitoring = False
                    self.monitor_btn.config(text="Start Monitoring")
                    self.progress.stop()
                    self.status_var.set("Monitoring stopped")
                    
        except queue.Empty:
            pass
        
        # Update monitoring duration if monitoring is active
        if self.monitoring and self.monitoring_start_time:
            duration = datetime.now() - self.monitoring_start_time
            hours, remainder = divmod(duration.total_seconds(), 3600)
            minutes, seconds = divmod(remainder, 60)
            self.monitoring_duration_var.set(f"Duration: {int(hours):02d}:{int(minutes):02d}:{int(seconds):02d}")
        
        # Schedule next check - faster polling for better responsiveness
        self.after(20, self.process_queue)

    def update_statistics(self):
        """Update the monitoring statistics display"""
        total_measurements = len(self.measurement_log)
        unique_devices = len(set(entry['address'] for entry in self.measurement_log))
        
        self.total_measurements_var.set(f"Total Measurements: {total_measurements}")
        self.devices_monitored_var.set(f"Devices: {unique_devices}")

    def scan_devices(self):
        if self.scanning:
            return
            
        self.scanning = True
        self.scan_btn.config(state='disabled')
        self.progress.start()
        
        # Clear previous results
        for item in self.device_tree.get_children():
            self.device_tree.delete(item)
        self.devices.clear()
        
        self.update_queue.put(("status_update", "Scanning for devices..."))
        self.update_queue.put(("clear_output", None))
        
        def stdout_consumer(address: str, name: str, battery: int, measurement: Measurement):
            self.update_queue.put(("device_found", (address, name, battery, measurement)))

        def progress_callback(found: int):
            self.update_queue.put(("status_update", f"Scanning... {found} BLE devices seen"))

        def run_scan():
            try:
                async def custom_scan():
                    from bleak import BleakScanner, BLEDevice, AdvertisementData
                    
                    found_devices = []
                    
                    def callback(device: BLEDevice, advertising_data: AdvertisementData):
                        if device.address not in found_devices:
                            found_devices.append(device.address)
                            if device.name and device.address.upper().startswith("A4:C1:38:"):
                                if 0xec88 in advertising_data.manufacturer_data:
                                    try:
                                        # Handle alias lookup safely
                                        if device.address in self.alias.aliases:
                                            humidityOffset = self.alias.aliases[device.address][1] if self.alias.aliases[device.address][1] else 0.0
                                            temperatureOffset = self.alias.aliases[device.address][2] if self.alias.aliases[device.address][2] else 0.0
                                        else:
                                            humidityOffset = 0.0
                                            temperatureOffset = 0.0

                                        measurement = Measurement.from_bytes(
                                            bytes=advertising_data.manufacturer_data[0xec88][1:4], 
                                            humidityOffset=humidityOffset, 
                                            temperatureOffset=temperatureOffset
                                        )
                                        
                                        battery = advertising_data.manufacturer_data[0xec88][4]
                                        stdout_consumer(device.address, device.name, battery, measurement)
                                        
                                    except Exception as e:
                                        self.update_queue.put(("output_text", f"Error processing device {device.address}: {str(e)}"))
                            
                            elif device.name:
                                progress_callback(len(found_devices))
                    
                    async with BleakScanner(callback) as scanner:
                        await asyncio.sleep(15)
                
                asyncio.run(custom_scan())
                self.update_queue.put(("scan_complete", None))
            except Exception as e:
                self.update_queue.put(("output_text", f"Scan error: {str(e)}"))
                self.update_queue.put(("scan_complete", None))

        self.executor.submit(run_scan)

    def toggle_monitoring(self):
        """Toggle continuous monitoring on/off"""
        if not self.monitoring:
            self.start_monitoring()
        else:
            self.stop_monitoring()

    def start_monitoring(self):
        """Start continuous monitoring of devices"""
        if self.monitoring:
            return
            
        self.update_queue.put(("monitoring_started", None))
        
        def continuous_monitor():
            try:
                async def monitor_loop():
                    from bleak import BleakScanner, BLEDevice, AdvertisementData
                    
                    def callback(device: BLEDevice, advertising_data: AdvertisementData):
                        if not self.monitoring:  # Check if monitoring should continue
                            return
                            
                        if device.name and device.address.upper().startswith("A4:C1:38:"):
                            if 0xec88 in advertising_data.manufacturer_data:
                                try:
                                    # Handle alias lookup safely
                                    if device.address in self.alias.aliases:
                                        humidityOffset = self.alias.aliases[device.address][1] if self.alias.aliases[device.address][1] else 0.0
                                        temperatureOffset = self.alias.aliases[device.address][2] if self.alias.aliases[device.address][2] else 0.0
                                    else:
                                        humidityOffset = 0.0
                                        temperatureOffset = 0.0

                                    measurement = Measurement.from_bytes(
                                        bytes=advertising_data.manufacturer_data[0xec88][1:4], 
                                        humidityOffset=humidityOffset, 
                                        temperatureOffset=temperatureOffset
                                    )
                                    
                                    battery = advertising_data.manufacturer_data[0xec88][4]
                                    timestamp = datetime.now()
                                    
                                    # Update device display (this will NOT trigger output during monitoring)
                                    self.update_queue.put(("device_found_silent", (device.address, device.name, battery, measurement)))
                                    
                                    # Log measurement with output - single line format
                                    self.update_queue.put(("measurement_with_output", (timestamp, device.address, device.name, battery, measurement)))
                                    
                                except Exception as e:
                                    self.update_queue.put(("output_text", f"Error processing device {device.address}: {str(e)}"))
                    
                    # Continuous scanning without artificial delays
                    async with BleakScanner(callback) as scanner:
                        while self.monitoring:
                            await asyncio.sleep(0.1)  # Just a small sleep to prevent CPU spinning
                
                asyncio.run(monitor_loop())
                
            except Exception as e:
                self.update_queue.put(("output_text", f"Monitoring error: {str(e)}"))
            finally:
                self.update_queue.put(("monitoring_stopped", None))

        self.executor.submit(continuous_monitor)

    def stop_monitoring(self):
        """Stop continuous monitoring"""
        self.monitoring = False
        self.update_queue.put(("monitoring_stopped", None))

    def get_status(self):
        """Get status from cached advertisement data - INSTANT"""
        selection = self.device_tree.selection()
        if not selection:
            messagebox.showwarning("No device selected", "Please select a device from the list.")
            return
        
        item_id = selection[0]
        device_info = self.devices.get(item_id)
        if not device_info:
            messagebox.showerror("Error", "Device information not found.")
            return
        
        # Show cached data instantly - no connection needed!
        measurement = device_info['measurement']
        last_update = device_info['last_update']
        
        self.update_queue.put(("clear_output", None))
        self.update_queue.put(("output_text", f"Status for {device_info['name']} ({device_info['address']}):"))
        self.update_queue.put(("output_text", f"Last Update: {last_update.strftime('%Y-%m-%d %H:%M:%S')}"))
        self.update_queue.put(("output_text", str(measurement)))
        self.update_queue.put(("output_text", f"Battery level: {device_info['battery']}%"))
        
        self.status_var.set("Status displayed from cached data")

    def get_device_info(self):
        """Get detailed device info via BLE connection - SLOW but comprehensive"""
        selection = self.device_tree.selection()
        if not selection:
            messagebox.showwarning("No device selected", "Please select a device from the list.")
            return
        
        item_id = selection[0]
        device_info = self.devices.get(item_id)
        if not device_info:
            messagebox.showerror("Error", "Device information not found.")
            return
        
        self.info_btn.config(state='disabled')
        self.progress.start()
        self.update_queue.put(("status_update", "Connecting to device for detailed info..."))

        async def fetch_info():
            try:
                device = GoveeThermometerHygrometer(device_info['address'])
                await device.connect()
                
                # Request all device information
                await device.requestDeviceName()
                await device.requestHumidityAlarm()
                await device.requestTemperatureAlarm()
                await device.requestHumidityOffset()
                await device.requestTemperatureOffset()
                await device.requestHardwareVersion()
                await device.requestFirmwareVersion()
                await device.requestMeasurementAndBattery()
                
                # Reduced wait time
                await asyncio.sleep(0.2)
                
                result = str(device)
                self.update_queue.put(("clear_output", None))
                self.update_queue.put(("output_text", f"Complete information for {device_info['name']} ({device_info['address']}):"))
                self.update_queue.put(("output_text", result))
                
                await device.disconnect()
                
            except Exception as e:
                self.update_queue.put(("output_text", f"Error fetching device info: {str(e)}"))
            finally:
                self.update_queue.put(("operation_complete", None))
                self.update_queue.put(("status_update", "Ready"))

        self.executor.submit(lambda: asyncio.run(fetch_info()))

    def export_json(self):
        if not self.measurement_log:
            messagebox.showwarning("No data", "No measurement data to export.")
            return
        
        filename = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            title="Save measurement data as JSON"
        )
        
        if filename:
            try:
                export_data = []
                for entry in self.measurement_log:
                    data = {
                        "timestamp": entry['timestamp'].strftime("%Y-%m-%d %H:%M:%S"),
                        "address": entry['address'],
                        "name": entry['name'],
                        "battery": entry['battery'],
                        "measurement": entry['measurement'].to_dict()
                    }
                    export_data.append(data)
                
                with open(filename, 'w') as f:
                    json.dump(export_data, f, indent=2)
                
                messagebox.showinfo("Export successful", f"Data exported to {filename}")
                
            except Exception as e:
                messagebox.showerror("Export failed", f"Failed to export data: {str(e)}")

    def export_csv(self):
        if not self.measurement_log:
            messagebox.showwarning("No data", "No measurement data to export.")
            return
        
        filename = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            title="Save measurement data as CSV"
        )
        
        if filename:
            try:
                with open(filename, 'w', newline='') as f:
                    writer = csv.writer(f)
                    
                    # Write header
                    writer.writerow([
                        'Timestamp', 'Address', 'Device Name', 'Temperature (°C)', 
                        'Temperature (°F)', 'Humidity (%)', 'Dew Point (°C)', 
                        'Dew Point (°F)', 'Abs Humidity (g/m³)', 'Steam Pressure (mbar)', 'Battery (%)'
                    ])
                    
                    # Write data
                    for entry in self.measurement_log:
                        m = entry['measurement']
                        writer.writerow([
                            entry['timestamp'].strftime("%Y-%m-%d %H:%M:%S"),
                            entry['address'],
                            entry['name'],
                            f"{m.temperatureC:.1f}",
                            f"{m.temperatureF:.1f}",
                            f"{m.relHumidity:.1f}",
                            f"{m.dewPointC:.1f}",
                            f"{m.dewPointF:.1f}",
                            f"{m.absHumidity:.1f}",
                            f"{m.steamPressure:.1f}",
                            f"{entry['battery']}"
                        ])
                
                messagebox.showinfo("Export successful", f"Data exported to {filename}")
                
            except Exception as e:
                messagebox.showerror("Export failed", f"Failed to export data: {str(e)}")

    def save_log(self):
        """Save the current output log to a text file"""
        content = self.output.get("1.0", tk.END)
        if not content.strip():
            messagebox.showwarning("No data", "No log data to save.")
            return
        
        filename = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
            title="Save output log"
        )
        
        if filename:
            try:
                with open(filename, 'w') as f:
                    f.write(content)
                
                messagebox.showinfo("Save successful", f"Log saved to {filename}")
                
            except Exception as e:
                messagebox.showerror("Save failed", f"Failed to save log: {str(e)}")

    def clear_output(self):
        """Clear the output text area"""
        self.output.delete("1.0", tk.END)

    def clear_log(self):
        """Clear the monitoring log with confirmation"""
        if not self.measurement_log:
            messagebox.showinfo("No data", "Log is already empty.")
            return
        
        if messagebox.askyesno("Confirm Clear", 
                              f"Are you sure you want to clear {len(self.measurement_log)} measurements?"):
            self.measurement_log.clear()
            
            # Clear the log treeview
            for item in self.log_tree.get_children():
                self.log_tree.delete(item)
            
            # Reset statistics
            self.update_statistics()
            messagebox.showinfo("Cleared", "Monitoring log has been cleared.")

    def on_closing(self):
        """Handle application closing"""
        if self.monitoring:
            self.stop_monitoring()
        
        # Clean up executor
        self.executor.shutdown(wait=False)
        self.destroy()

def main():
    app = GoveeUI()
    app.protocol("WM_DELETE_WINDOW", app.on_closing)
    
    # Set minimum window size
    app.minsize(1000, 700)
    
    try:
        app.mainloop()
    except KeyboardInterrupt:
        print("\nApplication interrupted by user")
    except Exception as e:
        print(f"Application error: {e}")
    finally:
        # Ensure cleanup
        try:
            app.on_closing()
        except:
            pass

if __name__ == "__main__":
    main()