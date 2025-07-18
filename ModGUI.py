import tkinter as tk
import tkinter.simpledialog as simpledialog
import math
import os
import sys
from pymodbus.client import ModbusTcpClient
from threading import Thread
import time
from functools import partial
from PIL import Image, ImageTk
import requests

# --- Modbus Configuration (Constants) ---
MODBUS_PORT = 502
REGISTER_ADDR = 1      # Register Address for the main counter
REGISTER_COUNT = 1
VELOCITY_ADDR = 3      # Register Address for velocity
TURN_ADDR = 7          # Register Address for the turn counter
CCW_ADDR = 18          # Register Address for rotation direction (0=CCW, 1=CW)
SLAVE_ID = 1           # The Modbus Slave ID of the device

# --- GUI Class ---
class ModbusGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Rotary Encoder Visualizer")

        # --- App State Variables ---
        self.client = None
        self.modbus_thread = None
        self.running = False
        self.is_initialized = False
        self.last_rotation_direction = 0

        # --- Style and Color Configuration ---
        self.colors = {
            "bg": "#B1B1B1",
            "canvas_bg": "#FFFFFF",
            "dial_outline": "#505050",
            "text_main": "#000000",
            "text_accent": "#4E4E4E",
            "needle": "#ED1F29",
            "tick": "#909090",
            "button_bg": "#ED1F29",
            "button_fg": "#FFFFFF",
            "status_ok": "#4CAF50",      
            "status_error": "#F44336"   
        }
        self.fonts = {
            "main": ("Segoe UI", 12),
            "value": ("Segoe UI Semibold", 28),
            "features": ("Segoe UI Semibold", 18),
            "title": ("Segoe UI Bold", 16),
            "compass": ("Segoe UI", 14),
            "button": ("Segoe UI Semibold", 11),
            "status": ("Segoe UI Semibold", 14)
        }
        
        self.root.configure(bg=self.colors["bg"])

        # --- Load Logo Image (Robust Method) ---
        self.logo_photo = None  # Store a reference to prevent garbage collection
        try:
            script_dir = os.path.dirname(os.path.abspath(__file__))
            logo_path = os.path.join(script_dir, "JoralLogo.png")
            img = Image.open(logo_path)
            img = img.resize((180, 60), Image.Resampling.LANCZOS)
            self.logo_photo = ImageTk.PhotoImage(img)
        except Exception as e:
            print(f"Warning: Could not load JoralLogo.png. {e}")

        # --- Storage for Canvas Item IDs ---
        self.tick_lines = {}
        self.tick_labels = {}
        self.arrow_poly = None
        
        # --- UI Setup ---
        self.setup_ui()

    def setup_ui(self):
        """Creates the main frames and widgets for the application."""
        main_frame = tk.Frame(self.root, bg=self.colors["bg"])
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        # --- Top Frame for Logo and Title ---
        top_frame = tk.Frame(main_frame, bg=self.colors["bg"])
        top_frame.pack(side=tk.TOP, fill=tk.X)
        top_frame.grid_columnconfigure(0, weight=1, uniform="equal")
        top_frame.grid_columnconfigure(1, weight=2)
        top_frame.grid_columnconfigure(2, weight=1, uniform="equal")

        if self.logo_photo:
            logo_label = tk.Label(top_frame, image=self.logo_photo, bg=self.colors["bg"])
            logo_label.grid(row=0, column=0, sticky="w")
        
        title_label = tk.Label(top_frame, text="Rotary Encoder Visualizer", font=self.fonts["title"], bg=self.colors["bg"], fg=self.colors["text_accent"])
        title_label.grid(row=0, column=1)

        # --- Bottom Frame for IP and Action Controls ---
        bottom_frame = tk.Frame(main_frame, bg=self.colors["bg"])
        bottom_frame.pack(side=tk.BOTTOM, fill=tk.X, pady=(10,0))

        # --- MOVED: Frame for action buttons, now in the bottom bar ---
        action_frame = tk.Frame(bottom_frame, bg=self.colors["bg"])
        action_frame.pack(side=tk.LEFT, padx=10) # Packed to the left
        
        self.toggle_button = tk.Button(action_frame, text="Toggle Direction", font=self.fonts["button"], bg=self.colors["button_bg"], fg=self.colors["button_fg"], command=self.toggle_direction)
        self.zero_button = tk.Button(action_frame, text="Zero Encoder", font=self.fonts["button"], bg=self.colors["button_bg"], fg=self.colors["button_fg"], command=self.zero_encoder)
        self.release_zero_button = tk.Button(action_frame, text="Release Zero", font=self.fonts["button"], bg=self.colors["button_bg"], fg=self.colors["button_fg"], command=self.release_zero)

        # Buttons are now in a horizontal row
        self.toggle_button.pack(side=tk.LEFT, padx=(0, 5))
        self.zero_button.pack(side=tk.LEFT, padx=(0, 5))
        self.release_zero_button.pack(side=tk.LEFT)
        
        # IP controls are packed to the right, so they appear on the other side
        ip_controls_frame = tk.Frame(bottom_frame, bg=self.colors["bg"])
        ip_controls_frame.pack(side=tk.RIGHT, padx=10) 

        tk.Label(ip_controls_frame, text="IP Address:", font=self.fonts["main"], bg=self.colors["bg"], fg=self.colors["text_main"]).pack(side=tk.LEFT, padx=(0,5))
        
        self.ip_entry = tk.Entry(ip_controls_frame, font=self.fonts["main"], width=15)
        self.ip_entry.pack(side=tk.LEFT)
        self.ip_entry.insert(0, "192.168.30.220") 
        
        self.connect_button = tk.Button(ip_controls_frame, text="Connect", font=self.fonts["button"], bg=self.colors["button_bg"], fg=self.colors["button_fg"], command=self.connect_to_ip)
        self.connect_button.pack(side=tk.LEFT, padx=(5,0))
        
        # --- Content Frame for Sidebars and Canvas ---
        content_frame = tk.Frame(main_frame, bg=self.colors["bg"])
        content_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True, pady=(10,0))

        # --- Status Panel (Left Side) ---
        left_status_frame = tk.Frame(content_frame, bg=self.colors["bg"], width=250)
        left_status_frame.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 20), anchor='n')
        left_status_frame.pack_propagate(False)

        tk.Label(left_status_frame, text="CONNECTION", font=self.fonts["title"], bg=self.colors["bg"], fg=self.colors["text_accent"]).pack(anchor="w")
        
        self.connection_status_label = tk.Label(left_status_frame, text="DISCONNECTED", font=self.fonts["status"], bg=self.colors["bg"], fg=self.colors["status_error"])
        self.connection_status_label.pack(anchor="w", pady=(5, 15))
        
        tk.Label(left_status_frame, text="DATA READOUTS", font=self.fonts["title"], bg=self.colors["bg"], fg=self.colors["text_accent"]).pack(anchor="w", pady=(10, 0))
        
        tk.Label(left_status_frame, text="Position Counts", font=self.fonts["main"], bg=self.colors["bg"], fg=self.colors["text_main"]).pack(anchor="w", pady=(15, 0))
        self.counter_label = tk.Label(left_status_frame, text="--", font=self.fonts["value"], bg=self.colors["bg"], fg=self.colors["text_main"])
        self.counter_label.pack(anchor="w")

        tk.Label(left_status_frame, text="Total Turns", font=self.fonts["main"], bg=self.colors["bg"], fg=self.colors["text_main"]).pack(anchor="w", pady=(15, 0))
        self.turn_label = tk.Label(left_status_frame, text="--", font=self.fonts["value"], bg=self.colors["bg"], fg=self.colors["text_main"])
        self.turn_label.pack(anchor="w")

        tk.Label(left_status_frame, text="Velocity (RPM)", font=self.fonts["main"], bg=self.colors["bg"], fg=self.colors["text_main"]).pack(anchor="w", pady=(15, 0))
        self.velocity_label = tk.Label(left_status_frame, text="--", font=self.fonts["value"], bg=self.colors["bg"], fg=self.colors["text_main"])
        self.velocity_label.pack(anchor="w")

        tk.Label(left_status_frame, text="Direction", font=self.fonts["main"], bg=self.colors["bg"], fg=self.colors["text_main"]).pack(anchor="w", pady=(15, 0))
        self.direction_label = tk.Label(left_status_frame, text="--", font=self.fonts["value"], bg=self.colors["bg"], fg=self.colors["text_main"])
        self.direction_label.pack(anchor="w")
        
        # --- Features Panel (Right Side) ---
        right_features_frame = tk.Frame(content_frame, bg=self.colors["bg"], width=300)
        right_features_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=(20, 0), anchor='n')
        right_features_frame.pack_propagate(False)

        tk.Label(right_features_frame, text="FEATURES", font=self.fonts["features"], bg=self.colors["bg"], fg=self.colors["text_accent"]).pack(anchor="w", pady=(10, 0))
        tk.Label(right_features_frame, text="- Dual Protocol Ethernet/IP\n& Modbus", font=self.fonts["features"], bg=self.colors["bg"], fg=self.colors["text_main"], justify=tk.LEFT).pack(anchor="w", pady=(10,0))
        tk.Label(right_features_frame, text="- Web Browser\nConfiguration", font=self.fonts["features"], bg=self.colors["bg"], fg=self.colors["text_main"], justify=tk.LEFT).pack(anchor="w")
        tk.Label(right_features_frame, text="- Static IP or DHCP", font=self.fonts["features"], bg=self.colors["bg"], fg=self.colors["text_main"], justify=tk.LEFT).pack(anchor="w")
        tk.Label(right_features_frame, text="- IP69K Rated", font=self.fonts["features"], bg=self.colors["bg"], fg=self.colors["text_main"], justify=tk.LEFT).pack(anchor="w")
        
        # --- Canvas for Compass (Middle) ---
        self.canvas = tk.Canvas(content_frame, bg=self.colors["canvas_bg"], highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True) 
        self.canvas.bind("<Configure>", self.on_canvas_resize)

    def connect_to_ip(self):
        """Handles connecting to a new IP address, including cleanup of old connections."""
        # 1. Stop any existing connection thread
        if self.modbus_thread and self.modbus_thread.is_alive():
            print("Stopping previous Modbus connection...")
            self.running = False
            self.modbus_thread.join(timeout=2) # Wait for thread to finish
            if self.client and self.client.is_socket_open():
                self.client.close()

        # 2. Get the new IP and create a new client
        ip_address = self.ip_entry.get()
        if not ip_address:
            print("Error: IP address cannot be empty.")
            return
            
        print(f"Attempting to connect to {ip_address}...")
        self.client = ModbusTcpClient(ip_address, port=MODBUS_PORT)
        
        # 3. Reset state and start a new connection thread
        self.is_initialized = False

        self.canvas.delete("all")
        self.tick_lines.clear()
        self.tick_labels.clear()
        self.arrow_poly = None

        self.running = True
        self.modbus_thread = Thread(target=self.update_loop, daemon=True)
        self.modbus_thread.start()

    def update_loop(self):
        """Background thread to continuously read Modbus data."""
        rotation_prev = -1
        
        # This loop will terminate if self.running is set to False
        while self.running:
            try:
                # Use the instance client, not a global one
                if not self.client.is_socket_open():
                    self.root.after(0, self.update_connection_status, False)
                    self.client.connect()
                
                if not self.client.is_socket_open():
                    time.sleep(2)
                    continue

                # Draw the compass for the first time on a new connection
                if not self.is_initialized:
                    init_rot_res = self.client.read_holding_registers(address=CCW_ADDR, count=REGISTER_COUNT, slave=SLAVE_ID)
                    if init_rot_res.isError():
                        print("Failed to read initial rotation. Retrying...")
                        time.sleep(1)
                        continue
                    
                    initial_rotation = init_rot_res.registers[0]
                    self.root.after(0, self.draw_initial_compass, initial_rotation)
                    self.is_initialized = True
                    print("Initial compass drawn.")

                # Read all registers
                rotation_res = self.client.read_holding_registers(address=CCW_ADDR, count=REGISTER_COUNT, slave=SLAVE_ID)
                counter_res = self.client.read_holding_registers(address=REGISTER_ADDR, count=REGISTER_COUNT, slave=SLAVE_ID)
                turns_res = self.client.read_holding_registers(address=TURN_ADDR, count=REGISTER_COUNT, slave=SLAVE_ID)
                velocity_res = self.client.read_holding_registers(address=VELOCITY_ADDR, count=REGISTER_COUNT, slave=SLAVE_ID)
                
                if any([res.isError() for res in [rotation_res, counter_res, turns_res, velocity_res]]):
                    print("Modbus error during read.")
                    time.sleep(1)
                    continue

                self.root.after(0, self.update_connection_status, True)

                # Process and update GUI
                rotation = rotation_res.registers[0]
                value = counter_res.registers[0]
                turns = turns_res.registers[0]
                velocity = velocity_res.registers[0]

                if turns > 32767:
                    turns -= 65536
                
                if rotation != rotation_prev:
                    for angle in range(0, 360, 10):
                        self.root.after(0, self.update_tick, angle, rotation)
                    rotation_prev = rotation
                
                self.root.after(0, self.update_arrow, value, rotation)
                self.root.after(0, self.update_gui_labels, value, turns, rotation, velocity)

            except Exception as e:
                # This block will catch connection errors if the IP is wrong
                print(f"Modbus connection failed: {e}")
                self.root.after(0, self.update_connection_status, False)
                if self.client and self.client.is_socket_open():
                    self.client.close()
                time.sleep(2)
            
            # If the loop is still running, pause before the next read
            if self.running:
                time.sleep(0.1)
        
        print("Modbus thread has stopped.")

    def draw_initial_compass(self, initial_rotation):
        """Draws the static elements of the compass dial."""
        # Main dial outline
        self.canvas.create_oval(self.center[0] - self.radius, self.center[1] - self.radius, self.center[0] + self.radius, self.center[1] + self.radius, outline=self.colors["dial_outline"], width=10)
        # Center pivot
        self.canvas.create_oval(self.center[0] - 8, self.center[1] - 8, self.center[0] + 8, self.center[1] + 8, fill=self.colors["needle"], outline="")
        
        # Draw ticks for the first time using the rotation value from the thread
        for angle in range(0, 360, 10):
            self.update_tick(angle, initial_rotation)

    def update_tick(self, angle_deg, rotation_mode):
        """Creates or updates a single compass tick and its label, with major/minor ticks."""
        if rotation_mode == 1: # CW
            angle_rad = math.radians(angle_deg - 90)
        else: # CCW
            angle_rad = math.radians(-angle_deg - 90)

        is_major_tick = (angle_deg % 45 == 0)
        tick_length = 30 if is_major_tick else 15
        tick_width = 5 if is_major_tick else 3

        x1 = self.center[0] + self.radius * math.cos(angle_rad)
        y1 = self.center[1] + self.radius * math.sin(angle_rad)
        x2 = self.center[0] + (self.radius - tick_length) * math.cos(angle_rad)
        y2 = self.center[1] + (self.radius - tick_length) * math.sin(angle_rad)
        
        if angle_deg in self.tick_lines:
            self.canvas.coords(self.tick_lines[angle_deg], x1, y1, x2, y2)
            self.canvas.itemconfig(self.tick_lines[angle_deg], width=tick_width)
            
            if is_major_tick and angle_deg in self.tick_labels:
                label_x = self.center[0] + (self.radius + 35) * math.cos(angle_rad)
                label_y = self.center[1] + (self.radius + 35) * math.sin(angle_rad)
                self.canvas.coords(self.tick_labels[angle_deg], label_x, label_y)
        else:
            line_id = self.canvas.create_line(x1, y1, x2, y2, width=tick_width, fill=self.colors["tick"])
            self.tick_lines[angle_deg] = line_id
            
            if is_major_tick:
                label_x = self.center[0] + (self.radius + 35) * math.cos(angle_rad)
                label_y = self.center[1] + (self.radius + 35) * math.sin(angle_rad)
                label_id = self.canvas.create_text(label_x, label_y, text=f"{angle_deg}°", font=self.fonts["compass"], fill=self.colors["text_main"])
                self.tick_labels[angle_deg] = label_id

    def update_arrow(self, modbus_value, rotation_mode):
        """Creates or updates the needle polygon."""
        angle_deg = (modbus_value % 4096) * 360 / 4096.0

        if rotation_mode == 1: # CW
            angle_rad = math.radians(angle_deg - 90)
        else: # CCW
            angle_rad = math.radians(-angle_deg - 90)

        arrow_length = self.radius - 15
        p2 = (self.center[0] + arrow_length * math.cos(angle_rad), self.center[1] + arrow_length * math.sin(angle_rad))
        p3 = (self.center[0] + 10 * math.cos(angle_rad + math.pi/2), self.center[1] + 10 * math.sin(angle_rad + math.pi/2))
        p4 = (self.center[0] + 10 * math.cos(angle_rad - math.pi/2), self.center[1] + 10 * math.sin(angle_rad - math.pi/2))
        
        coords = [p3[0], p3[1], p2[0], p2[1], p4[0], p4[1]]

        if self.arrow_poly:
            self.canvas.coords(self.arrow_poly, *coords)
        else:
            self.arrow_poly = self.canvas.create_polygon(coords, fill=self.colors["needle"], outline="")

    def update_connection_status(self, is_connected):
        """Thread-safe method to update the connection status indicator."""
        if is_connected:
            self.connection_status_label.config(text="CONNECTED", fg=self.colors["status_ok"])
        else:
            self.connection_status_label.config(text="DISCONNECTED", fg=self.colors["status_error"])

    def update_gui_labels(self, counter_val, turns_val, rotation_val, velocity_val):
        """Thread-safe method to update the text labels in the status panel."""
        self.last_rotation_direction = rotation_val

        self.counter_label.config(text=str(counter_val))
        self.turn_label.config(text=str(turns_val))
        self.velocity_label.config(text=str(velocity_val))
        
        if rotation_val == 1:
            self.direction_label.config(text="CW")
            self.toggle_button.config(text="Switch to CCW")
        else:
            self.direction_label.config(text="CCW")
            self.toggle_button.config(text="Switch to CW")
    
    def toggle_direction(self):
        """Reads the current direction and writes the opposite value back."""
        if not (self.client and self.client.is_socket_open()):
            print("Cannot toggle direction: Not connected.")
            return

        print("Toggle button pressed. Attempting to switch direction...")
        self.toggle_button.config(state=tk.DISABLED, text="Switching...")
        try:
            current_dir_res = self.client.read_holding_registers(address=CCW_ADDR, count=1, slave=SLAVE_ID)
            if current_dir_res.isError():
                print("Error: Could not read current direction.")
                return
            
            current_dir = current_dir_res.registers[0]
            new_dir = 1 - current_dir
            
            write_res = self.client.write_register(address=CCW_ADDR, value=new_dir, slave=SLAVE_ID)
            if write_res.isError():
                print(f"Error: Failed to write new direction to register {CCW_ADDR}")
            else:
                print("Success: Direction register updated.")
        except Exception as e:
            print(f"An exception occurred while toggling direction: {e}")
        finally:
            self.root.after(500, lambda: self.toggle_button.config(state=tk.NORMAL))

    def on_canvas_resize(self, event):
        """Redraws the compass whenever the canvas size changes."""
        # Recalculate the new center and radius
        self.center = (event.width / 2, event.height / 2)
        self.radius = min(event.width, event.height) * 0.4

        # Clear everything from the canvas and from our state trackers
        self.canvas.delete("all")
        self.tick_lines.clear()
        self.tick_labels.clear()
        self.arrow_poly = None

        # Redraw the base compass if we have already connected once
        if self.is_initialized:
            self.draw_initial_compass(self.last_rotation_direction)

    def zero_encoder(self):
        # Sends HTTP POST request to zero encoder
        
        #Confirmation dialog 
        if not tk.messagebox.askyesno("Confirm", "You are about to zero the encoder position. Are you sure?"):
            return
        
        try:
            # Get the current IP from the entry box
            ip_address = self.ip_entry.get()
            if not ip_address:
                tk.messagebox.showerror("Error", "IP Address cannot be empty.")
                return

            # Construct the URL. Most embedded devices use http, not https.
            url = f"http://{ip_address}/zero_offset"
            print(f"Sending POST request to {url}...")

            # Send the web request with a 5-second timeout
            response = requests.post(url, timeout=5)

            # Check if the request was successful (status code 200-299)
            if response.ok:
                print("Success: Zero command sent via HTTP.")
                tk.messagebox.showinfo("Success", "Encoder zero command sent successfully.")
            else:
                # The request went through but the server responded with an error
                error_message = f"Failed to send zero command. Status Code: {response.status_code}"
                print(error_message)
                tk.messagebox.showerror("HTTP Error", error_message)

        except requests.exceptions.RequestException as e:
            # This catches network errors like timeouts, DNS failures, or connection refused
            print(f"An exception occurred while zeroing encoder: {e}")
            tk.messagebox.showerror("Connection Error", f"Could not connect to the encoder.\n\n{e}")

    def release_zero(self):
        """Asks for confirmation and sends an HTTP POST request to release the zero offset."""
        
        # Confirmation dialog
        if not tk.messagebox.askyesno("Confirm", "You are about to release the encoder's zero offset. Are you sure?"):
            return
        
        try:
            # Get the current IP from the entry box
            ip_address = self.ip_entry.get()
            if not ip_address:
                tk.messagebox.showerror("Error", "IP Address cannot be empty.")
                return

            # Construct the URL for the release function
            url = f"http://{ip_address}/release_offset"
            print(f"Sending POST request to {url}...")

            # Send the web request
            response = requests.post(url, timeout=5)

            if response.ok:
                print("Success: Release zero command sent via HTTP.")
                tk.messagebox.showinfo("Success", "Release zero command sent successfully.")
            else:
                error_message = f"Failed to send release zero command. Status Code: {response.status_code}"
                print(error_message)
                tk.messagebox.showerror("HTTP Error", error_message)

        except requests.exceptions.RequestException as e:
            print(f"An exception occurred while releasing zero: {e}")
            tk.messagebox.showerror("Connection Error", f"Could not connect to the encoder.\n\n{e}")


    def close(self):
        """Cleanly close the application."""
        print("Closing application...")
        self.running = False
        if self.modbus_thread and self.modbus_thread.is_alive():
            self.modbus_thread.join(timeout=1)
        if self.client and self.client.is_socket_open():
            self.client.close()
        self.root.destroy()

# --- NEW Launch GUI Block ---
if __name__ == "__main__":
    root = tk.Tk()
    root.geometry("1400x900")

    gui = ModbusGUI(root)
    root.protocol("WM_DELETE_WINDOW", gui.close)
    root.mainloop()