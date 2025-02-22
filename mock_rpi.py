import sys
import types

# ---- Mock RPi.GPIO ----
try:
    import RPi.GPIO as GPIO
except ImportError:
    # PWM のダミークラス
    class PWM:
        def __init__(self, pin, frequency):
            self.pin = pin
            self.frequency = frequency
            print(f"MockGPIO: PWM.__init__({pin}, {frequency})")
        def start(self, duty_cycle):
            print(f"MockGPIO: PWM.start({duty_cycle})")
        def ChangeDutyCycle(self, duty_cycle):
            print(f"MockGPIO: PWM.ChangeDutyCycle({duty_cycle})")
        def ChangeFrequency(self, frequency):
            print(f"MockGPIO: PWM.ChangeFrequency({frequency})")
        def stop(self):
            print("MockGPIO: PWM.stop()")
    
    class MockGPIO:
        BOARD = "BOARD"
        BCM = "BCM"
        IN = "IN"
        OUT = "OUT"
        HIGH = 1
        LOW = 0
        PUD_UP = "PUD_UP"
        PUD_DOWN = "PUD_DOWN"
        RISING = "RISING"
        FALLING = "FALLING"
        BOTH = "BOTH"
        PWM = PWM  # PWM クラスを属性として追加

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
            if state == self.HIGH:
                state_str = "HIGH"
            elif state == self.LOW:
                state_str = "LOW"
            else:
                state_str = str(state)
            print(f"MockGPIO: output({pin}, {state_str})")

        def input(self, pin):
            if pin not in self.pins:
                raise RuntimeError(f"Pin {pin} not set up.")
            print(f"MockGPIO: input({pin})")
            return self.HIGH  # 常に HIGH を返す

        def add_event_detect(self, channel, edge, callback=None, bouncetime=None):
            print(f"MockGPIO: add_event_detect({channel}, {edge}, callback={callback}, bouncetime={bouncetime})")

        def remove_event_detect(self, channel):
            print(f"MockGPIO: remove_event_detect({channel})")

        def event_detected(self, channel):
            print(f"MockGPIO: event_detected({channel})")
            return False

        def wait_for_edge(self, channel, edge, timeout=None):
            print(f"MockGPIO: wait_for_edge({channel}, {edge}, timeout={timeout})")
            return channel

        def cleanup(self):
            print("MockGPIO: cleanup()")

        def setwarnings(self, flag):
            print(f"MockGPIO: setwarnings({flag})")

    mock_rpi = types.ModuleType("RPi")
    mock_rpi.GPIO = MockGPIO()
    sys.modules["RPi"] = mock_rpi
    sys.modules["RPi.GPIO"] = mock_rpi.GPIO

# ---- Mock board (Adafruit) ----
try:
    import board
except ImportError:
    class MockBoard:
        D18 = "D18"
        D21 = "D21"
        SCL = "SCL"
        SDA = "SDA"
    sys.modules["board"] = MockBoard()

# ---- Mock neopixel (Adafruit) ----
try:
    import neopixel
except ImportError:
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
            print(f"[Mock Neo Pixel] Filled all pixels with {color}")

    mock_neopixel = types.ModuleType("neopixel")
    mock_neopixel.NeoPixel = MockNeoPixel
    sys.modules["neopixel"] = mock_neopixel
