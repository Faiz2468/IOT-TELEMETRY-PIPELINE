"""
IoT Cloud Telemetry Pipeline — Device Simulator
Simulates multiple edge nodes streaming sensor readings to Supabase.
"""

import time
import random
import signal
import argparse
import requests
import os
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# ── Configuration ────────────────────────────────────────────────────────────

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("Missing SUPABASE_URL or SUPABASE_KEY in .env file")

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=minimal",
}

# Simulated devices — each has its own baseline temp/humidity range
DEVICES = {
    "EDGE-NODE-01": {"temp_range": (22.0, 32.0), "humidity_range": (50.0, 75.0), "location": "Server Room A"},
    "EDGE-NODE-02": {"temp_range": (18.0, 28.0), "humidity_range": (40.0, 65.0), "location": "Server Room B"},
    "EDGE-NODE-03": {"temp_range": (25.0, 38.0), "humidity_range": (55.0, 85.0), "location": "Rooftop Unit"},
}

# Anomaly injection probability (5% chance per reading)
ANOMALY_PROBABILITY = 0.05

# ── Helpers ───────────────────────────────────────────────────────────────────

running = True

def handle_shutdown(sig, frame):
    global running
    print("\n⏹  Shutdown signal received. Stopping pipeline gracefully...")
    running = False

signal.signal(signal.SIGINT, handle_shutdown)
signal.signal(signal.SIGTERM, handle_shutdown)


def derive_status(temperature: float, humidity: float) -> str:
    if temperature > 36.0:
        return "CRITICAL_TEMP"
    if temperature > 33.0:
        return "WARN_TEMP"
    if humidity > 80.0:
        return "WARN_HUMIDITY"
    if humidity < 30.0:
        return "WARN_DRY"
    return "OK"


def generate_telemetry(device_id: str) -> dict:
    cfg = DEVICES[device_id]
    if random.random() < ANOMALY_PROBABILITY:
        temperature = round(random.uniform(37.0, 42.0), 2)
        humidity = round(random.uniform(85.0, 95.0), 2)
    else:
        t_lo, t_hi = cfg["temp_range"]
        h_lo, h_hi = cfg["humidity_range"]
        temperature = round(random.uniform(t_lo, t_hi), 2)
        humidity = round(random.uniform(h_lo, h_hi), 2)
    return {
        "device_id": device_id,
        "temperature": temperature,
        "humidity": humidity,
        "status_code": derive_status(temperature, humidity),
    }


def push_reading(payload: dict) -> bool:
    try:
        response = requests.post(SUPABASE_URL, headers=HEADERS, json=payload, timeout=10)
        return response.status_code in (200, 201)
    except requests.exceptions.RequestException:
        return False


def timestamp() -> str:
    return datetime.now().strftime("%H:%M:%S")


# ── Main loop ─────────────────────────────────────────────────────────────────

def run(interval: int = 5):
    print("=" * 60)
    print("  IoT Cloud Telemetry Pipeline  —  Device Simulator")
    print("=" * 60)
    print(f"  Devices   : {', '.join(DEVICES.keys())}")
    print(f"  Interval  : {interval}s per cycle")
    print(f"  Endpoint  : {SUPABASE_URL}")
    print("  Press Ctrl+C to stop.\n")

    cycle = 0
    success_total = 0
    failure_total = 0

    while running:
        cycle += 1
        print(f"[{timestamp()}] ── Cycle #{cycle} ─────────────────────────")

        for device_id in DEVICES:
            payload = generate_telemetry(device_id)
            ok = push_reading(payload)

            if ok:
                success_total += 1
                icon = "✅" if payload["status_code"] == "OK" else "⚠️ "
                print(
                    f"  {icon} {device_id:<16} "
                    f"T={payload['temperature']:>5}°C  "
                    f"H={payload['humidity']:>5}%  "
                    f"[{payload['status_code']}]"
                )
            else:
                failure_total += 1
                print(f"  ❌ {device_id:<16} — push failed")

        print(f"  Stats: {success_total} sent / {failure_total} failed  (sleeping {interval}s)\n")
        time.sleep(interval)

    print(f"\n Pipeline stopped. Total sent: {success_total}, failed: {failure_total}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="IoT Telemetry Simulator")
    parser.add_argument("--interval", type=int, default=5)
    args = parser.parse_args()
    run(interval=args.interval)