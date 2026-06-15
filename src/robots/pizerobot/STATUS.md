# Pizerobot Status

## Goal

Build a real-hardware MCP path for this repo using a Raspberry Pi Zero W:

`MCP client -> yakrover MCP gateway -> /pizerobot/mcp -> Pi service -> Raspberry Pi camera / telemetry / GPIO`

## Current State

- `pizerobot` is discoverable by the existing `scripts/serve.py` gateway flow.
- Split gateway mode works:
  - Mac runs the yakrover MCP gateway.
  - Pi Zero W runs the tiny `pi_service.py` HTTP service.
  - MCP tools trigger Pi camera, telemetry, and servo actions over LAN.
- Pi-hosted core gateway mode also works:
  - Pi Zero W runs `scripts/serve.py --robots pizerobot --port 8002`.
  - Pi Zero W runs `pi_service.py` locally on `127.0.0.1:8081`.
  - A Mac MCP client called the Pi-hosted endpoint and moved the servo through GPIO18.
- Public ngrok/marketplace exposure has not yet been moved onto the Pi.

Confirmed working end-to-end:

- `pizerobot_is_online`
- `pizerobot_get_system_status`
- `pizerobot_get_cpu_temperature`
- `pizerobot_camera_is_available`
- `pizerobot_capture_image`
- `pizerobot_servo_sweep`

## Full-Stack Pi Zero W Install Findings

Test board:

- Raspberry Pi Zero W v1.1
- `armv6l`
- one CPU core
- about `427MiB` RAM plus about `426MiB` swap
- Python `3.13.5`

Install notes:

- The first concrete blocker was missing Python development headers.
- Failed source builds reported `fatal error: Python.h: No such file or directory`.
- Installing `python3-dev` / `python3.13-dev` fixed that blocker.
- The successful core dependency install took about 27 minutes after headers were installed.
- The prior failed attempt took about 13 minutes before reaching the missing-header failure.
- The full elapsed setup time was over 40 minutes when including the failed attempt, header fix, retry, service debugging, and servo backend work.

Slow or risky dependency areas:

- `agent0-sdk`
- `web3` / `eth-account` / Ethereum crypto dependencies
- `ipfshttpclient` / `multiaddr` / `py-multihash`
- `fastmcp`
- `fastapi` / `uvicorn`

Packages that had to build locally on ARMv6:

- `ckzg`
- `mmh3`
- `psutil`

Those source builds succeeded after Python development headers were installed.

## Runtime Footprint

Observed after the successful Pi-hosted core gateway run:

- `.venv` size: about `170M`
- root filesystem free space after install: about `2.9G`
- heavy import check: about `36s`
- gateway startup: under one minute
- Pi-hosted gateway memory while busy: about `76MB RSS`
- Pi-hosted gateway plus local hardware service: about `94MB RSS`
- system memory still available with both processes running: about `263MiB`
- swap used: about `15MiB`
- successful MCP temperature read returned about `47.62C`

## Servo Notes

- Tested servo signal pin: GPIO18.
- The isolated full-stack venv needed GPIO packages installed; system Python already had them.
- GPIO Zero's default backend in the venv reported `PWM is not supported on pin GPIO18`.
- Forcing `GPIOZERO_PIN_FACTORY=rpigpio` allowed direct service servo control and full MCP-triggered servo control.
- The successful final path was:

```text
Mac FastMCP client
  -> http://<pi-ip>:8002/pizerobot/mcp
  -> yakrover MCP gateway running on Pi Zero W
  -> Pi-local pizerobot service on 127.0.0.1:8081
  -> GPIO18 PWM
  -> servo
```

## What Is Not Yet Proven

- Running ngrok from the Pi.
- Publishing the Pi-hosted endpoint as the public marketplace route.
- Long-running reliability under repeated requests.
- Camera capture and servo motion under concurrent task load.
- Battery/power behavior under servo load.

## Discord-Safe Summary

The first demo used a split architecture: Mac-hosted marketplace/MCP gateway
and Pi-hosted hardware service. That was still a real MCP-triggered Pi hardware
demo.

The later benchmark got the core yakrover/FastMCP stack running directly on the
Pi Zero W. The Pi served `/pizerobot/mcp` locally on LAN, and an MCP call from a
Mac client triggered GPIO18 servo movement through the Pi-hosted gateway and
Pi-local hardware service.

The remaining caveat is public exposure: ngrok/marketplace routing has not yet
been moved onto the Pi.
