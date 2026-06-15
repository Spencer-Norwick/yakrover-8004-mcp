# Pizerobot Setup

`pizerobot` is a Raspberry Pi Zero W integration for camera, telemetry, and
small hobby-servo control over MCP.

## Architecture

Two deployment modes are useful:

### Split Gateway Mode

- Mac runs the standard `yakrover-8004-mcp` gateway
- Pi Zero W runs only `src/robots/pizerobot/pi_service.py`
- the `pizerobot` plugin talks to the Pi service over HTTP

This keeps the Pi-side runtime small enough for a practical demo on Pi Zero W
hardware.

### Pi-Hosted Core Gateway Mode

- Pi Zero W runs `scripts/serve.py --robots pizerobot`
- Pi Zero W also runs `src/robots/pizerobot/pi_service.py`
- an external MCP client calls the Pi-hosted `/pizerobot/mcp` endpoint

This has been tested successfully on a Pi Zero W v1.1 for local LAN access.
Pi-hosted ngrok has also been tested to the public gateway root endpoint.

## Hardware

Minimum hardware:

- Raspberry Pi Zero W v1.1
- microSD card with Raspberry Pi OS Lite
- optional CSI ribbon camera module for image capture
- optional soldered GPIO header for servo control
- small 3-wire hobby servo on GPIO18 for the current servo smoke test

Servo power note:

- Power the servo from a suitable external supply when possible.
- Connect Pi ground and servo power ground together.
- Do not rely on the Pi Zero's 3.3V GPIO pin to power a motor.

## Pi Image / OS

Recommended image:

- Raspberry Pi OS Lite

Recommended first-boot settings:

- Enable SSH
- Configure Wi-Fi
- Set hostname
- Set username/password

## Runtime Expectations

Expected on the Raspberry Pi:

- `python3`
- the repo checked out locally
- one camera command available:
  - `rpicam-still`, or
  - `libcamera-still`
- `gpiozero` plus a PWM-capable GPIO backend for servo control
- for the isolated Pi full-stack venv, install the Pi GPIO packages:

```bash
.venv/bin/python -m pip install gpiozero RPi.GPIO lgpio
```

Environment:

- Mac gateway side:
  - `PIZEROBOT_URL=http://<pi-ip>:8081`
- Pi service side:
  - `PIZEROBOT_SERVICE_PORT=8081` by default
  - `GPIOZERO_PIN_FACTORY=rpigpio` when running from an isolated venv on this Pi Zero W

## Run

### Pi-side service only

From the repo root on the Pi:

```bash
python3 src/robots/pizerobot/pi_service.py
```

### Mac-side gateway

From the repo root on the Mac:

```bash
PIZEROBOT_URL=http://<pi-ip>:8081 PYTHONPATH=src uv run python scripts/serve.py --robots pizerobot
```

MCP endpoint:

```text
http://<pi-host-or-ip>:8000/pizerobot/mcp
```

### Pi-hosted core gateway

From the repo root on the Pi:

```bash
GPIOZERO_PIN_FACTORY=rpigpio python3 src/robots/pizerobot/pi_service.py
```

In a second shell on the Pi:

```bash
PIZEROBOT_URL=http://127.0.0.1:8081 PYTHONPATH=src .venv/bin/python scripts/serve.py --robots pizerobot --port 8002
```

MCP endpoint:

```text
http://<pi-ip>:8002/pizerobot/mcp
```

### Pi-hosted ngrok gateway

Stop any Mac gateway using the same static ngrok domain first. Then run on the
Pi:

```bash
PIZEROBOT_URL=http://127.0.0.1:8081 PYTHONPATH=src \
  .venv/bin/python scripts/serve.py --robots pizerobot --port 8002 --ngrok
```

Public endpoint:

```text
https://<ngrok-domain>/pizerobot/mcp
```

On first run, `pyngrok` may download and install the ngrok agent for the Pi.

## Current Tools

- `pizerobot_is_online`
- `pizerobot_get_system_status`
- `pizerobot_get_cpu_temperature`
- `pizerobot_camera_is_available`
- `pizerobot_capture_image`
- `pizerobot_servo_sweep`

Suggested smoke-test order:

1. `pizerobot_is_online`
2. `pizerobot_get_cpu_temperature`
3. `pizerobot_camera_is_available`
4. `pizerobot_capture_image`
5. `pizerobot_servo_sweep`

## Current Limits

- local LAN Pi-hosted MCP gateway works
- Pi-hosted ngrok starts and serves the public gateway root URL
- public MCP tool calls through Pi-hosted ngrok still need a final client smoke test
- marketplace metadata has not yet been repointed specifically for Pi-hosted exposure
- GPIO Zero servo control from the isolated venv needs a PWM-capable backend;
  `GPIOZERO_PIN_FACTORY=rpigpio` worked for the tested Pi Zero W
