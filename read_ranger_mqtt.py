import argparse
import dataclasses as dc
import datetime as dt
import json  # To handle JSON encoding
import logging
import paho
import pigpio
import re


# Define a typed configuration object using @dataclass
@dc.dataclass
class Config:
    serial_gpio: str
    baud_rate: int
    data_bits: int
    pattern: str
    mqtt_broker: str
    mqtt_port: int
    mqtt_topic: str
    log_level: str


def get_config() -> Config:
    """
    Parse command-line arguments and return configuration as a typed Config object.
    """
    parser = argparse.ArgumentParser(
        description="MQTT and serial communication program",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        # Automatically includes default values in help messages
    )

    # Serial-related arguments (grouped)
    serial_group = parser.add_argument_group("Serial Communication Settings")
    serial_group.add_argument(
        "--serial-gpio", type=int, default=15, help="GPIO pin to connect to the serial device"
    )
    serial_group.add_argument(
        "--baud-rate", type=int, default=9600, help="Data transfer rate in bits per second (bps)"
    )
    serial_group.add_argument(
        "--data-bits",
        type=int,
        choices=[5, 6, 7, 8],
        default=8,
        help="Number of data bits per frame (5, 6, 7, or 8)",
    )
    serial_group.add_argument(
        "--pattern", type=str, default="^R(\\d{4})$", help="Pattern used for processing data"
    )

    # MQTT-related arguments (grouped)
    mqtt_group = parser.add_argument_group("MQTT Configuration")
    mqtt_group.add_argument(
        "--mqtt-broker",
        type=str,
        default="",
        help="MQTT Broker address",
    )
    mqtt_group.add_argument(
        "--mqtt-port", type=int, default=1883, help="MQTT Broker port (valid range: 1-65535)"
    )
    mqtt_group.add_argument(
        "--mqtt-topic",
        type=str,
        default="default_topic",
        help="MQTT topic to publish data to",
    )

    # Logging and verbosity
    parser.add_argument(
        "--log-level",
        type=str,
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="DEBUG",
        help="Set logging verbosity level",
    )

    # Parse the arguments
    args = parser.parse_args()

    # Custom validation for MQTT port
    if not (1 <= args.mqtt_port <= 65535):
        parser.error("MQTT port must be in the range 1-65535")

    # Return a Config object with parsed arguments
    return Config(
        serial_gpio=args.serial_gpio,
        baud_rate=args.baud_rate,
        data_bits=args.data_bits,
        pattern=args.pattern,
        mqtt_broker=args.mqtt_broker,
        mqtt_port=args.mqtt_port,
        mqtt_topic=args.mqtt_topic,
        log_level=args.log_level,
    )


def get_logger(log_level: str) -> logging.Logger:
    """
    Create and configure a logger object based on the provided log level.
    """
    logger = logging.getLogger("my_logger")
    logger.setLevel(log_level.upper())  # Set log level (e.g., DEBUG, INFO)

    # Add a console handler with formatting
    if not logger.handlers:  # Avoid adding duplicate handlers
        console_handler = logging.StreamHandler()
        console_handler.setLevel(log_level.upper())
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

    return logger


def display_config(config: Config, logger: logging.Logger):
    """
    Display the final configuration in a table format for transparency,
    but only if the logging level is DEBUG.
    """
    if logger.isEnabledFor(logging.DEBUG):
        config_dict = vars(config)
        config_summary = "\n".join([f"{key}: {value}" for key, value in config_dict.items()])
        logger.debug("\nConfiguration Summary:\n" + config_summary)


def read_from_ranger(config: Config, logger: logging.Logger):
    """
    Reads multiple bytes into a buffer until a '\r'.
    Checks if the buffer matches a predefined pattern.
    """
    pi = None  # Initialize pigpio instance variable
    try:
        # Initialize pigpio
        pi = pigpio.pi()
        if not pi.connected:
            raise RuntimeError("Cannot connect to pigpio daemon. Is it running?")

        # Enable bit-bang serial mode with inverted signal (invert=1)
        pi.bb_serial_read_open(config.serial_gpio, config.baud_rate, config.data_bits)
        pi.bb_serial_invert(config.serial_gpio, 1)  # Inverted mode flag

        buffer = b""  # Initialize empty buffer
        result = None  # Variable to store the result after a match

        while result is None:
            count, data = pi.bb_serial_read(config.serial_gpio)
            logger.debug(f"Read {count} bytes: {data}")

            if count > 0:
                buffer += data  # Append data to buffer

                # Check for carriage return '\r'
                if b'\r' in buffer:
                    # Decode buffer up to '\r' and reset it
                    line, _, buffer = buffer.partition(b'\r')
                    line = line.decode("utf-8", errors="replace").strip()

                    # Check if line matches the pattern
                    match = re.match(config.pattern, line)
                    if match:
                        logger.debug(f"Pattern matched: {line}")

                        # Extract data and timestamp
                        digits = match.group(1)  # Assuming pattern contains 1 capturing group
                        unix_time = int(dt.datetime.now(dt.timezone.utc).timestamp())

                        # Create the result dictionary
                        result = {
                            "timestamp": unix_time,
                            "data": digits,
                        }

        return result  # Return the valid data

    except Exception as e:
        # Include GPIO pin, baud rate, and data bits in error message
        logger.error(
            f"Error in read_from_ranger (GPIO: {config.serial_gpio}, Baud: {config.baud_rate}, Bits: {config.data_bits}): {e}"
        )
        raise  # Rethrow the exception to be handled by the caller

    finally:
        # Clean up pigpio interface
        if pi:
            try:
                pi.bb_serial_read_close(config.serial_gpio)
                pi.stop()
            except Exception as e:
                logger.error(f"Error during pigpio cleanup: {e}")
                raise  # Rethrow exceptions from cleanup if they occur


def send_to_mqtt(config: Config, payload_dict, logger: logging.Logger):
    """
    Publishes a given dictionary as a JSON payload to the MQTT topic.
    Opens a connection to the MQTT broker, sends the message, and closes the connection.

    Args:
        topic: The topic to publish to.
        payload_dict: A dictionary to be sent as the payload (will be serialized to JSON).
    """
    mqtt_client = paho.mqtt.client.Client()  # Create a new MQTT client instance
    try:
        # Connect to the MQTT broker
        mqtt_client.connect(config.mqtt_broker, config.mqtt_port, keepalive=60)

        # Convert the dictionary to a JSON string
        payload_json = json.dumps(payload_dict)

        # Publish to the MQTT topic
        mqtt_client.publish(config.mqtt_topic, payload_json)
        logger.info(
            f"Published data from GPIO {config.serial_gpio} to MQTT broker "
            f"{config.mqtt_broker}:{config.mqtt_port} on topic '{config.mqtt_topic}': {payload_json}"
        )

    except Exception as e:
        logger.error(
            f"Error publishing to MQTT broker '{config.mqtt_broker}:{config.mqtt_port}' "
            f"on topic '{config.mqtt_topic}': {e}"
        )
        raise  # Rethrow the exception so it can be handled by the caller

    finally:
        # Disconnect from the MQTT broker
        try:
            mqtt_client.disconnect()
            logger.info(f"Disconnected from MQTT broker '{config.mqtt_broker}:{config.mqtt_port}'.")
        except Exception as e:
            logger.error(
                f"Error during MQTT client cleanup for broker '{config.mqtt_broker}:{config.mqtt_port}': {e}"
            )
            raise  # Rethrow exceptions from cleanup if they occur


def main():
    config = get_config()
    logger = get_logger(config.log_level)
    display_config(config, logger)

    # Read data from the ranger once
    result = read_from_ranger(config, logger)

    if not config.mqtt_broker or not config.mqtt_port:
        logger.warning("MQTT server configuration is missing. Outputting data to stdout.")
        print(result)
    else:
        send_to_mqtt(config, result, logger)


if __name__ == "__main__":
    main()
