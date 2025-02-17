import sys
import types

# ---- Mock RPi.GPIO ----
if "RPi" not in sys.modules:
    class MockGPIO:
        BOARD = "BOARD"
        BCM = "BCM"
        IN = "IN"
        OUT = "OUT"
        HIGH = "HIGH"
        LOW = "LOW"
        PUD_UP = "PUD_UP"
        PUD_DOWN = "PUD_DOWN"

        def __init__(self):
            self.pins = {}

        def setmode(self, mode):
            print(f"MockGPIO: setmode({mode})")

        def setup(self, pin, mode, pull_up_down=None):
            self.pins[pin] = mode
            print(f"MockGPIO: setup({pin}, {mode}, pull_up_down={pull_up_down})")

        def output(self, pin, state):
            if pin not in self.pins:
                raise RuntimeError(f"Pin {pin} not set up.")
            print(f"MockGPIO: output({pin}, {state})")

        def input(self, pin):
            if pin not in self.pins:
                raise RuntimeError(f"Pin {pin} not set up.")
            print(f"MockGPIO: input({pin})")
            return self.HIGH  # Always return HIGH

        def cleanup(self):
            print("MockGPIO: cleanup()")

        def setwarnings(self, flag):
            print(f"MockGPIO: setwarnings({flag})")

    mock_rpi = types.ModuleType("RPi")
    mock_rpi.GPIO = MockGPIO()
    sys.modules["RPi"] = mock_rpi
    sys.modules["RPi.GPIO"] = mock_rpi.GPIO

# ---- Mock board (Adafruit) ----
if "board" not in sys.modules:
    class MockBoard:
        D18 = "D18"
        D21 = "D21"
        SCL = "SCL"
        SDA = "SDA"

    sys.modules["board"] = MockBoard()

# ---- Mock neopixel (Adafruit) ----
if "neopixel" not in sys.modules:
    class MockNeoPixel:
        def __init__(self, pin, num_pixels, brightness=1.0, auto_write=True, pixel_order=None):
            self.pin = pin
            self.num_pixels = num_pixels
            self.brightness = brightness
            self.auto_write = auto_write
            self.pixels = [(0, 0, 0)] * num_pixels

            print(f"[Mock NeoPixel] Initialized on {pin} with {num_pixels} pixels")

        def show(self):
            print(f"[Mock NeoPixel] Showing pixels: {self.pixels}")

        def __setitem__(self, index, color):
            if 0 <= index < self.num_pixels:
                self.pixels[index] = color
                print(f"[Mock NeoPixel] Set pixel {index} to {color}")
            else:
                print(f"[Mock NeoPixel] Index {index} out of range")

        def __getitem__(self, index):
            return self.pixels[index]

        def fill(self, color):
            self.pixels = [color] * self.num_pixels
            print(f"[Mock NeoPixel] Filled all pixels with {color}")

    mock_neopixel = types.ModuleType("neopixel")
    mock_neopixel.NeoPixel = MockNeoPixel
    sys.modules["neopixel"] = mock_neopixel

