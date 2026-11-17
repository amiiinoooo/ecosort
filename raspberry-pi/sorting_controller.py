import RPi.GPIO as GPIO
import time
from hx711 import HX711  # Weight sensor module

# --- GPIO Setup ---
GPIO.setwarnings(False)
GPIO.setmode(GPIO.BCM)  # Use Broadcom pin-numbering scheme

# Pin Definitions
IR_SENSOR_PIN = 22               # IR sensor to detect object presence
INDUCTIVE_SENSOR_PIN = 26        # Inductive sensor for metal detection
METAL_ECHO_PIN = 17              # Metal bin ultrasonic echo pin
METAL_TRIG_PIN = 27              # Metal bin ultrasonic trigger pin
ORGANIC_TRIG = 19                # Organic bin ultrasonic trigger pin
ORGANIC_ECHO = 13                # Organic bin ultrasonic echo pin
PAPER_TRIG = 20                  # Paper bin ultrasonic trigger pin
PAPER_ECHO = 12                  # Paper bin ultrasonic echo pin
REFLECTANCE_PINS = [23, 24, 25]  # Reflectance sensor pins for paper/organic detection

# HX711 Pins (Weight Sensor)
HX711_DT = 5
HX711_SCK = 6

# Servo Motor GPIO pins
SERVO_PINS = {
    "METAL": 18,
    "PAPER": 15,
    "ORGANIC": 7,
    "HANDLE": 8
}

TRASH_BAG_HEIGHT = 40  # Height of trash bin in cm (for fill level calculation)

# --- Sensor GPIO Setup ---
GPIO.setup(IR_SENSOR_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
GPIO.setup(INDUCTIVE_SENSOR_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)

# Setup ultrasonic sensors
for trig, echo in [(METAL_TRIG_PIN, METAL_ECHO_PIN), (ORGANIC_TRIG, ORGANIC_ECHO), (PAPER_TRIG, PAPER_ECHO)]:
    GPIO.setup(trig, GPIO.OUT)
    GPIO.setup(echo, GPIO.IN)
    GPIO.output(trig, GPIO.LOW)

# Setup reflectance sensors
for pin in REFLECTANCE_PINS:
    GPIO.setup(pin, GPIO.OUT)
    GPIO.output(pin, GPIO.LOW)

# Setup Servo Motors (PWM at 50Hz)
servo_pwms = {}
for label, pin in SERVO_PINS.items():
    GPIO.setup(pin, GPIO.OUT)
    pwm = GPIO.PWM(pin, 50)
    pwm.start(0)
    servo_pwms[label] = pwm

# Initialize HX711 Weight Sensor
hx = HX711(dout_pin=HX711_DT, pd_sck_pin=HX711_SCK)
hx.reset()

# --- Functions ---

# Set servo angle (0° to 180°)
def set_angle(pwm, angle):
    duty = 2.5 + (angle / 180.0) * 10  # Convert angle to duty cycle
    pwm.ChangeDutyCycle(duty)
    print(f"Setting angle: {angle}° → Duty Cycle: {duty:.1f}%")
    time.sleep(0.5)
    pwm.ChangeDutyCycle(0)  # Stop signal to avoid buzzing

# Generic ultrasonic distance measurement
def read_distance_custom(trig, echo):
    GPIO.output(trig, True)
    time.sleep(0.00001)
    GPIO.output(trig, False)

    start_time = time.time()
    while GPIO.input(echo) == 0:
        if time.time() - start_time > 0.05:
            return -1
        start = time.time()

    while GPIO.input(echo) == 1:
        if time.time() - start_time > 0.1:
            return -1
        end = time.time()

    duration = end - start
    return round((duration * 34300) / 2, 2)  # cm

# Metal bin ultrasonic
def read_distance():
    return read_distance_custom(METAL_TRIG_PIN, METAL_ECHO_PIN)

# Reflectance sensor reading (for paper/organic)
def read_reflectance(pin):
    GPIO.setup(pin, GPIO.OUT)
    GPIO.output(pin, True)
    time.sleep(0.00001)
    GPIO.output(pin, False)
    GPIO.setup(pin, GPIO.IN)

    start = time.time()
    while GPIO.input(pin) == 0:
        if time.time() - start > 0.01:
            break
    return time.time() - start

# Identify material using sensors
def get_material_type():
    if GPIO.input(INDUCTIVE_SENSOR_PIN) == 0:
        return "METAL"
    
    reflectance = [read_reflectance(pin) for pin in REFLECTANCE_PINS]
    avg = sum(reflectance) / len(reflectance)

    if avg < 0.002:
        return "PAPER"
    else:
        return "ORGANIC"

# Print trash bin fill level using ultrasonic
def print_fill_level(bin_name, distance):
    if distance != -1:
        print(f"[{bin_name} Bin] Distance: {distance:.1f} cm")
        fullness = max(0, min((1 - distance / TRASH_BAG_HEIGHT) * 100, 100))
        print(f"[{bin_name} Bin] Bag fullness: {fullness:.1f}%\n")
    else:
        print(f"[{bin_name} Bin] Ultrasonic Error: Timeout\n")

# Move appropriate servo motor when material is detected
def activate_servo(material):
    pin_label = material.upper()
    if pin_label in servo_pwms:
        print(f"{material} detected → Activating servo on GPIO {SERVO_PINS[pin_label]}")
        pwm = servo_pwms[pin_label]
        set_angle(pwm, 90)  # Open
        time.sleep(1)
        set_angle(pwm, 0)   # Close

# --- Main Loop ---
try:
    while True:
        # Show current fill levels of all bins
        print_fill_level("Metal", read_distance())
        print_fill_level("Organic", read_distance_custom(ORGANIC_TRIG, ORGANIC_ECHO))
        print_fill_level("Paper", read_distance_custom(PAPER_TRIG, PAPER_ECHO))

        # If object detected by IR sensor
        if GPIO.input(IR_SENSOR_PIN) == 0:
            print("IR Sensor: Object detected!")

            # Detect material type
            material = get_material_type()
            print(f"Detected Material: {material}")

            # Read and print raw weight
            weight = hx.get_raw_data()
            print(f"Raw Weight Reading: {weight}\n")

            # Activate appropriate servo motor
            activate_servo(material)

        else:
            print("IR Sensor: No object detected.")

        time.sleep(1)

# Cleanup when exiting
except KeyboardInterrupt:
    for pwm in servo_pwms.values():
        pwm.stop()
    GPIO.cleanup()
    print("Program interrupted and GPIO cleaned up.")

except Exception as e:
    for pwm in servo_pwms.values():
        pwm.stop()
    GPIO.cleanup()
    print(f"Error: {e}")
