import tkinter as tk
import math
from pymodbus.client.sync import ModbusTcpClient
from threading import Thread
import time
from functools import partial

# --- Modbus Configuration ---
MODBUS_HOST = '192.168.30.218'  # Modbus Device IP
MODBUS_PORT = 502
REGISTER_ADDR = 1  # Register Address for the main counter
REGISTER_COUNT = 1
TURN_ADDR = 7      # Register Address for the turn counter
CCW_ADDR = 18      # Register Address for rotation direction (0=CCW, 1=CW)

# --- Create Modbus Client ---
# It's better to connect inside the thread to handle connection errors gracefully.
client = ModbusTcpClient(MODBUS_HOST, port=MODBUS_PORT)

# --- GUI Class ---
class ModbusGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Rotary Ethernet/IP Encoder Visualizer")

        # Configure window size
        screen_width = root.winfo_screenwidth() * 2/3
        screen_height = root.winfo_screenheight() * 2/3
        self.canvas = tk.Canvas(root, width=screen_width, height=screen_height, bg="White")
        self.canvas.pack()

        self.center = (screen_width * 0.5, screen_height * 0.5)
        self.radius = screen_height * 0.4

        # --- Storage for Canvas Item IDs ---
        # This is the key to updating items instead of recreating them.
        self.tick_lines = {}
        self.tick_labels = {}
        self.arrow = None
        self.counter_label_id = None
        self.turn_label_id = None
        
        # --- Initial Drawing ---
        # Draw the main circular dial
        self.canvas.create_oval(
            self.center[0] - self.radius, self.center[1] - self.radius,
            self.center[0] + self.radius, self.center[1] + self.radius,
            width=20
        )
        
        # Draw the ticks and labels for the first time
        # We read the initial rotation direction once for efficiency.
        try:
            initial_rotation = client.read_holding_registers(CCW_ADDR, REGISTER_COUNT, unit=1).registers[0]
        except Exception:
            initial_rotation = 1 # Default to CW if device is not connected yet
            
        for angle in range(0, 360, 45):
            self.update_tick(angle, initial_rotation)

        # Initialize the arrow and text labels
        self.update_arrow(0, initial_rotation)
        self.counter_label_id = self.canvas.create_text(55, 25, text="Counter: --", font=("Arial", 16), anchor="w")
        self.turn_label_id = self.canvas.create_text(55, 55, text="Turns: --", font=("Arial", 16), anchor="w")
        
        # Start the background thread for Modbus communication
        self.running = True
        self.modbus_thread = Thread(target=self.update_loop, daemon=True)
        self.modbus_thread.start()

    def update_tick(self, angle_deg, rotation_mode):
        """
        Creates or updates a single compass tick and its label.
        This is the corrected and efficient way to draw.
        """
        # Determine the angle in radians based on rotation mode
        if rotation_mode == 1:  # Clockwise
            angle_rad = math.radians(angle_deg - 90)
        else:  # Counter-Clockwise
            angle_rad = math.radians(-angle_deg - 90)

        # Calculate coordinates for the line (tick mark)
        x1 = self.center[0] + self.radius * math.cos(angle_rad)
        y1 = self.center[1] + self.radius * math.sin(angle_rad)
        x2 = self.center[0] + (self.radius - 40) * math.cos(angle_rad)
        y2 = self.center[1] + (self.radius - 40) * math.sin(angle_rad)
        
        # Calculate coordinates for the label
        label_x = self.center[0] + (self.radius + 55) * math.cos(angle_rad)
        label_y = self.center[1] + (self.radius + 55) * math.sin(angle_rad)

        # --- Logic to Update or Create ---
        if angle_deg in self.tick_labels:
            # Item exists: update its coordinates
            self.canvas.coords(self.tick_lines[angle_deg], x1, y1, x2, y2)
            self.canvas.coords(self.tick_labels[angle_deg], label_x, label_y)
        else:
            # Item does not exist: create it and store its ID
            line_id = self.canvas.create_line(x1, y1, x2, y2, width=10)
            label_id = self.canvas.create_text(label_x, label_y, text=str(angle_deg), font=("Arial", 25))
            self.tick_lines[angle_deg] = line_id
            self.tick_labels[angle_deg] = label_id

    def update_arrow(self, modbus_value, rotation_mode):
        """Creates or updates the main arrow indicator."""
        # Calculate angle from 12-bit Modbus value (0-4095)
        angle_deg = (modbus_value % 4096) * 360 / 4096.0

        if rotation_mode == 1:  # Clockwise
            angle_rad = math.radians(angle_deg - 90)
        else:  # Counter-Clockwise
            angle_rad = math.radians(-angle_deg - 90)

        arrow_length = self.radius - 20
        x = self.center[0] + arrow_length * math.cos(angle_rad)
        y = self.center[1] + arrow_length * math.sin(angle_rad)

        if self.arrow:
            self.canvas.coords(self.arrow, self.center[0], self.center[1], x, y)
        else:
            self.arrow = self.canvas.create_line(
                self.center[0], self.center[1], x, y,
                arrow=tk.LAST, width=10, fill='red'
            )

    def update_text_labels(self, counter_val, turns_val):
        """Thread-safe method to update the text labels."""
        self.canvas.itemconfig(self.counter_label_id, text=f"Counter: {counter_val}")
        self.canvas.itemconfig(self.turn_label_id, text=f"Turns: {turns_val}")

    def update_loop(self):
        """Background thread to continuously read Modbus data."""
        rotation_prev = -1  # Initialize to a value that guarantees first-run update

        while self.running:
            try:
                # Ensure the client is connected
                if not client.is_socket_open():
                    print("Connecting to Modbus device...")
                    client.connect()
                
                # Read all required registers
                rotation_res = client.read_holding_registers(CCW_ADDR, REGISTER_COUNT, unit=1)
                counter_res = client.read_holding_registers(REGISTER_ADDR, REGISTER_COUNT, unit=1)
                turns_res = client.read_holding_registers(TURN_ADDR, REGISTER_COUNT, unit=1)
                
                # Check for errors
                if rotation_res.isError() or counter_res.isError() or turns_res.isError():
                    print("Modbus error during read.")
                    time.sleep(1) # Wait before retrying
                    continue

                # --- Process Data ---
                rotation = rotation_res.registers[0]
                value = counter_res.registers[0]
                turns = turns_res.registers[0]

                # Handle signed 16-bit integer for turns
                if turns > 32767:
                    turns -= 65536
                
                # --- Schedule GUI Updates (Thread-Safe) ---

                # If rotation direction has changed, redraw the compass ticks
                if rotation != rotation_prev:
                    print(f"Rotation changed to {'CW' if rotation == 1 else 'CCW'}")
                    for angle in self.tick_labels.keys():
                        # Use partial to pass arguments with 'after'
                        update_func = partial(self.update_tick, angle, rotation)
                        self.root.after(0, update_func)
                    rotation_prev = rotation
                
                # Schedule arrow and text updates
                self.root.after(0, self.update_arrow, value, rotation)
                self.root.after(0, self.update_text_labels, value, turns)

            except Exception as e:
                print(f"Modbus connection failed: {e}")
                if client.is_socket_open():
                    client.close()
                time.sleep(2) # Wait longer after a failure
            
            time.sleep(0.01)

    def close(self):
        """Cleanly close the application."""
        print("Closing application...")
        self.running = False
        self.modbus_thread.join(timeout=1) # Wait for the thread to finish
        if client.is_socket_open():
            client.close()
        self.root.destroy()

# --- Launch GUI ---
if __name__ == "__main__":
    root = tk.Tk()
    gui = ModbusGUI(root)
    # Ensure the close function is called when the window is closed
    root.protocol("WM_DELETE_WINDOW", gui.close)
    root.mainloop()
