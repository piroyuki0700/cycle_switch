import json
import sys
import threading
import time
from datetime import datetime, timedelta
from flask import Flask, render_template, request, jsonify
import mock_rpi
import RPi.GPIO as GPIO
import neopixel
import board
import adafruit_dht
import smbus
import logging
import socket

RETRY_COUNT = 5
SETTINGS_FILE = "settings.json"
LOG_FILE = "cycle_switch.log"
LOG_TO_FILE = True  # Trueならファイル出力、Falseならコンソール出力

# GPIOピン設定
OUTPUT1_PIN = 6
OUTPUT2_PIN = 19
OUTPUT3_PIN = 20
OUTPUT4_PIN = 26

# 水位センサーのピン
WATER_LEVEL_PIN = 15

# NeoPixelのピン設定
NEOPIXEL_PIN = board.D18

# DHT11センサーの設定
dht_device = adafruit_dht.DHT11(board.D5, use_pulseio=False)  # GPIO5を使用

# 温度センサーのデバイスファイル
DS18B20_DEVICE = "/sys/bus/w1/devices/28-01204c43b99b/w1_slave"

# PCF8591 の I2C アドレス（通常は 0x48）
I2C_ADDR = 0x48
bus = smbus.SMBus(1)
# 定数設定
VREF = 3.3      # ADC基準電圧
EC_FACTOR = 1.0 # EC補正係数（キャリブレーションが必要）

# 定数定義（control_enabledを追加）
DEFAULT_SETTINGS = {
    "start_time": "07:00",
    "end_time": "18:00",
    "interval_output2_on": 3,
    "interval_output3_on": 3,
    "interval_both_off": 3,
    "night_cycle_times": ["21:00", "00:00", "03:00"],
    "control_enabled": True
}

# グローバル変数
logger = None

# ログ設定
def setup_logger():
    global logger
    logger = logging.getLogger("SeedboxControl")  # ルートロガーを取得
    logger.setLevel(logging.INFO)    # ログレベルを設定
    # ハンドラー設定
    if LOG_TO_FILE:
        handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
    else:
        handler = logging.StreamHandler(sys.stdout)
    # フォーマット設定
    formatter = logging.Formatter(
        "%(asctime)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    handler.setFormatter(formatter)
    # ハンドラーをロガーに追加
    logger.addHandler(handler)

class Controller:
    def __init__(self):
        self.running = False
        self.thread = None
        self.exit_event = threading.Event()
        self.lock = threading.RLock()
        self.current_settings = None
        self.control_enabled = False  # 全体制御ON/OFF状態
        self.operation_state = "stopped"  # "running", "waiting", "stopped"
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(OUTPUT1_PIN, GPIO.OUT)
        GPIO.setup(OUTPUT2_PIN, GPIO.OUT)
        GPIO.setup(OUTPUT3_PIN, GPIO.OUT)
        GPIO.setup(OUTPUT4_PIN, GPIO.OUT)
        self.stop_outputs()

        # 水位センサーの設定（リスナー登録）
        GPIO.setup(WATER_LEVEL_PIN, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)

    def start(self, settings):
        with self.lock:
            if self.running:
                self.stop()
            self.exit_event.clear()
            self.current_settings = settings
            self.running = True
            self.control_enabled = True
            self.operation_state = "waiting"  # 開始直後は待機状態
            self.thread = threading.Thread(target=self.control_loop)
            self.thread.start()
            logger.info("Controller started with settings: %s", settings)

    def stop(self):
        with self.lock:
            if self.running:
                logger.info("Controller stopping.")
            self.running = False
            self.control_enabled = False
            self.operation_state = "stopped"
            self.exit_event.set()
            if self.thread and self.thread.is_alive():
                self.thread.join(timeout=3)
            self.stop_outputs()
            update_led("none")
            logger.info("Controller stopped.")

    def stop_outputs(self):
        GPIO.output(OUTPUT1_PIN, GPIO.LOW)
        GPIO.output(OUTPUT2_PIN, GPIO.LOW)
        GPIO.output(OUTPUT3_PIN, GPIO.LOW)
        GPIO.output(OUTPUT4_PIN, GPIO.LOW)

    def parse_time(self, time_str):
        return datetime.strptime(time_str, "%H:%M").time()

    def control_loop(self):
        settings = self.current_settings

        start_time = self.parse_time(settings["start_time"])
        end_time = self.parse_time(settings["end_time"])
        night_times = [self.parse_time(t) for t in settings["night_cycle_times"]]

        while self.running and not self.exit_event.is_set():
            try:
                now = datetime.now().time().replace(second=0, microsecond=0)

                # 制御対象の時間帯の場合
                if (start_time <= now <= end_time) or (now in night_times):
                    self.operation_state = "running"
                    update_led('green')  # 動作中：緑
                    logger.info("Main cycle started at %s", datetime.now().strftime("%H:%M:%S"))
                    self.run_main_cycle(settings, start_time, end_time, night_times)
                    logger.info("Main cycle ended at %s", datetime.now().strftime("%H:%M:%S"))
                    # ルーチン終了後、まだ動作可能なら待機状態へ
                    if self.running:
                        self.operation_state = "waiting"
                        update_led('blue')   # 待機中：青
                else:
                    self.stop_outputs()

                now = datetime.now()
                # 次の分の0秒までの秒数を計算
                next_minute = now.replace(second=0, microsecond=0) + timedelta(minutes=1)
                wait_seconds = (next_minute - now).total_seconds()

                # 最大1分の待機（早期解除可能）
                self.exit_event.wait(wait_seconds)

            except Exception as e:
                logger.error("Control loop error: %s", e)
                break

    def run_main_cycle(self, settings, start_time, end_time, night_times):
        GPIO.output(OUTPUT1_PIN, GPIO.HIGH)

        while self.running and not self.exit_event.is_set():
            now = datetime.now().time().replace(second=0, microsecond=0)
            if not ((start_time <= now <= end_time) or (now in night_times)):
                break

            # 出力2と3の交互制御
            GPIO.output(OUTPUT2_PIN, GPIO.HIGH)
            if self.exit_event.wait(settings["interval_output2_on"] * 60):
                break
            GPIO.output(OUTPUT2_PIN, GPIO.LOW)
    
            GPIO.output(OUTPUT3_PIN, GPIO.HIGH)
            GPIO.output(OUTPUT4_PIN, GPIO.HIGH)
            if self.exit_event.wait(settings["interval_output3_on"] * 60):
                break
            GPIO.output(OUTPUT3_PIN, GPIO.LOW)
            GPIO.output(OUTPUT4_PIN, GPIO.LOW)

            # 夜間モードの場合は1サイクルのみ実行
            if now in night_times:
                break

            if self.exit_event.wait(settings["interval_both_off"] * 60):
                break

        GPIO.output(OUTPUT1_PIN, GPIO.LOW)

# コントローラーの初期化
controller = Controller()

# 状態表示LED更新
def update_led(color):
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
            settings.setdefault('control_enabled', True)
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
        "night_cycle_times": [t for t in new_settings.get("night_cycle_times", []) if t][:3],
        "control_enabled": new_settings.get("control_enabled", True)
    })
    
    with open(SETTINGS_FILE, "w") as f:
        json.dump(settings, f, indent=4)
    logger.info("Settings saved: %s", settings)
    
    if settings.get("control_enabled", True):
        controller.start(settings)
    else:
        controller.stop()

# DS18B20から温度を読み取る関数
def read_temperature():
    try:
        with open(DS18B20_DEVICE, 'r') as f:
            lines = f.readlines()
        # 最初の行に"YES"があれば読み取り成功
        if lines[0].strip()[-3:] != "YES":
            return None
        equals_pos = lines[1].find("t=")
        if equals_pos != -1:
            temp_string = lines[1][equals_pos+2:]
            temperature = float(temp_string) / 1000.0
            return temperature
    except Exception as e:
        logger.info("温度センサー読み取りエラー: " + str(e))
        return None

def read_adc(channel=0):
    """
    PCF8591の指定チャンネルからアナログ値を取得（0-255の値を返す）
    PCF8591は最初の読み出しが不正確な場合があるため、ダミーリードを行います。
    """
    bus.write_byte(I2C_ADDR, channel)
    bus.read_byte(I2C_ADDR)  # ダミーリード
    value = bus.read_byte(I2C_ADDR)
    return value

def get_ec(temperature=25):
    """
    AIN0チャンネルからTDSセンサー（EC測定用）の値を取得し、
    温度補正を加えたEC値（電気伝導率）を計算して返します。
    """
    raw_value = read_adc(channel=0)  # AIN0から値を取得
    voltage = (raw_value / 255.0) * VREF  # 電圧に変換
    # 簡易的なEC計算（温度補正付き）
    ec_value = (voltage / VREF) * EC_FACTOR * (1.0 + 0.02 * (temperature - 25))
    # return round(ec_value, 3), round(voltage, 3)
    return ec_value # round(ec_value, 3)

def get_brightness():
    """
    PCF8591モジュール内蔵の照度センサー（AIN1チャンネル接続）の値を取得します。

    生のADC値および電圧から、仮の換算式（電圧×100）で照度(lux)を計算します。
    ※実際の換算はセンサーや回路の特性に合わせたキャリブレーションが必要です。
    """
    raw_value = read_adc(channel=1)  # 内蔵照度センサーはAIN1チャンネルに接続
    voltage = (raw_value / 255.0) * VREF
    lux = voltage * 100  # 仮の換算式（例：1V=100lux）
    # return raw_value, round(voltage, 3), round(lux, 3)
    return raw_value

# サーバーのローカルIPアドレスを取得
def get_local_ip():
    try:
        # 外部に接続せずにローカルIPを取得
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))  # Google DNSを利用 (実際に接続しない)
            return s.getsockname()[0]  # IPアドレスを取得
    except Exception as e:
        print(f"IPアドレス取得エラー: {e}")
        return "127.0.0.1"

# Flaskアプリケーション設定
app = Flask(__name__)

# ルート：HTML画面の表示
@app.route('/')
def index():
    ip_address = get_local_ip()  # サーバーのIPアドレス取得
    return render_template('index.html', server_ip=ip_address)

@app.route("/api/settings", methods=["GET", "POST"])
def settings_api():
    if request.method == "GET":
        return jsonify(load_settings())
    elif request.method == "POST":
        new_settings = request.json
        save_settings(new_settings)
        return jsonify({"status": "success"})

@app.route("/api/status", methods=["GET"])
def status_api():
    water_level = "low" if GPIO.input(WATER_LEVEL_PIN) == GPIO.HIGH else "normal"

    for i in range(RETRY_COUNT):
        try:
            temperature = dht_device.temperature
            humidity = dht_device.humidity
            break
        except RuntimeError:
            pass

    water_temp = read_temperature()
    ec_value = get_ec(water_temp)
    brightness = get_brightness()

    status = {
        "operation": controller.operation_state,  # ここでフラグを返す
        "water_level": water_level,
        "humidity": humidity,
        "temperature": temperature,
        "water_temp": water_temp,
        "ec_value": ec_value,
        "brightness": brightness,
        "control_enabled": controller.control_enabled
    }
    return jsonify(status)

if __name__ == "__main__":
    setup_logger()
    try:
        if len(sys.argv) > 1 and sys.argv[1] == 'on':
            initial_settings = load_settings()
            if initial_settings.get("control_enabled", True):
                controller.start(initial_settings)
            else:
                controller.stop()
            logger.info("Application started. Running Flask app on port 5000.")
            app.run(host="0.0.0.0", port=5000)
    except KeyboardInterrupt:
        logger.info("KeyboardInterrupt received. Shutting down...")
    finally:
        update_led("none")
        controller.stop()
        GPIO.cleanup()
        logger.info("GPIO cleaned up")
