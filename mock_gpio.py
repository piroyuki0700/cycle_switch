# mock_gpio.py

class MockGPIO:
    def __init__(self):
        self.setup_calls = []
        self.output_calls = []
        self.input_calls = []
        self.mode = None

        # 定数を定義
        self.BCM = "BCM"
        self.OUT = "OUT"
        self.IN = "IN"
        self.HIGH = "HIGH"
        self.LOW = "LOW"

    def setmode(self, mode):
        self.mode = mode
        print(f"MockGPIO: setmode({mode})")

    def setup(self, channel, direction):
        self.setup_calls.append((channel, direction))
        print(f"MockGPIO: setup({channel}, {direction})")

    def output(self, channel, value):
        self.output_calls.append((channel, value))
        print(f"MockGPIO: output({channel}, {value})")

    def input(self, channel):
        self.input_calls.append(channel)
        print(f"MockGPIO: input({channel})")
        return 0  # デフォルトで0を返す

    def cleanup(self):
        print("MockGPIO: cleanup()")

# モジュールにGPIOインスタンスを直接注入
import sys
sys.modules[__name__] = MockGPIO()

