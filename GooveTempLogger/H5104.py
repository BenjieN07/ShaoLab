import asyncio
import tkinter as tk
from tkinter import ttk
import threading
from bleak import BleakScanner
from datetime import datetime
import json
import os
import re
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
import matplotlib.dates as mdates
from collections import deque
import numpy as np


class GoveeThermometerGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Govee H5104 Multi-Thermometer Reader")
        self.root.geometry("1400x900")  # Wider window to accommodate graphs

        try:
            from ctypes import windll
            windll.shcore.SetProcessDpiAwareness(1)
        except:
            pass

        self.root.tk.call('tk', 'scaling', 1.0)

        self.scanner = None
        self.scanning = False
        self.scan_task = None

        self.devices = {}
        self.device_names = {}
        
        # Track update counts for each device (save every 10 updates)
        self.update_counts = {}
        self.save_every_n_updates = 20

        # Store historical data for graphs (keep last 100 readings per device)
        self.historical_data = {}
        self.max_history_points = 100

        # Store graph widgets
        self.device_graphs = {}

        script_dir = os.path.dirname(os.path.abspath(__file__))
        self.names_file = os.path.join(script_dir, "thermometer_names.json")
        
        # Create data directory for thermometer readings
        self.data_dir = os.path.join(script_dir, "thermometer_data")
        if not os.path.exists(self.data_dir):
            os.makedirs(self.data_dir)
            print(f"Created data directory: {self.data_dir}")

        self.load_device_names()
        self.setup_ui()

    def load_device_names(self):
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
        try:
            with open(self.names_file, 'w', encoding='utf-8') as f:
                json.dump(self.device_names, f, indent=2, ensure_ascii=False)
            print(f"Saved {len(self.device_names)} device names")
        except Exception as e:
            print(f"Error saving device names: {e}")

    def sanitize_filename(self, name):
        """Sanitize a name for use as a filename"""
        # Remove or replace invalid characters for filenames
        sanitized = re.sub(r'[<>:"/\\|?*]', '_', name)
        sanitized = sanitized.strip()
        # Ensure it's not empty
        if not sanitized:
            sanitized = "thermometer"
        return sanitized

    def should_save_reading(self, address):
        """Check if this update should be saved (every 10th update)"""
        # Increment update count for this device
        self.update_counts[address] = self.update_counts.get(address, 0) + 1
        
        # Save every 10th update
        return self.update_counts[address] % self.save_every_n_updates == 0

    def get_data_filename(self, address):
        """Get the filename for storing thermometer data (now .txt format)"""
        display_name = self.get_display_name(address)
        sanitized_name = self.sanitize_filename(display_name)
        return os.path.join(self.data_dir, f"{sanitized_name}.txt")

    def save_thermometer_reading(self, address, data):
        """Save a reading to the thermometer's text file with line-based format"""
        try:
            filename = self.get_data_filename(address)
            
            # Create readable timestamp and data line
            timestamp_str = data['last_update'].strftime('%Y-%m-%d %H:%M:%S')
            temp = round(data['temperature'], 1)
            humidity = round(data['humidity'], 1)
            battery = data['battery']
            
            # Format: [YYYY-MM-DD HH:MM:SS] [temp, humidity, battery]
            line = f"[{timestamp_str}] [{temp}, {humidity}, {battery}]\n"
            
            # Append the new reading to the file
            with open(filename, 'a', encoding='utf-8') as f:
                f.write(line)
            
            update_count = self.update_counts.get(address, 0)
            print(f"Saved reading #{update_count} to {filename}: {line.strip()}")

        except Exception as e:
            print(f"Error saving thermometer reading for {address}: {e}")

    def add_historical_data(self, address, data):
        """Add data point to historical data for graphing"""
        if address not in self.historical_data:
            self.historical_data[address] = {
                'timestamps': deque(maxlen=self.max_history_points),
                'temperatures': deque(maxlen=self.max_history_points),
                'humidity': deque(maxlen=self.max_history_points),
                'battery': deque(maxlen=self.max_history_points)
            }
        
        hist = self.historical_data[address]
        hist['timestamps'].append(data['last_update'])
        hist['temperatures'].append(data['temperature'])
        hist['humidity'].append(data['humidity'])
        hist['battery'].append(data['battery'])

    def get_reading_count_from_file(self, address):
        """Count the number of readings in the data file"""
        try:
            filename = self.get_data_filename(address)
            if os.path.exists(filename):
                with open(filename, 'r', encoding='utf-8') as f:
                    return sum(1 for line in f if line.strip())
            return 0
        except Exception as e:
            print(f"Error counting readings in file: {e}")
            return 0

    def get_updates_until_next_save(self, address):
        """Get number of updates until next save for this device"""
        current_count = self.update_counts.get(address, 0)
        return self.save_every_n_updates - (current_count % self.save_every_n_updates)

    def setup_ui(self):
        style = ttk.Style()
        style.theme_use('clam')

        # Custom style for device names (MagLab, etc.)
        style.configure("DeviceName.TLabelframe.Label", font=("Segoe UI", 18, "bold"))

        # Slightly bigger font for Temperature/Humidity/Battery labels
        self.reading_label_font = ("Segoe UI", 14, "bold")
        # Bigger numbers for readings
        self.reading_value_font = ("Segoe UI", 28, "bold")

        main_frame = ttk.Frame(self.root, padding="25")
        main_frame.grid(row=0, column=0, sticky="nsew")

        # Bigger title
        title_label = ttk.Label(main_frame, text="Govee H5104 Multi-Thermometer Reader",
                                font=("Segoe UI", 22, "bold"))
        title_label.grid(row=0, column=0, columnspan=2, pady=(0, 25))

        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=1, column=0, columnspan=2, pady=(0, 20))

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
        self.names_button.grid(row=0, column=3, padx=(0, 15))

        # Add button to open data folder
        self.data_button = ttk.Button(button_frame, text="Open Data Folder",
                                      command=self.open_data_folder,
                                      style='Action.TButton', width=15)
        self.data_button.grid(row=0, column=4)

        self.status_label = ttk.Label(main_frame, text="Click 'Start Scanning' to begin",
                                      font=("Segoe UI", 11), foreground="gray")
        self.status_label.grid(row=2, column=0, columnspan=2, pady=(0, 15))

        # Devices section
        devices_frame = ttk.LabelFrame(main_frame, text="Detected Devices", padding="15")
        devices_frame.grid(row=3, column=0, columnspan=2, sticky="nsew", pady=(0, 15))
        devices_frame.config(height=600)

        canvas_frame = ttk.Frame(devices_frame)
        canvas_frame.grid(row=0, column=0, sticky="nsew")

        self.canvas = tk.Canvas(canvas_frame, bg="#f8f9fa", highlightthickness=0, bd=0)
        scrollbar = ttk.Scrollbar(canvas_frame, orient="vertical", command=self.canvas.yview)
        self.scrollable_frame = ttk.Frame(self.canvas)

        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )

        self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=scrollbar.set)

        self.canvas.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")

        self.no_devices_label = ttk.Label(self.scrollable_frame,
                                          text="No devices detected yet...",
                                          font=("Segoe UI", 12), foreground="#6c757d")
        self.no_devices_label.grid(row=0, column=0, pady=80)

        summary_frame = ttk.LabelFrame(main_frame, text="Summary", padding="15")
        summary_frame.grid(row=4, column=0, columnspan=2, sticky="ew")

        self.summary_label = ttk.Label(summary_frame, text="Devices found: 0",
                                       font=("Segoe UI", 11, "bold"))
        self.summary_label.grid(row=0, column=0, sticky="w")

        # Add data folder info (updated for .txt format)
        self.data_info_label = ttk.Label(summary_frame, text=f"Data saved to: {self.data_dir} (Every {self.save_every_n_updates} updates, line-based .txt format)",
                                         font=("Segoe UI", 9), foreground="#6c757d")
        self.data_info_label.grid(row=1, column=0, sticky="w", pady=(5, 0))

        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(3, weight=5)
        devices_frame.columnconfigure(0, weight=1)
        devices_frame.rowconfigure(0, weight=1)
        canvas_frame.columnconfigure(0, weight=1)
        canvas_frame.rowconfigure(0, weight=1)

        self.canvas.bind("<MouseWheel>", self._on_mousewheel)

    def create_graph_widget(self, parent, address):
        """Create a matplotlib graph widget for the device - separate temperature and humidity graphs"""
        # Create figure with larger size and better spacing
        fig = Figure(figsize=(8, 6), dpi=100, facecolor='white')
        fig.subplots_adjust(hspace=0.4, left=0.1, right=0.95, top=0.9, bottom=0.15)
        
        # Temperature subplot (top)
        ax1 = fig.add_subplot(211)
        ax1.set_title('Temperature Over Time', fontsize=14, fontweight='bold', pad=15)
        ax1.set_ylabel('Temperature (°C)', fontsize=12, fontweight='bold')
        ax1.tick_params(axis='both', labelsize=11)
        ax1.grid(True, alpha=0.3, linewidth=1)
        
        # Humidity subplot (bottom)
        ax2 = fig.add_subplot(212)
        ax2.set_title('Humidity Over Time', fontsize=14, fontweight='bold', pad=15)
        ax2.set_ylabel('Humidity (%)', fontsize=12, fontweight='bold')
        ax2.set_xlabel('Time', fontsize=12, fontweight='bold')
        ax2.tick_params(axis='both', labelsize=11)
        ax2.grid(True, alpha=0.3, linewidth=1)
        
        # Format x-axis to show time with larger labels
        for ax in [ax1, ax2]:
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
            ax.xaxis.set_major_locator(mdates.MinuteLocator(interval=5))
            plt.setp(ax.xaxis.get_majorticklabels(), rotation=45, fontsize=10)
        
        # Create canvas
        canvas = FigureCanvasTkAgg(fig, parent)
        canvas.draw()
        
        return canvas, fig, (ax1, ax2)

    def update_graph(self, address):
        """Update the graph for a specific device"""
        if address not in self.device_graphs or address not in self.historical_data:
            return
        
        canvas, fig, (ax1, ax2) = self.device_graphs[address]
        hist = self.historical_data[address]
        
        if len(hist['timestamps']) == 0:
            return
        
        # Clear previous plots
        ax1.clear()
        ax2.clear()
        
        # Convert timestamps to matplotlib dates
        times = list(hist['timestamps'])
        temps = list(hist['temperatures'])
        humidity = list(hist['humidity'])
        
        # Plot temperature
        ax1.plot(times, temps, 'r-', linewidth=3, label='Temperature', marker='o', markersize=4)
        ax1.set_title('Temperature Over Time', fontsize=14, fontweight='bold', pad=15)
        ax1.set_ylabel('Temperature (°C)', fontsize=12, fontweight='bold', color='red')
        ax1.tick_params(axis='both', labelsize=11)
        ax1.tick_params(axis='y', labelcolor='red')
        ax1.grid(True, alpha=0.3, linewidth=1)
        
        # Plot humidity
        ax2.plot(times, humidity, 'b-', linewidth=3, label='Humidity', marker='s', markersize=4)
        ax2.set_title('Humidity Over Time', fontsize=14, fontweight='bold', pad=15)
        ax2.set_ylabel('Humidity (%)', fontsize=12, fontweight='bold', color='blue')
        ax2.set_xlabel('Time', fontsize=12, fontweight='bold')
        ax2.tick_params(axis='both', labelsize=11)
        ax2.tick_params(axis='y', labelcolor='blue')
        ax2.grid(True, alpha=0.3, linewidth=1)
        
        # Format axes with larger fonts
        for ax in [ax1, ax2]:
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
            plt.setp(ax.xaxis.get_majorticklabels(), rotation=45, fontsize=10)
        
        # Set reasonable y-axis limits with proper range handling
        if temps:
            temp_range = max(temps) - min(temps)
            if temp_range == 0:
                # If all temperatures are the same, add a small buffer
                center = temps[0]
                ax1.set_ylim(center - 1, center + 1)
            else:
                ax1.set_ylim(min(temps) - temp_range * 0.1, max(temps) + temp_range * 0.1)
        
        if humidity:
            hum_range = max(humidity) - min(humidity)
            if hum_range == 0:
                # If all humidity values are the same, add a small buffer
                center = humidity[0]
                ax2.set_ylim(center - 2, center + 2)
            else:
                ax2.set_ylim(min(humidity) - hum_range * 0.1, max(humidity) + hum_range * 0.1)
        
        # Redraw canvas
        fig.tight_layout()
        canvas.draw()

    def open_data_folder(self):
        """Open the data folder in the system file explorer"""
        try:
            import subprocess
            import platform
            
            system = platform.system()
            if system == "Windows":
                os.startfile(self.data_dir)
            elif system == "Darwin":  # macOS
                subprocess.run(["open", self.data_dir])
            else:  # Linux and others
                subprocess.run(["xdg-open", self.data_dir])
        except Exception as e:
            print(f"Error opening data folder: {e}")

    def _on_mousewheel(self, event):
        self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def callback(self, device, advertisement_data):
        if "GVH5104" in (device.name or ""):
            manufacturer_data = advertisement_data.manufacturer_data
            if 1 in manufacturer_data:
                raw = manufacturer_data[1]
                packed = int.from_bytes(raw[2:5], byteorder='big')
                temperature = (packed // 1000) / 10
                humidity = (packed % 1000) / 10
                battery = raw[5]

                device_data = {
                    'name': device.name or 'Unknown',
                    'address': device.address,
                    'temperature': temperature,
                    'humidity': humidity,
                    'battery': battery,
                    'last_update': datetime.now(),
                    'rssi': getattr(advertisement_data, 'rssi', 'N/A'),
                    'display_name': self.get_display_name(device.address)
                }

                # Always update the device data in memory (for immediate display update)
                self.devices[device.address] = device_data
                
                # Add to historical data for graphing
                self.add_historical_data(device.address, device_data)
                
                # Only save to file every nth update
                if self.should_save_reading(device.address):
                    self.save_thermometer_reading(device.address, device_data)
                
                # Always update the display and graphs immediately
                self.root.after(0, self.update_display)

    def update_display(self):
        # Destroy all widgets in the scrollable frame first
        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()

        # Clean up all existing graphs since we'll recreate them
        for addr in list(self.device_graphs.keys()):
            canvas, fig, axes = self.device_graphs[addr]
            try:
                canvas.get_tk_widget().destroy()
            except:
                pass  # Widget may already be destroyed
            plt.close(fig)
        self.device_graphs.clear()

        if not self.devices:
            self.no_devices_label = ttk.Label(self.scrollable_frame,
                                              text="No devices detected yet...",
                                              font=("Arial", 12), foreground="gray")
            self.no_devices_label.grid(row=0, column=0, pady=50)
        else:
            for i, (address, data) in enumerate(self.devices.items()):
                self.create_device_widget(i, data)

        self.summary_label.config(text=f"Devices found: {len(self.devices)}")

        if self.scanning:
            self.status_label.config(text=f"Scanning... Found {len(self.devices)} device(s) - Saving every {self.save_every_n_updates} updates",
                                     foreground="green")
        else:
            self.status_label.config(text=f"Scanning stopped. {len(self.devices)} device(s) in memory",
                                     foreground="gray")

        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def create_device_widget(self, row, data):
        display_name = data['display_name']
        device_frame = ttk.LabelFrame(
            self.scrollable_frame,
            text=f"{display_name}",
            padding="20",
            style="DeviceName.TLabelframe"
        )
        device_frame.grid(row=row, column=0, sticky="ew", pady=8, padx=10)

        # Main container with left (readings) and right (graph) sections
        main_container = ttk.Frame(device_frame)
        main_container.grid(row=0, column=0, sticky="ew")
        main_container.columnconfigure(1, weight=1)  # Make graph section expandable

        # Left section - readings (same as before)
        readings_section = ttk.Frame(main_container)
        readings_section.grid(row=0, column=0, sticky="nw", padx=(0, 20))

        info_frame = ttk.Frame(readings_section)
        info_frame.grid(row=0, column=0, sticky="ew", pady=(0, 15))

        ttk.Label(info_frame, text=f"Address: {data['address']}",
                  font=("Consolas", 10)).grid(row=0, column=0, sticky="w")
        ttk.Label(info_frame, text=f"Signal: {data['rssi']} dBm",
                  font=("Segoe UI", 10)).grid(row=0, column=1, sticky="e", padx=(30, 0))

        rename_btn = ttk.Button(info_frame, text="Rename",
                                command=lambda addr=data['address']: self.rename_device(addr),
                                style='Action.TButton')
        rename_btn.grid(row=0, column=2, sticky="e", padx=(10, 0))

        # Add update count and save status
        update_count = self.update_counts.get(data['address'], 0)
        updates_until_save = self.get_updates_until_next_save(data['address'])
        
        data_filename = self.get_data_filename(data['address'])
        data_exists = os.path.exists(data_filename)
        
        if data_exists:
            saved_count = self.get_reading_count_from_file(data['address'])
            if updates_until_save == self.save_every_n_updates:
                status_text = f"Updates: {update_count} | Saved: {saved_count} lines | Next save: now"
                status_color = "orange"
            else:
                status_text = f"Updates: {update_count} | Saved: {saved_count} lines | Next save: {updates_until_save} updates"
                status_color = "green"
        else:
            status_text = f"Updates: {update_count} | No data file yet"
            status_color = "gray"
        
        ttk.Label(info_frame, text=status_text,
                  font=("Segoe UI", 9), foreground=status_color).grid(row=1, column=0, sticky="w", pady=(5, 0))

        readings_frame = ttk.Frame(readings_section)
        readings_frame.grid(row=1, column=0, sticky="ew")

        temp_frame = ttk.Frame(readings_frame)
        temp_frame.grid(row=0, column=0, padx=(0, 30))
        ttk.Label(temp_frame, text="Temperature",
                  font=self.reading_label_font).grid(row=0, column=0)
        ttk.Label(temp_frame, text=f"{data['temperature']:.1f}°C",
                  font=self.reading_value_font, foreground="#dc3545").grid(row=1, column=0)

        humid_frame = ttk.Frame(readings_frame)
        humid_frame.grid(row=0, column=1, padx=(30, 30))
        ttk.Label(humid_frame, text="Humidity",
                  font=self.reading_label_font).grid(row=0, column=0)
        ttk.Label(humid_frame, text=f"{data['humidity']:.1f}%",
                  font=self.reading_value_font, foreground="#007bff").grid(row=1, column=0)

        battery_frame = ttk.Frame(readings_frame)
        battery_frame.grid(row=0, column=2, padx=(30, 0))
        ttk.Label(battery_frame, text="Battery",
                  font=self.reading_label_font).grid(row=0, column=0)
        ttk.Label(battery_frame, text=f"{data['battery']}%",
                  font=self.reading_value_font, foreground="#28a745").grid(row=1, column=0)

        update_frame = ttk.Frame(readings_section)
        update_frame.grid(row=2, column=0, sticky="ew", pady=(15, 0))
        time_str = data['last_update'].strftime("%H:%M:%S")
        ttk.Label(update_frame, text=f"Last update: {time_str}",
                  font=("Segoe UI", 10), foreground="#6c757d").grid(row=0, column=0, sticky="w")

        # Right section - graph (larger and more visible)
        graph_section = ttk.LabelFrame(main_container, text="Temperature & Humidity Trends", padding="15")
        graph_section.grid(row=0, column=1, sticky="nsew", padx=(20, 0))

        # Always create a fresh graph for each display update
        address = data['address']
        canvas, fig, axes = self.create_graph_widget(graph_section, address)
        
        # Store the new graph (replacing any old one)
        if address in self.device_graphs:
            # Clean up the old graph
            old_canvas, old_fig, old_axes = self.device_graphs[address]
            try:
                old_canvas.get_tk_widget().destroy()
            except:
                pass  # Widget may already be destroyed
            plt.close(old_fig)
        
        self.device_graphs[address] = (canvas, fig, axes)
        canvas.get_tk_widget().grid(row=0, column=0, sticky="nsew")
        
        # Update the graph with current data
        if address in self.historical_data and len(self.historical_data[address]['timestamps']) > 0:
            self.update_graph(address)
        
        graph_section.columnconfigure(0, weight=1)
        graph_section.rowconfigure(0, weight=1)

    def get_display_name(self, address):
        return self.device_names.get(address, f"Thermometer ({address[-5:]})")

    def rename_device(self, address):
        current_name = self.device_names.get(address, "")

        dialog = tk.Toplevel(self.root)
        dialog.title("Rename Device")
        dialog.geometry("400x250")
        dialog.resizable(False, False)
        dialog.transient(self.root)
        dialog.grab_set()

        main_frame = ttk.Frame(dialog, padding="20")
        main_frame.grid(row=0, column=0, sticky="nsew")

        ttk.Label(main_frame, text=f"Device Address: {address}",
                  font=("Consolas", 10)).grid(row=0, column=0, columnspan=2, pady=(0, 15))

        ttk.Label(main_frame, text="Custom Name:",
                  font=("Segoe UI", 11)).grid(row=1, column=0, sticky="w", pady=(0, 10))

        name_var = tk.StringVar(value=current_name)
        name_entry = ttk.Entry(main_frame, textvariable=name_var, font=("Segoe UI", 11), width=30)
        name_entry.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(0, 15))
        name_entry.focus()

        # Add warning about file renaming
        warning_label = ttk.Label(main_frame, 
                                  text="Note: Changing the name will create a new data file.\nOld data file will remain with the old name.",
                                  font=("Segoe UI", 9), foreground="#856404",
                                  justify="center")
        warning_label.grid(row=3, column=0, columnspan=2, pady=(0, 15))

        def save_name():
            new_name = name_var.get().strip()
            if new_name:
                self.device_names[address] = new_name
            else:
                self.device_names.pop(address, None)
            self.save_device_names()
            if address in self.devices:
                self.devices[address]['display_name'] = self.get_display_name(address)
            self.update_display()
            dialog.destroy()

        ttk.Button(main_frame, text="Save", command=save_name).grid(row=4, column=0, padx=(0, 10))
        ttk.Button(main_frame, text="Cancel", command=dialog.destroy).grid(row=4, column=1)

    def open_names_dialog(self):
        dialog = tk.Toplevel(self.root)
        dialog.title("Manage Device Names")
        dialog.geometry("500x300")
        dialog.transient(self.root)
        dialog.grab_set()

        main_frame = ttk.Frame(dialog, padding="15")
        main_frame.grid(row=0, column=0, sticky="nsew")

        ttk.Label(main_frame, text="Device Name Management",
                  font=("Segoe UI", 14, "bold")).grid(row=0, column=0, columnspan=3, pady=(0, 15))

        all_addresses = set(self.devices.keys()) | set(self.device_names.keys())

        if not all_addresses:
            ttk.Label(main_frame, text="No devices found yet.",
                      font=("Segoe UI", 11), foreground="#6c757d").grid(row=1, column=0, columnspan=3, pady=20)
        else:
            for i, address in enumerate(sorted(all_addresses), start=1):
                ttk.Label(main_frame, text=address,
                          font=("Consolas", 10)).grid(row=i, column=0, sticky="w", padx=(0, 15), pady=5)
                current_name = self.device_names.get(address, "(default)")
                ttk.Label(main_frame, text=current_name,
                          font=("Segoe UI", 10)).grid(row=i, column=1, sticky="w", padx=(0, 15), pady=5)
                edit_btn = ttk.Button(main_frame, text="Edit",
                                      command=lambda addr=address: self.rename_device_from_manager(addr, dialog))
                edit_btn.grid(row=i, column=2, pady=5)

        ttk.Button(main_frame, text="Close", command=dialog.destroy).grid(
            row=len(all_addresses) + 2, column=0, columnspan=3, pady=(15, 0))

        dialog.columnconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)

    def rename_device_from_manager(self, address, manager_dialog):
        manager_dialog.destroy()
        self.rename_device(address)
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
        await asyncio.sleep(5)
        await scanner.stop()
        self.root.after(0, lambda: self.status_label.config(
            text="Single scan completed", foreground="gray"))

    def clear_devices(self):
        # Properly clean up graphs before clearing devices
        for addr in list(self.device_graphs.keys()):
            canvas, fig, axes = self.device_graphs[addr]
            canvas.get_tk_widget().destroy()
            plt.close(fig)
        
        self.devices.clear()
        self.update_counts.clear()  # Also clear update counts when clearing devices
        self.historical_data.clear()  # Clear historical data for graphs
        self.device_graphs.clear()  # Clear graph references
        self.update_display()


def main():
    root = tk.Tk()
    app = GoveeThermometerGUI(root)

    def on_closing():
        if app.scanning:
            app.stop_scanning()
        app.save_device_names()
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_closing)
    root.mainloop()


if __name__ == "__main__":
    main()