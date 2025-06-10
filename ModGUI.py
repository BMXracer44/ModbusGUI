import tkinter as tk
import math
import os
from pymodbus.client.sync import ModbusTcpClient
from threading import Thread
import time
from functools import partial
from PIL import Image, ImageTk

# --- Modbus Configuration ---
MODBUS_HOST = '192.168.30.218'  # Modbus Device IP
MODBUS_PORT = 502
REGISTER_ADDR = 1  # Register Address for the main counter
REGISTER_COUNT = 1
VELOCITY_ADDR = 3  # Register Address for velocity
TURN_ADDR = 7      # Register Address for the turn counter
CCW_ADDR = 18      # Register Address for rotation direction (0=CCW, 1=CW)

# --- Create Modbus Client ---
client = ModbusTcpClient(MODBUS_HOST, port=MODBUS_PORT)

# --- GUI Class ---
class ModbusGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Rotary Encoder Visualizer")
        
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
            "status_ok": "#4CAF50",      # Green for connected
            "status_error": "#F44336"   # Red for disconnected
        }
        self.fonts = {
            "main": ("Segoe UI", 12),
            "value": ("Segoe UI Semibold", 28),
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
            logo_path = os.path.join(script_dir, "JoralLogo.png") # Updated to PNG
            
            print(f"Attempting to load logo from: {logo_path}")
            
            img = Image.open(logo_path)
            img = img.resize((180, 60), Image.Resampling.LANCZOS)
            self.logo_photo = ImageTk.PhotoImage(img)
        except FileNotFoundError:
            print("Warning: JoralLogo.png not found. Make sure it is in the same directory as the script.")
        except Exception as e:
            print(f"Error loading logo: {e}")

        # --- Storage for Canvas Item IDs ---
        self.tick_lines = {}
        self.tick_labels = {}
        self.arrow_poly = None
        
        # --- UI Setup ---
        self.setup_ui()

        # --- Initial Drawing ---
        self.draw_initial_compass()

        # --- Start Background Thread ---
        self.running = True
        self.modbus_thread = Thread(target=self.update_loop, daemon=True)
        self.modbus_thread.start()

    def setup_ui(self):
        """Creates the main frames and widgets for the application."""
        # Main container frame
        main_frame = tk.Frame(self.root, bg=self.colors["bg"])
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        # --- Top Frame for Logo ---
        top_frame = tk.Frame(main_frame, bg=self.colors["bg"])
        top_frame.pack(side=tk.TOP, fill=tk.X)
        
        if self.logo_photo:
            # Store the label as an instance attribute to prevent garbage collection
            self.logo_label = tk.Label(top_frame, image=self.logo_photo, bg=self.colors["bg"])
            self.logo_label.pack(side=tk.LEFT) # Pack to the left within the top frame


        self.title_label = tk.Label(top_frame, text="Rotary Ethernet/IP Encoder w/ Modbus", font=self.fonts["title"], bg=self.colors["bg"], fg=self.colors["text_main"])
        self.title_label.pack(side=tk.LEFT, fill=tk.Y, padx=(20,0))

        # --- Content Frame for Status and Canvas ---
        content_frame = tk.Frame(main_frame, bg=self.colors["bg"])
        content_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True, pady=(10,0))

        # Status Panel (Left Side)
        status_frame = tk.Frame(content_frame, bg=self.colors["bg"])
        status_frame.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 20))

        tk.Label(status_frame, text="CONNECTION", font=self.fonts["title"], bg=self.colors["bg"], fg=self.colors["text_accent"]).pack(anchor="w")
        self.connection_status_label = tk.Label(status_frame, text="DISCONNECTED", font=self.fonts["status"], bg=self.colors["bg"], fg=self.colors["status_error"])
        self.connection_status_label.pack(anchor="w", pady=(5, 15))
        
        tk.Label(status_frame, text="DATA READOUTS", font=self.fonts["title"], bg=self.colors["bg"], fg=self.colors["text_accent"]).pack(anchor="w", pady=(10, 0))
        
        tk.Label(status_frame, text="Position Counts", font=self.fonts["main"], bg=self.colors["bg"], fg=self.colors["text_main"]).pack(anchor="w", pady=(15, 0))
        self.counter_label = tk.Label(status_frame, text="--", font=self.fonts["value"], bg=self.colors["bg"], fg=self.colors["text_main"])
        self.counter_label.pack(anchor="w")

        tk.Label(status_frame, text="Total Turns", font=self.fonts["main"], bg=self.colors["bg"], fg=self.colors["text_main"]).pack(anchor="w", pady=(15, 0))
        self.turn_label = tk.Label(status_frame, text="--", font=self.fonts["value"], bg=self.colors["bg"], fg=self.colors["text_main"])
        self.turn_label.pack(anchor="w")

        tk.Label(status_frame, text="Velocity (RPM)", font=self.fonts["main"], bg=self.colors["bg"], fg=self.colors["text_main"]).pack(anchor="w", pady=(15, 0))
        self.velocity_label = tk.Label(status_frame, text="--", font=self.fonts["value"], bg=self.colors["bg"], fg=self.colors["text_main"])
        self.velocity_label.pack(anchor="w")

        tk.Label(status_frame, text="Direction", font=self.fonts["main"], bg=self.colors["bg"], fg=self.colors["text_main"]).pack(anchor="w", pady=(15, 0))
        self.direction_label = tk.Label(status_frame, text="--", font=self.fonts["value"], bg=self.colors["bg"], fg=self.colors["text_main"])
        self.direction_label.pack(anchor="w")

        # --- Direction Toggle Button ---
        self.toggle_button = tk.Button(status_frame, text="Toggle Direction",
                                       font=self.fonts["button"],
                                       bg=self.colors["button_bg"],
                                       fg=self.colors["button_fg"],
                                       activebackground=self.colors["text_accent"],
                                       activeforeground=self.colors["bg"],
                                       relief=tk.FLAT,
                                       padx=10, pady=5,
                                       command=self.toggle_direction)
        self.toggle_button.pack(anchor="w", pady=(30, 0))

        # Status Panel (Right Side)
        status_frame = tk.Frame(content_frame, bg=self.colors["bg"])
        status_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=(20, 0))

        tk.Label(status_frame, text="FEATURES", font=self.fonts["value"], bg=self.colors["bg"], fg=self.colors["text_main"]).pack(anchor="w")
        
        self.feature1_label = tk.Label(status_frame, text=" - Dual Protocol Ethernet/IP \n  and Modbus Connectivity", font=self.fonts["title"], bg=self.colors["bg"], fg=self.colors["text_accent"])
        self.feature1_label.pack(anchor="w")

        self.feature2_label = tk.Label(status_frame, text=" - Web Browser for Easy\n  Encoder Configuration", font=self.fonts["title"], bg=self.colors["bg"], fg=self.colors["text_accent"])
        self.feature2_label.pack(anchor="w")

        self.feature3_label = tk.Label(status_frame, text=" - Static IP or DHCP", font=self.fonts["title"], bg=self.colors["bg"], fg=self.colors["text_accent"])
        self.feature3_label.pack(anchor="w")

        self.feature4_label = tk.Label(status_frame, text=" - IP69K Rated", font=self.fonts["title"], bg=self.colors["bg"], fg=self.colors["text_accent"])
        self.feature4_label.pack(anchor="w")

        # Canvas for Compass (Right Side)
        canvas_width = self.root.winfo_screenwidth() * 0.5
        canvas_height = self.root.winfo_screenheight() * 0.6
        self.canvas = tk.Canvas(content_frame, width=canvas_width, height=canvas_height, bg=self.colors["canvas_bg"], highlightthickness=0)
        self.canvas.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        self.center = (canvas_width / 2, canvas_height / 2)
        self.radius = min(canvas_width, canvas_height) * 0.4

    def draw_initial_compass(self):
        """Draws the static elements of the compass dial."""
        # Main dial outline
        self.canvas.create_oval(
            self.center[0] - self.radius, self.center[1] - self.radius,
            self.center[0] + self.radius, self.center[1] + self.radius,
            outline=self.colors["dial_outline"], width=10
        )
        # Center pivot
        self.canvas.create_oval(
            self.center[0] - 8, self.center[1] - 8,
            self.center[0] + 8, self.center[1] + 8,
            fill=self.colors["needle"], outline=""
        )
        
        # Draw ticks for the first time
        try:
            initial_rotation = client.read_holding_registers(CCW_ADDR, REGISTER_COUNT, unit=1).registers[0]
        except Exception:
            initial_rotation = 1  # Default to CW
            
        # Draw a tick every 10 degrees
        for angle in range(0, 360, 10):
            self.update_tick(angle, initial_rotation)

    def update_tick(self, angle_deg, rotation_mode):
        """Creates or updates a single compass tick and its label, with major/minor ticks."""
        if rotation_mode == 1:
            angle_rad = math.radians(angle_deg - 90)
        else:
            angle_rad = math.radians(-angle_deg - 90)

        # Differentiate between major (every 45 deg) and minor (every 10 deg) ticks
        is_major_tick = (angle_deg % 45 == 0)
        tick_length = 30 if is_major_tick else 15
        tick_width = 5 if is_major_tick else 3

        # Coordinates for tick mark
        x1 = self.center[0] + self.radius * math.cos(angle_rad)
        y1 = self.center[1] + self.radius * math.sin(angle_rad)
        x2 = self.center[0] + (self.radius - tick_length) * math.cos(angle_rad)
        y2 = self.center[1] + (self.radius - tick_length) * math.sin(angle_rad)
        
        if angle_deg in self.tick_lines:
            # Update existing line
            self.canvas.coords(self.tick_lines[angle_deg], x1, y1, x2, y2)
            self.canvas.itemconfig(self.tick_lines[angle_deg], width=tick_width)
            
            # Update existing label if it's a major tick
            if is_major_tick and angle_deg in self.tick_labels:
                label_x = self.center[0] + (self.radius + 35) * math.cos(angle_rad)
                label_y = self.center[1] + (self.radius + 35) * math.sin(angle_rad)
                self.canvas.coords(self.tick_labels[angle_deg], label_x, label_y)
        else:
            # Create new line
            line_id = self.canvas.create_line(x1, y1, x2, y2, width=tick_width, fill=self.colors["tick"])
            self.tick_lines[angle_deg] = line_id
            
            # Create new label only for major ticks
            if is_major_tick:
                label_x = self.center[0] + (self.radius + 35) * math.cos(angle_rad)
                label_y = self.center[1] + (self.radius + 35) * math.sin(angle_rad)
                label_id = self.canvas.create_text(label_x, label_y, text=f"{angle_deg}°", font=self.fonts["compass"], fill=self.colors["text_main"])
                self.tick_labels[angle_deg] = label_id

    def update_arrow(self, modbus_value, rotation_mode):
        """Creates or updates the needle polygon."""
        angle_deg = (modbus_value % 4096) * 360 / 4096.0

        if rotation_mode == 1:
            angle_rad = math.radians(angle_deg - 90)
        else:
            angle_rad = math.radians(-angle_deg - 90)

        # Define the polygon shape for the needle
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
        print("Toggle button pressed. Attempting to switch direction...")
        self.toggle_button.config(state=tk.DISABLED, text="Switching...")
        try:
            current_dir_res = client.read_holding_registers(CCW_ADDR, 1, unit=1)
            if current_dir_res.isError():
                print("Error: Could not read current direction.")
                self.toggle_button.config(state=tk.NORMAL)
                return
            
            current_dir = current_dir_res.registers[0]
            new_dir = 1 - current_dir # Flips 0 to 1 and 1 to 0
            
            print(f"Current is {current_dir}. Writing new direction: {new_dir}")
            write_res = client.write_register(CCW_ADDR, new_dir, unit=1)
            
            if write_res.isError():
                print(f"Error: Failed to write new direction to register {CCW_ADDR}")
            else:
                print("Success: Direction register updated.")

        except Exception as e:
            print(f"An exception occurred while toggling direction: {e}")
        finally:
            self.root.after(500, lambda: self.toggle_button.config(state=tk.NORMAL))


    def update_loop(self):
        """Background thread to continuously read Modbus data."""
        rotation_prev = -1

        while self.running:
            try:
                if not client.is_socket_open():
                    self.root.after(0, self.update_connection_status, False)
                    print("Connecting to Modbus device...")
                    client.connect()
                
                rotation_res = client.read_holding_registers(CCW_ADDR, REGISTER_COUNT, unit=1)
                counter_res = client.read_holding_registers(REGISTER_ADDR, REGISTER_COUNT, unit=1)
                turns_res = client.read_holding_registers(TURN_ADDR, REGISTER_COUNT, unit=1)
                velocity_res = client.read_holding_registers(VELOCITY_ADDR, REGISTER_COUNT, unit=1)
                
                if rotation_res.isError() or counter_res.isError() or turns_res.isError() or velocity_res.isError():
                    print("Modbus error during read.")
                    # Don't change connection status on a read error, only on a connect failure
                    time.sleep(1)
                    continue

                # If we successfully read, we are connected
                self.root.after(0, self.update_connection_status, True)

                rotation = rotation_res.registers[0]
                value = counter_res.registers[0]
                turns = turns_res.registers[0]
                velocity = velocity_res.registers[0]

                if turns > 32767:
                    turns -= 65536
                
                # --- Schedule GUI Updates ---
                if rotation != rotation_prev:
                    print(f"Rotation changed to {'CW' if rotation == 1 else 'CCW'}")
                    # Update all ticks when direction changes
                    for angle in self.tick_lines.keys():
                        update_func = partial(self.update_tick, angle, rotation)
                        self.root.after(0, update_func)
                    rotation_prev = rotation
                
                self.root.after(0, self.update_arrow, value, rotation)
                self.root.after(0, self.update_gui_labels, value, turns, rotation, velocity)

            except Exception as e:
                print(f"Modbus connection failed: {e}")
                self.root.after(0, self.update_connection_status, False)
                if client.is_socket_open():
                    client.close()
                time.sleep(2)
            
            time.sleep(0.1)

    def close(self):
        """Cleanly close the application."""
        print("Closing application...")
        self.running = False
        self.modbus_thread.join(timeout=1)
        if client.is_socket_open():
            client.close()
        self.root.destroy()

# --- Launch GUI ---
if __name__ == "__main__":
    root = tk.Tk()
    gui = ModbusGUI(root)
    root.protocol("WM_DELETE_WINDOW", gui.close)
    root.mainloop()

