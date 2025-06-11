# ModbusGUI

Simple GUI for a rotary Modbus Encoder

## Instructions for Using Application
Step 1: Run the Executable

First, try to run the EncoderVisualizer.exe file. You will likely see one of two pop-ups.

    If you see a "Windows protected your PC" pop-up (SmartScreen):
        Click on More info.
        Click the Run anyway button that appears.

    If Microsoft Defender deletes the file and shows a notification:
    Proceed to Step 2.

Step 2: Restore the File from Quarantine

    Open the Start Menu and type Windows Security, then open it.
    Click on Virus & threat protection.
    Under "Current threats," click on Protection history.
    You will see an entry for a "Threat quarantined." It will likely be categorized as severe. Click on it to expand.
    You will see the name of the threat and the affected file (...EncoderVisualizer.exe).
    In the bottom-right corner, click the Actions dropdown menu and select Allow on device or Restore.

This will restore the file and mark it as safe on your computer. You should now be able to run the executable.

Step 3: (Optional) Add a Permanent Exclusion

If you continue to have issues, you can tell Defender to ignore the application folder permanently.

    In Windows Security > Virus & threat protection, click on Manage settings.

Scroll down to Exclusions and click Add or remove exclusions.
Click + Add an exclusion, and choose Folder.
Navigate to and select the entire EncoderVisualizer folder that contains the .exe file.

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