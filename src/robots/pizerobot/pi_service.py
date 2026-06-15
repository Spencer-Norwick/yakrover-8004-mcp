"""Tiny Pi-side camera/status service for pizerobot.

Run directly on the Raspberry Pi:
    python3 src/robots/pizerobot/pi_service.py
"""

from __future__ import annotations

import base64
import json
import os
import shutil
import socket
import subprocess
import time
from datetime import datetime, UTC
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


HOST = os.getenv("PIZEROBOT_SERVICE_HOST", "0.0.0.0")
PORT = int(os.getenv("PIZEROBOT_SERVICE_PORT", "8081"))
CAPTURE_DIR = Path(
    os.getenv("PIZEROBOT_CAPTURE_DIR", str(Path.home() / "pizerobot-data" / "captures"))
)
CAPTURE_DIR.mkdir(parents=True, exist_ok=True)


def _now() -> str:
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")


def _read_cpu_temp_c() -> float | None:
    path = Path("/sys/class/thermal/thermal_zone0/temp")
    if not path.exists():
        return None
    try:
        return round(int(path.read_text().strip()) / 1000, 2)
    except Exception:
        return None


def _get_primary_ip() -> str | None:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("8.8.8.8", 80))
        return sock.getsockname()[0]
    except Exception:
        return None
    finally:
        sock.close()


def _memory_info() -> dict:
    total = available = None
    try:
        values = {}
        for line in Path("/proc/meminfo").read_text().splitlines():
            key, value = line.split(":", 1)
            values[key.strip()] = value.strip()
        total = values.get("MemTotal")
        available = values.get("MemAvailable")
    except Exception:
        pass
    return {"mem_total": total, "mem_available": available}


def _disk_info() -> dict:
    usage = shutil.disk_usage(Path.home())
    return {
        "disk_total_bytes": usage.total,
        "disk_used_bytes": usage.used,
        "disk_free_bytes": usage.free,
    }


def _uptime_seconds() -> float | None:
    try:
        return round(float(Path("/proc/uptime").read_text().split()[0]), 2)
    except Exception:
        return None


def _detect_camera_command() -> str | None:
    explicit = os.getenv("PIZEROBOT_CAMERA_CMD")
    if explicit:
        return explicit
    for cmd in ("rpicam-still", "libcamera-still"):
        if shutil.which(cmd):
            return cmd
    return None


def _camera_available() -> dict:
    cmd = _detect_camera_command()
    if not cmd:
        return {"available": False, "error": "No camera capture command found.", "camera_command": None}

    probe = subprocess.run(
        [cmd, "--list-cameras"],
        capture_output=True,
        text=True,
        timeout=15,
    )
    stdout = (probe.stdout or "").strip()
    stderr = (probe.stderr or "").strip()
    available = (
        probe.returncode == 0
        and bool(stdout)
        and "No cameras available!" not in stdout
    )
    return {
        "available": available,
        "camera_command": cmd,
        "stdout": stdout,
        "stderr": stderr,
    }


def _capture_image(width: int, height: int, timeout_ms: int, include_base64: bool) -> dict:
    cmd = _detect_camera_command()
    if not cmd:
        raise RuntimeError("No camera capture command found. Install rpicam-still or libcamera-still.")

    filename = f"capture-{_now()}.jpg"
    output_path = CAPTURE_DIR / filename

    capture_cmd = [
        cmd,
        "-n",
        "--width",
        str(width),
        "--height",
        str(height),
        "--timeout",
        str(timeout_ms),
        "-o",
        str(output_path),
    ]
    proc = subprocess.run(capture_cmd, capture_output=True, text=True, timeout=max(20, timeout_ms / 1000 + 10))
    if proc.returncode != 0:
        raise RuntimeError((proc.stderr or proc.stdout or "Camera capture failed.").strip())

    image_bytes = output_path.read_bytes()
    result = {
        "status": "ok",
        "camera_command": cmd,
        "filename": filename,
        "capture_path": str(output_path),
        "width": width,
        "height": height,
        "timeout_ms": timeout_ms,
        "size_bytes": len(image_bytes),
        "captured_at": _now(),
    }
    if include_base64:
        result["image_base64"] = base64.b64encode(image_bytes).decode("ascii")
        result["mime_type"] = "image/jpeg"
    return result


def _sweep_servo(
    gpio_pin: int,
    positions: list[float],
    delay_seconds: float,
    min_pulse_width: float,
    max_pulse_width: float,
) -> dict:
    try:
        from gpiozero import Servo
    except ImportError as exc:
        raise RuntimeError("gpiozero is not installed on the Pi.") from exc

    servo = Servo(
        gpio_pin,
        min_pulse_width=min_pulse_width,
        max_pulse_width=max_pulse_width,
    )
    try:
        for position in positions:
            servo.value = position
            time.sleep(delay_seconds)
    finally:
        servo.detach()

    return {
        "status": "ok",
        "gpio_pin": gpio_pin,
        "positions": positions,
        "delay_seconds": delay_seconds,
        "min_pulse_width": min_pulse_width,
        "max_pulse_width": max_pulse_width,
        "completed_at": _now(),
    }


def _service_info() -> dict:
    return {
        "service": "pizerobot-pi-service",
        "hostname": socket.gethostname(),
        "ip_address": _get_primary_ip(),
        "cpu_temperature_c": _read_cpu_temp_c(),
        "camera_command": _detect_camera_command(),
    }


def _system_status() -> dict:
    return {
        **_service_info(),
        "uptime_seconds": _uptime_seconds(),
        "load_average": tuple(round(v, 2) for v in os.getloadavg()),
        **_memory_info(),
        **_disk_info(),
    }


class Handler(BaseHTTPRequestHandler):
    server_version = "pizerobot-pi-service/0.1"

    def do_GET(self):
        if self.path == "/info":
            return self._json(200, _service_info())
        if self.path == "/system/status":
            return self._json(200, _system_status())
        if self.path == "/system/temp":
            return self._json(200, {"cpu_temperature_c": _read_cpu_temp_c()})
        if self.path == "/camera/available":
            return self._json(200, _camera_available())
        return self._json(404, {"error": "Not found"})

    def do_POST(self):
        try:
            payload = self._read_json()
            if self.path == "/camera/capture":
                result = _capture_image(
                    width=max(64, min(3280, int(payload.get("width", 640)))),
                    height=max(64, min(2464, int(payload.get("height", 480)))),
                    timeout_ms=max(1, min(10000, int(payload.get("timeout_ms", 1500)))),
                    include_base64=bool(payload.get("include_base64", False)),
                )
            elif self.path == "/servo/sweep":
                raw_positions = payload.get("positions", [0, -0.5, 0, 0.5, 0, -0.5, 0])
                if not isinstance(raw_positions, list):
                    raise ValueError("positions must be a list of values from -1.0 to 1.0")
                positions = [max(-1.0, min(1.0, float(value))) for value in raw_positions[:20]]
                result = _sweep_servo(
                    gpio_pin=max(0, min(27, int(payload.get("gpio_pin", 18)))),
                    positions=positions,
                    delay_seconds=max(0.05, min(2.0, float(payload.get("delay_seconds", 0.7)))),
                    min_pulse_width=max(
                        0.0003,
                        min(0.0015, float(payload.get("min_pulse_width", 0.0006))),
                    ),
                    max_pulse_width=max(
                        0.0015,
                        min(0.0030, float(payload.get("max_pulse_width", 0.0024))),
                    ),
                )
            else:
                return self._json(404, {"error": "Not found"})
            return self._json(200, result)
        except Exception as exc:
            return self._json(500, {"error": str(exc)})

    def log_message(self, fmt, *args):
        return

    def _read_json(self) -> dict:
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0:
            return {}
        raw = self.rfile.read(length)
        return json.loads(raw.decode("utf-8"))

    def _json(self, status: int, payload: dict):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


if __name__ == "__main__":
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"Serving pizerobot Pi service on http://{HOST}:{PORT}")
    server.serve_forever()
