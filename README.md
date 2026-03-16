# Instructions:
1. Clone the repository
    a. After cloning, navigate the the cloned repository in the command line
2. Set up the hardware
    a. Put the Adafruit Ultimate GPS + Logging Shield with an SD card onto an Arduino UNO
    b. Connect the positive node of the TMP36 sensor into +5V, the negative node into GND, and the middle node into A0
    c. Connect the GPS SMA antenna into the SMA cable port on the Adafruit Ultimate GPS + Logging Shield
    d. Connect the Arduino UNO into the computer to program
        i. After the Arduino UNO is programmed, a standard power source can be used instead of a computer
        ii. If using a computer serial terminal to view the data, use the 115200 Baud rate
3. Program the Arduino board with the .ino file located in the `arduino_logger_code` directory
    a. Make sure to install version `1.1.3` of the `Adafruit GPS` Arduino library
4. Collect data
    a. After data collection, move all .txt files from the SD card into the `data` directory
5. Create a virtual python environment and install requirements
    a. Run the line `python -m venv *environment_name*` in the command line
        i. Activate the evironment by running `source *environment_name*/bin/activate`
    b. Run the line `pip install -r requirements.txt`
6. Either run the .py script or go through the .ipynb notebook
    a. To run the script run the line `python parser.py` in the command line
    b. The loaded data is saved to a parquet file called `data.parquet` for future use
        i. A script to use those has not been added to the repo yet (as of 15-03-2026)
7. Explore outputted images
    a. The 3D images that pop up when running can be interacted with the mouse
        i. In order to view the next image, close the current one (only 1 image displayed at a time)
    b. The images are saved as .png files to the repo directory