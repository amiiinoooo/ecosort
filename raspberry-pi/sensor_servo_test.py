import RPi.GPIO as GPIO
import time
from adafruit_pca9685 import PCA9685
from board import SCL, SDA
import busio

# Cleanup before setting anything
GPIO.cleanup()

# Set GPIO mode to BCM
GPIO.setmode(GPIO.BCM)

# BCM Pin definitions
US_SENSOR_EC_PIN_METAL = 17     # GPIO17 (physical pin 11)
US_SENSOR_TR_PIN_METAL = 27     # GPIO27 (physical pin 13)
IR_SENSOR_PIN = 22              # GPIO22 (physical pin 15)
INDUCTIVE_SENSOR_PIN = 23       # GPIO23 (physical pin 16)

# Metal bin servo channel
METAL_MOTOR_CHANNEL = 0

# Trash bag reference height
TRASH_BAG_HEIGHT = 40  # cm

# GPIO Setup
GPIO.setup(US_SENSOR_EC_PIN_METAL, GPIO.IN)
GPIO.setup(US_SENSOR_TR_PIN_METAL, GPIO.OUT)
GPIO.setup(IR_SENSOR_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
GPIO.setup(INDUCTIVE_SENSOR_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
GPIO.output(US_SENSOR_TR_PIN_METAL, GPIO.LOW)
time.sleep(0.01)

# Setup I2C for PCA9685
i2c = busio.I2C(SCL, SDA)
pca = PCA9685(i2c)
pca.frequency = 50  # Standard servo frequency

# Function to move servo (mutual for all bins)
def open_bin(channel):
    pca.channels[channel].duty_cycle = 0x1999  # approx 90 degrees
    time.sleep(1)
    pca.channels[channel].duty_cycle = 0       # stop signal

# Function to read distance from ultrasonic sensor
def read_distance():
    GPIO.output(US_SENSOR_TR_PIN_METAL, GPIO.HIGH)
    time.sleep(0.00001)
    GPIO.output(US_SENSOR_TR_PIN_METAL, GPIO.LOW)

    start_time = time.time()
    start = None
    end = None

    # Wait for echo to go HIGH
    while GPIO.input(US_SENSOR_EC_PIN_METAL) == 0:
        if time.time() - start_time > 0.05:
            return -1
        start = time.time()

    # Wait for echo to go LOW
    while GPIO.input(US_SENSOR_EC_PIN_METAL) == 1:
        if time.time() - start_time > 0.1:
            return -1
        end = time.time()

    if start is None or end is None:
        return -1

    duration = end - start
    distance = (duration * 34300) / 2
    return round(distance, 2)

# Main loop
while True:
    try:
        st = input("Test? (press Enter to test again, anything else to quit): ").strip()
        if st != '':
            GPIO.cleanup()
            print("You exited the program!")
            break

        # IR Sensor check
        ir_val = GPIO.input(IR_SENSOR_PIN)
        print(f"IR Raw Output: {ir_val}")
        print("IR Sensor: Object detected!" if ir_val == 0 else "IR Sensor: No object detected.")

        # Inductive Sensor check
        inductive_val = GPIO.input(INDUCTIVE_SENSOR_PIN)
        print(f"Inductive Sensor Raw Output: {inductive_val}")
        print("Inductive Sensor: Metal detected!" if inductive_val == 0 else "Inductive Sensor: No metal detected.")

        # Ultrasonic sensor distance
        distance = read_distance()
        if distance == -1:
            print("[Metal Bag] Ultrasonic Error: Timeout\n")
        else:
            print(f"[Metal Bag] Distance: {distance:.1f} cm")
            if distance > TRASH_BAG_HEIGHT:
                print("[Metal Bag] Fill Level: 0% (Bag empty or sensor misaligned)\n")
            else:
                fullness = (1 - (distance / TRASH_BAG_HEIGHT)) * 100
                fullness = min(fullness, 100)
                if fullness > 75:
                    print(f"[Metal Bag] Fill Level: {fullness:.1f}% (Bag full or sensor blocked)\n")
                else:
                    print(f"[Metal Bag] Fill Level: {fullness:.1f}%\n")

        # Trigger servo
        servo_input = input("Trigger metal bin flap servo? (Y/N): ").strip().lower()
        if servo_input == 'y':
            print("Opening metal bin flap...")
            open_bin(METAL_MOTOR_CHANNEL)

    except KeyboardInterrupt:
        GPIO.cleanup()
        print("\nProgram interrupted and GPIO cleaned up.")
        break

    except Exception as e:
        print(f"Error: {e}")
