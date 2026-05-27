#!/usr/bin/env python3
"""Run one existing-shop simulation process per manifest target."""

from __future__ import annotations

import asyncio
import json
import os
import re
import signal
import sys
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
DEFAULT_MANIFEST_PATH = Path(os.getenv("SIM_MANIFEST_PATH", BASE_DIR / "shop_manifest.json"))
START_STAGGER_SECONDS = float(os.getenv("SIM_START_STAGGER_SECONDS", "0"))


def load_manifest() -> list[dict]:
    with DEFAULT_MANIFEST_PATH.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    targets = data.get("targets", data)
    if not isinstance(targets, list):
        raise RuntimeError("Simulation manifest must contain a top-level list or a 'targets' list")
    return targets


def _safe_key(value: object) -> str:
    key = re.sub(r"[^a-z0-9]+", "-", str(value).lower()).strip("-")
    return key or "demo-shop"


def default_employee_specs(target: dict) -> list[dict]:
    key = _safe_key(target.get("key") or target.get("shop_slug") or target.get("shop_name"))
    password = str(target.get("employee_password") or target.get("owner_password") or "Test123!")
    return [
        {
            "display_name": "Marcus",
            "email": f"marcus.{key}@zeroqwait.demo",
            "username": f"marcus-{key}",
            "password": password,
        },
        {
            "display_name": "Elena",
            "email": f"elena.{key}@zeroqwait.demo",
            "username": f"elena-{key}",
            "password": password,
        },
    ]


def build_env(target: dict) -> dict[str, str]:
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    env["SIM_LOG_ONLY"] = "true"
    env["SIM_ALLOW_USER_CREATE"] = str(target.get("allow_user_create", False)).lower()
    env["SIM_ALLOW_SHOP_CREATE"] = str(target.get("allow_shop_create", False)).lower()
    env["SIM_OWNER_EMAIL"] = str(target["owner_email"])
    env["SIM_OWNER_PASSWORD"] = str(target["owner_password"])
    env["SIM_OWNER_DISPLAY_NAME"] = str(target.get("owner_display_name", target.get("key", "owner")))
    env["SHOP_NAME"] = str(target.get("shop_name", ""))
    if target.get("shop_slug"):
        env["SIM_SHOP_SLUG"] = str(target["shop_slug"])
    env["SIM_EMPLOYEE_SPECS"] = json.dumps(target.get("employees") or default_employee_specs(target))
    for key, value in (target.get("env") or {}).items():
        env.setdefault(str(key), str(value))
    return env


async def pipe_output(prefix: str, stream: asyncio.StreamReader) -> None:
    while True:
        line = await stream.readline()
        if not line:
            return
        print(f"[{prefix}] {line.decode(errors='replace').rstrip()}", flush=True)


async def run_target(target: dict, delay_seconds: float = 0.0) -> int:
    if delay_seconds > 0:
        await asyncio.sleep(delay_seconds)
    key = target.get("key") or target.get("shop_name") or target["owner_email"]
    process = await asyncio.create_subprocess_exec(
        sys.executable,
        "-u",
        "main.py",
        cwd=str(BASE_DIR),
        env=build_env(target),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout_task = asyncio.create_task(pipe_output(str(key), process.stdout))
    stderr_task = asyncio.create_task(pipe_output(str(key), process.stderr))
    try:
        return await process.wait()
    finally:
        stdout_task.cancel()
        stderr_task.cancel()
        await asyncio.gather(stdout_task, stderr_task, return_exceptions=True)


async def main() -> int:
    targets = load_manifest()
    if not targets:
        print("No simulation targets found in manifest.", flush=True)
        return 1

    tasks = [
        asyncio.create_task(run_target(target, index * START_STAGGER_SECONDS))
        for index, target in enumerate(targets)
    ]

    def _stop() -> None:
        for task in tasks:
            task.cancel()

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            asyncio.get_running_loop().add_signal_handler(sig, _stop)
        except NotImplementedError:
            pass

    try:
        results = await asyncio.gather(*tasks)
    except asyncio.CancelledError:
        return 1

    return 0 if all(code == 0 for code in results) else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))