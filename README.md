# ModbusGUI

Simple GUI for a rotary Modbus Encoder

## Functions

### init
Stores colors for each object
Stores fonts for each text object
Stores logo to be displayed (image)
Sets up UI and compass

### setup_ui
Creates main frame for the application and configures the frame
Places the image (logo) in the upper left of the frame
Places the labels for connection and data readouts as well as toggle button 

### draw_initial_compass
Creates oval for the initial compass
Updates tick marks around the compass

### update_tick
Depending on rotation direction, creates the ticks for around the compass

### update_connection_status
Updates the connection status depending on connection status

### update_gui_labels
Updates the text labels such as the data readouts

### toggle_direction
Reads current direction based on the Modbus register and when button is pressed, toggles the direction and changes the value in the Modbus register

### update_arrow
Updates the arrow around the spinner using the value passed into it and converting it to radians.

### update_loop
Updates the arrow and both the counter and turn counter. 