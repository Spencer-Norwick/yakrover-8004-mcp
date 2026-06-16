import time

from core.marketplace_tools import MARKETPLACE_TOOL_NAMES
from core.plugin import BiddingTerms, RobotPlugin, RobotMetadata


class PiZeroRobotPlugin(RobotPlugin):
    def metadata(self) -> RobotMetadata:
        return RobotMetadata(
            name="PiZero-Robot-01",
            description="A Raspberry Pi Zero W robot exposing camera, system telemetry, and servo control over MCP.",
            robot_type="embedded_controller",  # Provisional until the physical robot form factor is defined.
            url_prefix="pizerobot",
            fleet_provider="yakrover",
            fleet_domain="yakrover.com/dev",
            bidding_terms=BiddingTerms(
                min_price_cents=75,
                rate_per_minute_cents=15,
                currency="usd",
                accepted_task_types=["camera"],
                max_duration_secs=120,
                max_concurrent_tasks=1,
                requires_approval=True,
            ),
        )

    def tool_names(self) -> list[str]:
        return [
            "pizerobot_is_online",
            "pizerobot_get_system_status",
            "pizerobot_get_cpu_temperature",
            "pizerobot_camera_is_available",
            "pizerobot_capture_image",
            "pizerobot_servo_sweep",
            "pizerobot_dual_servo_sweep",
            *MARKETPLACE_TOOL_NAMES,
        ]

    def register_tools(self, mcp):
        from .client import PiZeroRobotClient
        from .tools import register

        self.client = PiZeroRobotClient()
        register(mcp, self.client)

    async def bid(self, task_spec: dict) -> dict | None:
        """Generate a bid for visual inspection tasks after liveness and camera checks."""
        if task_spec.get("task_category") not in ("visual_inspection", "camera"):
            return None

        terms = self.metadata().bidding_terms
        min_price = terms.min_price_cents / 100
        if task_spec.get("budget_ceiling", 0) < min_price:
            return None

        client = getattr(self, "client", None)
        if client is None:
            from .client import PiZeroRobotClient
            client = PiZeroRobotClient()

        online = await client.is_online()
        if not online.get("online"):
            return None

        camera = await client.camera_is_available()
        if not camera.get("available"):
            return None

        reqs = task_spec.get("capability_requirements") or {}
        required_modalities = set(reqs.get("modalities_required", []))
        if required_modalities and not required_modalities.issubset({"still_image", "visible_light"}):
            return None

        return {
            "price": min_price,
            "currency": "usd",
            "sla_commitment_seconds": min(task_spec.get("sla_seconds", 60), terms.max_duration_secs),
            "confidence": 0.9,
            "capabilities_offered": ["still_image", "visible_light", "fixed_view"],
            "notes": "Pi Zero W with OV5647 camera module; returns a single still image and capture metadata.",
        }

    async def execute(self, task_id: str, task_description: str, parameters: dict) -> dict:
        """Capture a still image and return it as visual inspection delivery data."""
        client = getattr(self, "client", None)
        if client is None:
            from .client import PiZeroRobotClient
            client = PiZeroRobotClient()

        start = time.monotonic()
        partial_data: dict = {}

        try:
            camera = await client.camera_is_available()
            partial_data["camera_status"] = camera
            if not camera.get("available"):
                return {
                    "success": False,
                    "error": "Camera is not available for capture.",
                    "partial_data": partial_data,
                }

            width = int(parameters.get("width", 1280))
            height = int(parameters.get("height", 720))
            timeout_ms = int(parameters.get("timeout_ms", 1500))
            capture = await client.capture_image(
                width=width,
                height=height,
                timeout_ms=timeout_ms,
                include_base64=bool(parameters.get("include_base64", True)),
            )
            partial_data["capture"] = {
                key: value for key, value in capture.items() if key != "image_base64"
            }
        except Exception as exc:
            return {
                "success": False,
                "error": str(exc),
                "partial_data": partial_data,
            }

        duration = round(time.monotonic() - start, 2)

        delivery = {
            "readings": [
                {"type": "image_width", "value": capture.get("width"), "unit": "pixels"},
                {"type": "image_height", "value": capture.get("height"), "unit": "pixels"},
                {"type": "image_size", "value": capture.get("size_bytes"), "unit": "bytes"},
            ],
            "summary": (
                f"Visual inspection capture complete for '{task_description}'. "
                f"Captured {capture.get('width')}x{capture.get('height')} JPEG on pizerobot."
            ),
            "robot_id": "pizerobot",
            "robot_name": self.metadata().name,
            "duration_seconds": duration,
            "capture": {
                key: value
                for key, value in capture.items()
                if key not in {"image_base64"}
            },
        }
        if "image_base64" in capture:
            delivery["capture"]["image_base64"] = capture["image_base64"]
            delivery["capture"]["mime_type"] = capture.get("mime_type", "image/jpeg")

        return {"success": True, "delivery_data": delivery}
