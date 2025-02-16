import json
import threading
import time
from datetime import datetime
from flask import Flask, render_template, request, jsonify
# import RPi.GPIO as GPIO
import neopixel
import board
import mock_gpio as GPIO

app = Flask(__name__)
SETTINGS_FILE = "settings.json"

# GPIOピン設定
OUTPUT1_PIN = 6
OUTPUT2_PIN = 13
OUTPUT3_PIN = 20
OUTPUT4_PIN = 26

# NeoPixelのピン設定
NEOPIXEL_PIN = board.D18

# 定数定義
DEFAULT_SETTINGS = {
    "start_time": "07:00",
    "end_time": "18:00",
    "interval_output2_on": 5,
    "interval_output3_on": 5,
    "interval_both_off": 2,
    "night_cycle_times": ["21:00", "00:00", "03:00"]
}

class Controller:
    def __init__(self):
        self.running = False
        self.thread = None
        self.exit_event = threading.Event()
        self.lock = threading.Lock()
        self.current_settings = None
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(OUTPUT1_PIN, GPIO.OUT)
        GPIO.setup(OUTPUT2_PIN, GPIO.OUT)
        GPIO.setup(OUTPUT3_PIN, GPIO.OUT)
        GPIO.setup(OUTPUT4_PIN, GPIO.OUT)
        self.stop_outputs()

    def start(self, settings):
        with self.lock:
            if self.running:
                self.stop()
            self.exit_event.clear()
            self.current_settings = settings
            self.running = True
            self.thread = threading.Thread(target=self.control_loop)
            self.thread.start()

    def stop(self):
        with self.lock:
            self.running = False
            self.exit_event.set()
            if self.thread and self.thread.is_alive():
                self.thread.join(timeout=3)
            self.stop_outputs()

    def stop_outputs(self):
        GPIO.output(OUTPUT1_PIN, GPIO.LOW)
        GPIO.output(OUTPUT2_PIN, GPIO.LOW)
        GPIO.output(OUTPUT3_PIN, GPIO.LOW)
        GPIO.output(OUTPUT4_PIN, GPIO.LOW)

    def parse_time(self, time_str):
        return datetime.strptime(time_str, "%H:%M").time()

    def control_loop(self):
        while self.running and not self.exit_event.is_set():
            try:
                now = datetime.now().time()
                settings = self.current_settings

                start_time = self.parse_time(settings["start_time"])
                end_time = self.parse_time(settings["end_time"])
                night_times = [self.parse_time(t) for t in settings["night_cycle_times"]]

                # メイン制御
                if (start_time <= now <= end_time) or (now in night_times):
                    update_led('green')
                    self.run_main_cycle(settings, start_time, end_time, night_times)
                else:
                    update_led('blue')
                    self.stop_outputs()

                # 中断可能なスリープ
                self.exit_event.wait(60)

            except Exception as e:
                print(f"Control loop error: {e}")
                break

            finally:
                update_led('none')

    def run_main_cycle(self, settings, start_time, end_time, night_times):
        GPIO.output(OUTPUT1_PIN, GPIO.HIGH)
        cycle_count = 0

        while self.running and not self.exit_event.is_set():
            now = datetime.now().time()
            if not ((start_time <= now <= end_time) or (now in night_times)):
                break

            # 出力2と3の交互制御（中断可能なスリープ）
            GPIO.output(OUTPUT2_PIN, GPIO.HIGH)
            if self.exit_event.wait(settings["interval_output2_on"] * 60):
                break
            
            GPIO.output(OUTPUT2_PIN, GPIO.LOW)
            if self.exit_event.wait(settings["interval_both_off"] * 60):
                break
            
            GPIO.output(OUTPUT3_PIN, GPIO.HIGH)
            GPIO.output(OUTPUT4_PIN, GPIO.HIGH)
            if self.exit_event.wait(settings["interval_output3_on"] * 60):
                break
            
            GPIO.output(OUTPUT3_PIN, GPIO.LOW)
            GPIO.output(OUTPUT4_PIN, GPIO.LOW)
            if self.exit_event.wait(settings["interval_both_off"] * 60):
                break

            # 夜間モードの場合は1サイクルのみ実行
            if now in night_times:
                cycle_count += 1
                if cycle_count >= 1:
                    break

# コントローラーの初期化
controller = Controller()

# 状態表示LED更新
def update_led(color):
#        logger.debug(f"called. color={color}")
        pixels = neopixel.NeoPixel(NEOPIXEL_PIN, 1)
        if color == 'blue':
                pixels[0] = (0, 0, 50)
        elif color == 'green' or color == 'success':
                pixels[0] = (50, 0, 0)
        elif color == 'yellow' or color == 'warning':
                pixels[0] = (32, 32, 0)
        elif color == 'red' or color == 'danger':
                pixels[0] = (0, 50, 0)
        elif color == 'cyan':
                pixels[0] = (32, 0, 32)
        elif color == 'magenta':
                pixels[0] = (0, 32, 32)
        elif color == 'white':
                pixels[0] = (20, 20, 20)
        else:
                pixels[0] = (0, 0, 0)
        return True

def load_settings():
    try:
        with open(SETTINGS_FILE, "r") as f:
            settings = json.load(f)
            settings.setdefault('night_cycle_times', [])
            return settings
    except FileNotFoundError:
        return DEFAULT_SETTINGS.copy()

def save_settings(new_settings):
    settings = DEFAULT_SETTINGS.copy()
    settings.update({
        "start_time": new_settings.get("start_time", DEFAULT_SETTINGS["start_time"]),
        "end_time": new_settings.get("end_time", DEFAULT_SETTINGS["end_time"]),
        "interval_output2_on": int(new_settings.get("interval_output2_on", DEFAULT_SETTINGS["interval_output2_on"])),
        "interval_output3_on": int(new_settings.get("interval_output3_on", DEFAULT_SETTINGS["interval_output3_on"])),
        "interval_both_off": int(new_settings.get("interval_both_off", DEFAULT_SETTINGS["interval_both_off"])),
        "night_cycle_times": [t for t in new_settings.get("night_cycle_times", []) if t][:3]
    })
    
    with open(SETTINGS_FILE, "w") as f:
        json.dump(settings, f, indent=4)
    
    controller.start(settings)

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/settings", methods=["GET", "POST"])
def settings_api():
    if request.method == "GET":
        return jsonify(load_settings())
    elif request.method == "POST":
        new_settings = request.json
        save_settings(new_settings)
        return jsonify({"status": "success"})

if __name__ == "__main__":
    try:
        initial_settings = load_settings()
        controller.start(initial_settings)
        app.run(host="0.0.0.0", port=5000)
    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        controller.stop()
        GPIO.cleanup()
        print("GPIO cleaned up")
