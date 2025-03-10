import argparse
import dataclasses as dc
import datetime as dt
import json  # To handle JSON encoding
import logging
import paho.mqtt.client as mqtt
import pathlib as pl
import pigpio
import re
import serial
import time


# Define a typed configuration object using @dataclass
@dc.dataclass
class Config:
    serial_gpio: str
    serial_port: str
    baud_rate: int
    data_bits: int
    pattern: str
    mqtt_broker: str
    mqtt_port: int
    mqtt_topic: str
    mqtt_user: str
    mqtt_password: str
    log_level: str
    source_type: int
    source_desc: str
    sink_desc: str


def get_config() -> Config:
    parser = argparse.ArgumentParser(
        description="MQTT and serial communication program",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)

    # Serial-related arguments (grouped)
    serial_group = parser.add_argument_group("Serial Communication Settings")
    serial_group.add_argument("--serial-gpio",
                              type=int,
                              default=-1,
                              help="GPIO pin connected to the serial device")
    serial_group.add_argument("--serial-port",
                              type=str,
                              default="",
                              help="Serial port connected to the serial device")
    serial_group.add_argument("--baud-rate",
                              type=int,
                              default=9600,
                              help="Data transfer rate in bits per second (bps)")
    serial_group.add_argument("--data-bits",
                              type=int,
                              choices=[5, 6, 7, 8],
                              default=8,
                              help="Number of data bits per frame (5, 6, 7, or 8)")
    serial_group.add_argument("--pattern",
                              type=str,
                              default="^R(\\d{4})$",
                              help="Pattern used for processing data")

    # MQTT-related arguments (grouped)
    mqtt_group = parser.add_argument_group("MQTT Configuration")
    mqtt_group.add_argument("--mqtt-broker",
                            type=str,
                            default="192.168.1.39",
                            help="MQTT Broker address")
    mqtt_group.add_argument("--mqtt-port",
                            type=int,
                            default=1883,
                            help="MQTT Broker port (valid range: 1-65535)")
    mqtt_group.add_argument("--mqtt-topic",
                            type=str,
                            default="snowdata/921a_18",
                            help="MQTT topic to publish data to")
    mqtt_group.add_argument('--mqtt-user',
                            help="Username for MQTT broker authentication",
                            required=False)
    mqtt_group.add_argument('--mqtt-password',
                            help="Password for MQTT broker authentication",
                            required=False)

    # Logging and verbosity
    parser.add_argument("--log-level",
                        type=str,
                        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
                        default="INFO",
                        help="Set logging verbosity level")

    # Parse the arguments
    args = parser.parse_args()

    source_type = 0
    source_desc = "unspecified"
    if args.serial_gpio != -1:
        source_type = 1
        source_desc = f"GPIO {args.serial_gpio}"

    elif args.serial_port != "":
        source_type = 2
        source_desc = f"serial port {args.serial_port}"

    sink_desc = f"MQTT broker {args.mqtt_broker}:{args.mqtt_port} " + \
                    f"on topic '{args.mqtt_topic}'"

    # Return a Config object with parsed arguments
    return Config(
        serial_gpio=args.serial_gpio,
        serial_port=args.serial_port,
        baud_rate=args.baud_rate,
        data_bits=args.data_bits,
        pattern=args.pattern,
        mqtt_broker=args.mqtt_broker,
        mqtt_port=args.mqtt_port,
        mqtt_topic=args.mqtt_topic,
        mqtt_user=args.mqtt_user,
        mqtt_password=args.mqtt_password,
        log_level=args.log_level,
        source_type=source_type,
        source_desc=source_desc,
        sink_desc=sink_desc,
    )


def get_logger(log_level: str) -> logging.Logger:
    logger = logging.getLogger(pl.Path(__file__).stem)
    logger.setLevel(log_level.upper())  # Set log level (e.g., DEBUG, INFO)

    # Add a console handler with formatting
    if not logger.handlers:  # Avoid adding duplicate handlers
        console_handler = logging.StreamHandler()
        console_handler.setLevel(log_level.upper())
        formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                                      datefmt="%Y-%m-%d %H:%M:%S")
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

    return logger


def display_config(config: Config, logger: logging.Logger):
    if logger.isEnabledFor(logging.DEBUG):
        config_dict = vars(config)
        config_summary = "\n".join([f"{key}: {value}" for key, value in config_dict.items()])
        logger.debug("\nConfiguration Summary:\n" + config_summary)


def read_from_ranger_uart(config: Config, logger: logging.Logger) -> dict | None:
    if config.data_bits == 5:
        bytesize = serial.FIVEBITS
    elif config.data_bits == 6:
        bytesize = serial.SIXBITS
    elif config.data_bits == 7:
        bytesize = serial.SEVENBITS
    elif config.data_bits == 8:
        bytesize = serial.EIGHTBITS
    else:
        logger.error(f"Invalid data bits: {config.data_bits}")
        raise ValueError(f"Unsupported data bit value: {config.data_bits}")

    try:
        # Open the serial connection
        ser = serial.Serial(config.serial_port,
                            baudrate=config.baud_rate,  # Baud rate
                            bytesize=bytesize,  # Data bits: 8
                            parity=serial.PARITY_NONE,  # Parity: None
                            stopbits=serial.STOPBITS_ONE,  # Stop bits: 1
                            timeout=1)

    except serial.SerialException as e:
        logger.error(f"Error opening {config.source_desc}: {e}")
        raise

    buffer = b""  # Initialize empty buffer
    match = None
    unix_time = None

    # Define a timeout mechanism to prevent indefinite looping
    start_time = time.time()
    timeout = 20  # seconds

    time.sleep(1)

    try:
        ser.read(ser.in_waiting) # flush buffer
        while time.time() - start_time < timeout:
            if ser.in_waiting > 0:  # Proceed only if data is available
                data = ser.read(ser.in_waiting)
                unix_time = int(dt.datetime.now(dt.timezone.utc).timestamp())
                logger.debug(f"Read {len(data)} bytes: {data}")

                buffer += data  # Append data to the buffer

                # Check if buffer contains desired delimiter
                if b'\r' in buffer:
                    line, _, buffer = buffer.partition(b'\r')  # Partition buffer
                    line = line.decode("utf-8", errors="replace").strip()
                    logger.debug(f"Decoded line: {line}")

                    # Match the pattern
                    match = re.match(config.pattern, line)
                    if match:
                        break
            time.sleep(0.1)

        else:
            logger.error(f"Serial reading timed out from {config.source_desc}")
            raise

    finally:
        ser.close()

    if match and match.groups():
        return {
            "timestamp": unix_time,
            "ranger_distance": match.group(1),
        }
    else:
        logger.error(f"Unexpected data format or regex match failed from {config.source_desc}.")
        raise


def read_from_ranger_gpio(config: Config, logger: logging.Logger) -> dict | None:
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
        unix_time = 0

        while True:
            count, data = pi.bb_serial_read(config.serial_gpio)
            unix_time = int(dt.datetime.now(dt.timezone.utc).timestamp())
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
                        return {
                            "timestamp": unix_time,
                            "ranger_distance": match.group(1),
                        }

    except Exception as e:
        logger.error(f"Error in read_from_ranger from {config.source_desc}: {e}")
        raise

    finally:
        # Clean up pigpio interface
        if pi:
            try:
                pi.bb_serial_read_close(config.serial_gpio)
                pi.stop()
            except Exception as e:
                logger.error(f"Error during pigpio cleanup: {e}")
                raise


def read_from_ranger(config: Config, logger: logging.Logger) -> dict | None:
    if config.serial_gpio != -1:
        return read_from_ranger_gpio(config, logger)

    if config.serial_port != "":
        return read_from_ranger_uart(config, logger)

    logger.error(f"Error in read_from_ranger: Must specify - GPIO (--serial_gpio 18) or "
                 "Port (--serial_port /dev/ttyS0) {config.serial_gpio}")
    raise


def send_to_mqtt(config: Config, payload_dict, logger: logging.Logger):
    mqtt_client = mqtt.Client()  # Create a new MQTT client instance
    try:
        if config.mqtt_user and config.mqtt_password:
            mqtt_client.username_pw_set(config.mqtt_user, config.mqtt_password)

        # Connect to the MQTT broker
        mqtt_client.connect(config.mqtt_broker, config.mqtt_port, keepalive=60)

        # Convert the dictionary to a JSON string
        payload_json = json.dumps(payload_dict)

        # Publish to the MQTT topic
        mqtt_client.publish(config.mqtt_topic, payload_json)
        logger.info(f"Published data from {config.source_desc} "
                    f"to {config.sink_desc}': {payload_json}")

    except Exception as e:
        logger.error(f"Error publishing to {config.sink_desc}: {e}")
        raise

    finally:
        # Disconnect from the MQTT broker
        try:
            mqtt_client.disconnect()
            logger.debug(f"Disconnected from {config.sink_desc}.")
        except Exception as e:
            logger.error(f"Error during cleanup for {config.sink_desc}: {e}")
            raise


def main():
    config = get_config()
    logger = get_logger(config.log_level)
    display_config(config, logger)

    # Read data from the ranger once
    result = read_from_ranger(config, logger)

    if result and config.mqtt_broker and config.mqtt_port:
        send_to_mqtt(config, result, logger)
    else:
        logger.info(f"No MQTT broker setup for data from {config.source_desc }: {result}")


if __name__ == "__main__":
    main()
