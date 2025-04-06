import pigpio
import time
import re
from datetime import datetime  # Import datetime module for accurate timestamps

# Configurable parameters
SERIAL_GPIO = 15  # GPIO pin to read serial data from (change as needed)
BAUD_RATE = 9600  # Baud rate for serial communication
DATA_BITS = 8  # Number of data bits per frame
PATTERN = r"^R(\d{4})$"  # Regex pattern to match Rxxxx where x is a digit


def main():
    try:
        # Initialize pigpio
        pi = pigpio.pi()
        if not pi.connected:
            print("Error: Cannot connect to pigpio daemon. Is it running?")
            return

        # Enable bit-bang serial mode with inverted signal (invert=1)
        pi.bb_serial_read_open(SERIAL_GPIO, BAUD_RATE, DATA_BITS)
#        pi.bb_serial_invert(SERIAL_GPIO, 1)  # Inverted mode flag

        while True:
            # Read serial data from the GPIO
            count, data = pi.bb_serial_read(SERIAL_GPIO)
            if count > 0:
                # Decode the received data and strip any newlines or leading/trailing spaces
                line = data.decode('utf-8', errors='replace').strip()

                # Check if the line matches the "Rxxxx" pattern
                match = re.match(PATTERN, line)
                if match:
                    # Extract the 4 digits
                    digits = match.group(1)

                    # Get the current Unix timestamp using datetime
                    unix_time = int(datetime.now().timestamp())

                    # Print the timestamp and digits in the required format
                    print(f"{unix_time},{digits}")
                    break  # Exit the loop once a match is found

            # Sleep for a short period to avoid excessive CPU usage
            time.sleep(0.1)

    except KeyboardInterrupt:
        print("Error: Program terminated by user.")
    except Exception as e:
        print(f"Error: {e}")

    finally:
        # Clean up and disable bit-bang serial mode
        try:
            pi.bb_serial_read_close(SERIAL_GPIO)
            pi.stop()
        except Exception as e:
            print(f"Error: {e}")


if __name__ == "__main__":
    main()
