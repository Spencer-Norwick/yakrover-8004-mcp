import asyncio
import base64
import os
from pathlib import Path

import requests


class PiZeroRobotClient:
    """HTTP client for the tiny Pi-side camera/status service."""

    def __init__(self):
        self.base_url = os.getenv("PIZEROBOT_URL", "http://127.0.0.1:8081")
        self.timeout = float(os.getenv("PIZEROBOT_TIMEOUT_SECS", "10"))
        self.capture_cache_dir = Path(
            os.getenv("PIZEROBOT_CAPTURE_CACHE_DIR", "/tmp/pizerobot-captures")
        )
        self.capture_cache_dir.mkdir(parents=True, exist_ok=True)
        self.session = requests.Session()

    async def is_online(self) -> dict:
        try:
            info = await self._get_json("/info")
            return {"online": True, **info}
        except Exception as exc:
            return {"online": False, "base_url": self.base_url, "error": str(exc)}

    async def get_system_status(self) -> dict:
        return await self._get_json("/system/status")

    async def get_cpu_temperature(self) -> dict:
        return await self._get_json("/system/temp")

    async def camera_is_available(self) -> dict:
        return await self._get_json("/camera/available")

    async def capture_image(
        self,
        width: int = 640,
        height: int = 480,
        timeout_ms: int = 1500,
        include_base64: bool = False,
    ) -> dict:
        payload = {
            "width": max(64, min(3280, int(width))),
            "height": max(64, min(2464, int(height))),
            "timeout_ms": max(1, min(10000, int(timeout_ms))),
            "include_base64": bool(include_base64),
        }
        result = await self._post_json("/camera/capture", payload)

        image_b64 = result.get("image_base64")
        if image_b64:
            local_path = self.capture_cache_dir / result.get("filename", "capture.jpg")
            local_path.write_bytes(base64.b64decode(image_b64))
            result["local_cache_path"] = str(local_path)

        return result

    async def servo_sweep(
        self,
        gpio_pin: int = 18,
        positions: list[float] | None = None,
        delay_seconds: float = 0.7,
    ) -> dict:
        payload = {
            "gpio_pin": max(0, min(27, int(gpio_pin))),
            "positions": positions or [0, -0.5, 0, 0.5, 0, -0.5, 0],
            "delay_seconds": max(0.05, min(2.0, float(delay_seconds))),
        }
        return await self._post_json("/servo/sweep", payload)

    async def dual_servo_sweep(
        self,
        gpio_pin_a: int = 18,
        gpio_pin_b: int = 13,
        duration_seconds: float = 5.0,
        steps: int = 51,
    ) -> dict:
        payload = {
            "gpio_pin_a": max(0, min(27, int(gpio_pin_a))),
            "gpio_pin_b": max(0, min(27, int(gpio_pin_b))),
            "duration_seconds": max(0.5, min(30.0, float(duration_seconds))),
            "steps": max(2, min(200, int(steps))),
        }
        return await self._post_json("/servo/dual-sweep", payload)

    async def _get_json(self, path: str) -> dict:
        return await asyncio.to_thread(self._sync_get_json, path)

    async def _post_json(self, path: str, payload: dict) -> dict:
        return await asyncio.to_thread(self._sync_post_json, path, payload)

    def _sync_get_json(self, path: str) -> dict:
        resp = self.session.get(f"{self.base_url}{path}", timeout=self.timeout)
        resp.raise_for_status()
        return resp.json()

    def _sync_post_json(self, path: str, payload: dict) -> dict:
        resp = self.session.post(f"{self.base_url}{path}", json=payload, timeout=max(self.timeout, 30))
        resp.raise_for_status()
        return resp.json()
