import pigpio
import time
import re
import json  # To handle JSON encoding
from datetime import datetime
import paho.mqtt.client as mqtt  # MQTT library

# Configurable parameters
SERIAL_GPIO = 15  # GPIO pin to read serial data from (change as needed)
BAUD_RATE = 9600  # Baud rate for serial communication
DATA_BITS = 8  # Number of data bits per frame
PATTERN = r"^R(\d{4})$"  # Regex pattern to match Rxxxx where x is a digit
MQTT_BROKER = "mqtt.example.com"  # Replace with your MQTT broker address
MQTT_PORT = 1883  # Default MQTT port
MQTT_TOPIC = "sensor/data"  # Topic to publish the data


def read_from_ranger():
    """
    Opens the pigpio interface, reads a valid packet (Rxxxx format),
    and cleans up before returning the result.

    Returns:
        dict: A dictionary containing "timestamp" and "data" fields.

    Raises:
        Exception: Rethrows any exceptions that occur during operation.
    """
    pi = None  # Initialize pigpio instance variable
    try:
        # Initialize pigpio
        pi = pigpio.pi()
        if not pi.connected:
            raise RuntimeError("Cannot connect to pigpio daemon. Is it running?")

        # Enable bit-bang serial mode with inverted signal (invert=1)
        pi.bb_serial_read_open(SERIAL_GPIO, BAUD_RATE, DATA_BITS)
        pi.bb_serial_invert(SERIAL_GPIO, 1)  # Inverted mode flag

        result = None  # Initialize result

        # Loop until valid data is found
        while result is None:
            # Read serial data from the GPIO
            count, data = pi.bb_serial_read(SERIAL_GPIO)
            if count > 0:
                # Decode the received data and strip trailing spaces/newlines
                line = data.decode('utf-8', errors='replace').strip()

                # Check if the line matches the "Rxxxx" pattern
                match = re.match(PATTERN, line)
                if match:
                    # Extract the 4 digits
                    digits = match.group(1)

                    # Get the current Unix timestamp in UTC
                    unix_time = int(datetime.utcnow().timestamp())

                    # Create valid result as a dictionary
                    result = {
                        "timestamp": unix_time,
                        "data": digits
                    }

            # Sleep for a short period to avoid excessive CPU usage
            if result is None:
                time.sleep(0.1)

        return result  # Return the valid data

    except Exception as e:
        # Include GPIO pin, baud rate, and data bits in error message
        print(
            f"Error in read_from_ranger (GPIO: {SERIAL_GPIO}, Baud: {BAUD_RATE}, Bits: {DATA_BITS}): {e}"
        )
        raise  # Rethrow the exception to be handled by the caller

    finally:
        # Clean up pigpio interface
        if pi:
            try:
                pi.bb_serial_read_close(SERIAL_GPIO)
                pi.stop()
            except Exception as e:
                print(f"Error during pigpio cleanup: {e}")
                raise  # Rethrow exceptions from cleanup if they occur


def send_to_mqtt(topic, payload_dict):
    """
    Publishes a given dictionary as a JSON payload to the MQTT topic.
    Opens a connection to the MQTT broker, sends the message, and closes the connection.

    Args:
        topic: The topic to publish to.
        payload_dict: A dictionary to be sent as the payload (will be serialized to JSON).
    """
    mqtt_client = mqtt.Client()  # Create a new MQTT client instance
    try:
        # Connect to the MQTT broker
        mqtt_client.connect(MQTT_BROKER, MQTT_PORT, keepalive=60)

        # Convert the dictionary to a JSON string
        payload_json = json.dumps(payload_dict)

        # Publish to the MQTT topic
        mqtt_client.publish(topic, payload_json)
        print(
            f"Published data from GPIO {SERIAL_GPIO} to MQTT broker {MQTT_BROKER}:{MQTT_PORT} on topic '{topic}': {payload_json}"
        )

    except Exception as e:
        print(
            f"Error publishing to MQTT broker '{MQTT_BROKER}:{MQTT_PORT}' on topic '{topic}': {e}"
        )

    finally:
        # Disconnect from the MQTT broker
        try:
            mqtt_client.disconnect()
        except Exception as e:
            print(
                f"Error during MQTT client cleanup for broker '{MQTT_BROKER}:{MQTT_PORT}' on topic '{topic}': {e}"
            )


def main():
    # Read data from the ranger once
    result = read_from_ranger()

    # Send the data to MQTT (routine expects a dictionary)
    send_to_mqtt(MQTT_TOPIC, result)


if __name__ == "__main__":
    main()
