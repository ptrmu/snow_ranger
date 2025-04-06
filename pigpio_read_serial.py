import pigpio
import time

# Configurable parameters
SERIAL_GPIO = 15  # GPIO pin to read serial data from (change as needed)
BAUD_RATE = 9600  # Baud rate for serial communication
DATA_BITS = 8  # Number of data bits per frame


def main():
    try:
        # Initialize pigpio
        pi = pigpio.pi()
        if not pi.connected:
            print("Error: Cannot connect to pigpio daemon. Is it running?")
            return

        # Enable bit-bang serial mode with inverted signal (invert=1)
        pi.bb_serial_read_open(SERIAL_GPIO, BAUD_RATE, DATA_BITS)  # Inverted mode flag
#        pi.bb_serial_invert(SERIAL_GPIO, 1)# Inverted mode flag
        print(f"Listening for non-inverted serial data on GPIO {SERIAL_GPIO} at {BAUD_RATE} baud...")

        while True:
            # Read serial data from the GPIO
            count, data = pi.bb_serial_read(SERIAL_GPIO)
            if count > 0:
                print(f"Received: {data.decode('utf-8', errors='replace')}")

            # Sleep for a short period to avoid excessive CPU usage
            time.sleep(0.1)

    except KeyboardInterrupt:
        print("\nProgram terminated by user.")

    finally:
        # Clean up and disable bit-bang serial mode
        pi.bb_serial_read_close(SERIAL_GPIO)
        pi.stop()
        print("Resources released. Exiting program.")


if __name__ == "__main__":
    main()
