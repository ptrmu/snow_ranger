import pigpio
import time

# GPIO pin to monitor
GPIO_PIN = 18  # Change to the GPIO pin you want to monitor

# File to log transitions
LOG_FILE = "gpio_transitions.log"


# Callback function to capture GPIO transitions
def gpio_callback(gpio, level, tick):
    # Log the state change
    timestamp = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())
    transition_type = "Rising Edge" if level == 1 else "Falling Edge" if level == 0 else "Unknown"
    log_entry = f"{timestamp} - GPIO {gpio} - {transition_type} - Tick: {tick}\n"

    print(log_entry.strip())  # Print to console
    with open(LOG_FILE, "a") as file:
        file.write(log_entry)


def main():
    try:
        # Initialize pigpio and setup the GPIO pin
        pi = pigpio.pi()
        if not pi.connected:
            print("Error: Cannot connect to pigpio daemon. Is it running?")
            return

        # Set GPIO pin as input
        pi.set_mode(GPIO_PIN, pigpio.INPUT)

        # Register a callback function for GPIO transitions
        pi.callback(GPIO_PIN, pigpio.EITHER_EDGE, gpio_callback)

        print(f"Monitoring GPIO {GPIO_PIN} for transitions... Press Ctrl+C to stop.")

        # Keep the program running
        while True:
            time.sleep(1)

    except KeyboardInterrupt:
        print("\nProgram stopped by user.")

    finally:
        # Clean up resources
        pi.stop()
        print("Resources released. Exiting program.")


if __name__ == "__main__":
    main()
