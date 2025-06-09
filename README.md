# ModbusGUI

Simple GUI for a rotary Modbus Encoder

## Functions

### draw_tick
Draws the ticks around the circle every degree you give it. Simple if statement in the beginning changes the circle depending on if you are recording clockwise or counterclockwise movement. We track the direction of movement using register CCW_ADDR defined in the beginning of the file. 

### update_arrow
Updates the arrow around the spinner using the value passed into it and converting it to radians.

### update_loop
Updates the arrow and both the counter and turn counter. 