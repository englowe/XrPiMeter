import time

from led import LEDs, GREEN, Color
DIM_GREEN = Color(0,255,0)


leds = LEDs()

print("Starting slow LED test...")


try:

    while True:

        leds.strip.set_all_pixels(DIM_GREEN)
        leds.strip.show()

        print("Frame sent")

        time.sleep(2)


except KeyboardInterrupt:

    print()
    print("Stopping...")


finally:

    leds.shutdown()