import serial
import time


def read_serial_data():
    # Replace `/dev/ttyS0` with the correct serial port on your Raspberry Pi
    # `/dev/ttyS0` is for the Raspberry Pi using the GPIO UART pins
    # If it's a USB-to-serial adapter, it might be something like `/dev/ttyUSB0`.
    port = '/dev/ttyS0'

    try:
        # Open the serial connection
        ser = serial.Serial(port,
                            baudrate=9600,  # Baud rate
                            bytesize=serial.EIGHTBITS,  # Data bits: 8
                            parity=serial.PARITY_NONE,  # Parity: None
                            stopbits=serial.STOPBITS_ONE,  # Stop bits: 1
                            timeout=1)
        print(f"Connected to {port}")

        # Allow time to establish connection
        time.sleep(2)

        while True:
            # Read data from the serial port
            if ser.in_waiting > 0:  # Only proceed if there's data waiting in the buffer
                data = ser.read(ser.in_waiting)
                print(f"Received: {data}")

    except serial.SerialException as e:
        print(f"Error: {e}")

    except KeyboardInterrupt:
        print("Exiting program.")

    finally:
        ser.close()  # Close the serial port connection
        print("Serial connection closed.")


if __name__ == "__main__":
    read_serial_data()
