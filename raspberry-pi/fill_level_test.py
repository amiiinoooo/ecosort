import RPi.GPIO as GPIO
import time

# Set GPIO mode to BOARD (physical pin numbering)
GPIO.setmode(GPIO.BOARD)

# Define pin numbers
US_SENSOR_EC_PIN = 11  # Ultrasonic Echo
US_SENSOR_TR_PIN = 13  # Ultrasonic Trigger
IR_SENSOR_PIN = 16     # IR Sensor (NPN logic)

# Trash bag height reference (tuned for sensitivity)
TRASH_BAG_HEIGHT = 40  # cm

# Setup GPIO directions
GPIO.setup(US_SENSOR_EC_PIN, GPIO.IN)
GPIO.setup(US_SENSOR_TR_PIN, GPIO.OUT)
GPIO.setup(IR_SENSOR_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)

# Set Trigger LOW initially
GPIO.output(US_SENSOR_TR_PIN, GPIO.LOW)
time.sleep(0.01)

# Read distance from HC-SR04
def read_distance():
    GPIO.output(US_SENSOR_TR_PIN, GPIO.HIGH)
    time.sleep(0.00001)
    GPIO.output(US_SENSOR_TR_PIN, GPIO.LOW)

    start_timeout = time.time()
    while GPIO.input(US_SENSOR_EC_PIN) == 0:
        start = time.time()
        if start - start_timeout > 0.05:
            return -1

    end_timeout = time.time()
    while GPIO.input(US_SENSOR_EC_PIN) == 1:
        end = time.time()
        if end - end_timeout > 0.05:
            return -1

    duration = end - start
    distance = (duration * 34300) / 2
    return round(distance, 2)

# Main loop
while True:
    try:
        st = input("Test? (Y to run, anything else to quit): ").strip().lower()
        if st == 'y':
            # IR Sensor
            ir_val = GPIO.input(IR_SENSOR_PIN)
            print(f"IR Raw Output: {ir_val}")
            if ir_val == 0:
                print("IR Sensor: Object detected!")
            else:
                print("IR Sensor: No object detected.")

            # Ultrasonic Distance & Fill Level
            distance = read_distance()
            if distance == -1:
                print("Ultrasonic Error: Timeout\n")
            else:
                print(f"Distance: {distance:.1f} cm")

                if distance > TRASH_BAG_HEIGHT:
                    print("Fill Level: 0% (Bag empty or sensor misaligned)\n")
                else:
                    fullness = (1 - (distance / TRASH_BAG_HEIGHT)) * 100
                    if fullness > 100:
                        fullness = 100
                    if fullness > 75:
                        print(f"Fill Level: {fullness:.1f}% (Bag full or sensor blocked)\n")
                    else:
                        print(f"Fill Level: {fullness:.1f}%\n")

        else:
            GPIO.cleanup()
            print("You exited the program!")
            break

    except KeyboardInterrupt:
        GPIO.cleanup()
        print("\nProgram interrupted and GPIO cleaned up.")
        break

    except Exception as e:
        print(f"Error: {e}")
