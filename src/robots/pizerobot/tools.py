from fastmcp import FastMCP

from .client import PiZeroRobotClient


def register(mcp: FastMCP, robot: PiZeroRobotClient) -> None:
    """Register Raspberry Pi Zero camera, status, and servo tools on the server."""

    @mcp.tool
    async def pizerobot_is_online() -> dict:
        """Check if the Pi-side service is reachable."""
        return await robot.is_online()

    @mcp.tool
    async def pizerobot_get_system_status() -> dict:
        """Return Pi hostname, uptime, load, memory, disk, and network status."""
        return await robot.get_system_status()

    @mcp.tool
    async def pizerobot_get_cpu_temperature() -> dict:
        """Return the Raspberry Pi CPU/SoC temperature."""
        return await robot.get_cpu_temperature()

    @mcp.tool
    async def pizerobot_camera_is_available() -> dict:
        """Check whether the Pi camera stack sees a camera module."""
        return await robot.camera_is_available()

    @mcp.tool
    async def pizerobot_capture_image(
        width: int = 640,
        height: int = 480,
        timeout_ms: int = 1500,
        include_base64: bool = False,
    ) -> dict:
        """Capture a still image on the Pi camera service."""
        return await robot.capture_image(
            width=width,
            height=height,
            timeout_ms=timeout_ms,
            include_base64=include_base64,
        )

    @mcp.tool
    async def pizerobot_servo_sweep(
        gpio_pin: int = 18,
        delay_seconds: float = 0.7,
    ) -> dict:
        """Sweep a small hobby servo connected to a Pi GPIO pin."""
        return await robot.servo_sweep(
            gpio_pin=gpio_pin,
            delay_seconds=delay_seconds,
        )
