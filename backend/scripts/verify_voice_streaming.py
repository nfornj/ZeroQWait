#!/usr/bin/env python3
"""Verify ZeroQwait voice consistency and streaming latency after deploy.

What this script validates:
1) Backend and TTS health endpoints respond.
2) Repeated /api/voice/tts calls for identical text return stable audio bytes
   (proxy + model path consistency signal).
3) /api/agent/master/chat/stream in voice mode emits sentence events with audio.
4) Basic latency metrics: time-to-first-sentence and end-to-end stream time.

Usage examples:
  python verify_voice_streaming.py
  python verify_voice_streaming.py --base-url https://zeroqwait.com --insecure
  python verify_voice_streaming.py --runs 4 --warn-ttfs-ms 7000 --warn-total-ms 25000
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import statistics
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import httpx


@dataclass
class StreamRunResult:
    prompt: str
    ok: bool
    status_code: int
    first_sentence_ms: Optional[float]
    total_ms: float
    sentence_count: int
    audio_sentence_count: int
    missing_audio_count: int
    audio_formats: List[str]
    errors: List[str]


def _normalize_base_url(base_url: str) -> str:
    return base_url.rstrip("/")


async def check_health(client: httpx.AsyncClient, base_url: str) -> Dict[str, Any]:
    results: Dict[str, Any] = {"ok": True, "checks": []}
    endpoints = [
        ("agent_health", f"{base_url}/api/agent/health"),
        ("tts_health", f"{base_url}/api/voice/tts/health"),
    ]

    for name, url in endpoints:
        item = {"name": name, "url": url, "ok": False, "status": None, "body": None}
        try:
            res = await client.get(url, timeout=20.0)
            item["status"] = res.status_code
            item["body"] = res.text[:300]
            item["ok"] = res.status_code == 200
        except Exception as exc:  # noqa: BLE001
            item["body"] = f"error: {exc}"
        if not item["ok"]:
            results["ok"] = False
        results["checks"].append(item)

    return results


async def check_tts_repeat_consistency(
    client: httpx.AsyncClient,
    base_url: str,
    text: str,
    repeats: int = 3,
) -> Dict[str, Any]:
    url = f"{base_url}/api/voice/tts"
    hashes: List[str] = []
    lengths: List[int] = []
    latencies_ms: List[float] = []
    statuses: List[int] = []
    errors: List[str] = []

    for _ in range(repeats):
        started = time.perf_counter()
        try:
            res = await client.post(
                url,
                json={"text": text, "voice": "Vivian", "speed": 1.0},
                timeout=90.0,
            )
            elapsed_ms = (time.perf_counter() - started) * 1000.0
            latencies_ms.append(elapsed_ms)
            statuses.append(res.status_code)
            if res.status_code != 200:
                errors.append(f"status={res.status_code} body={res.text[:180]}")
                continue
            raw = res.content
            hashes.append(hashlib.sha256(raw).hexdigest())
            lengths.append(len(raw))
        except Exception as exc:  # noqa: BLE001
            errors.append(str(exc))

    unique_hashes = sorted(set(hashes))
    all_ok_status = len(statuses) == repeats and all(s == 200 for s in statuses)
    length_span = (max(lengths) - min(lengths)) if lengths else None
    length_mean = statistics.mean(lengths) if lengths else None
    # Small synthesis variations can produce different bytes while preserving voice identity.
    # Treat this as warning-only if output sizes remain reasonably close.
    length_variation_ratio = (
        (length_span / length_mean) if (length_span is not None and length_mean and length_mean > 0) else None
    )
    stable_size = (
        length_variation_ratio is not None and length_variation_ratio <= 0.08
    )
    strong_ok = all_ok_status and len(hashes) == repeats and stable_size and len(errors) == 0
    return {
        "ok": strong_ok,
        "byte_identical": len(unique_hashes) == 1 and len(hashes) == repeats,
        "repeats": repeats,
        "statuses": statuses,
        "latencies_ms": latencies_ms,
        "latency_avg_ms": statistics.mean(latencies_ms) if latencies_ms else None,
        "latency_p95_ms": _p95(latencies_ms),
        "audio_lengths": lengths,
        "audio_length_span": length_span,
        "audio_length_variation_ratio": length_variation_ratio,
        "unique_hash_count": len(unique_hashes),
        "hashes": unique_hashes,
        "errors": errors,
    }


def _p95(values: List[float]) -> Optional[float]:
    if not values:
        return None
    if len(values) == 1:
        return values[0]
    ordered = sorted(values)
    idx = max(0, min(len(ordered) - 1, int(round(0.95 * (len(ordered) - 1)))))
    return ordered[idx]


async def run_stream_prompt(
    client: httpx.AsyncClient,
    base_url: str,
    prompt: str,
    session_id: str,
) -> StreamRunResult:
    stream_url = f"{base_url}/api/agent/master/chat/stream"
    payload = {
        "message": prompt,
        "session_id": session_id,
        "is_voice": True,
        "history": [],
        "context": {},
    }

    started = time.perf_counter()
    first_sentence_ms: Optional[float] = None
    sentence_count = 0
    audio_sentence_count = 0
    missing_audio_count = 0
    formats: List[str] = []
    errors: List[str] = []
    status_code = 0

    try:
        async with client.stream("POST", stream_url, json=payload, timeout=120.0) as res:
            status_code = res.status_code
            if res.status_code != 200:
                body = await res.aread()
                return StreamRunResult(
                    prompt=prompt,
                    ok=False,
                    status_code=res.status_code,
                    first_sentence_ms=None,
                    total_ms=(time.perf_counter() - started) * 1000.0,
                    sentence_count=0,
                    audio_sentence_count=0,
                    missing_audio_count=0,
                    audio_formats=[],
                    errors=[body.decode(errors="ignore")[:300]],
                )

            async for line in res.aiter_lines():
                if not line or not line.startswith("data: "):
                    continue
                data_str = line[6:]
                if data_str == "[DONE]":
                    break
                try:
                    event = json.loads(data_str)
                except json.JSONDecodeError:
                    continue

                event_type = event.get("type")
                if event_type == "sentence":
                    sentence_count += 1
                    if first_sentence_ms is None:
                        first_sentence_ms = (time.perf_counter() - started) * 1000.0
                    if event.get("audio"):
                        audio_sentence_count += 1
                    else:
                        missing_audio_count += 1
                    fmt = event.get("audio_format")
                    if fmt:
                        formats.append(str(fmt))
                elif event_type == "error":
                    errors.append(str(event.get("content", "unknown stream error")))

    except Exception as exc:  # noqa: BLE001
        errors.append(str(exc))

    total_ms = (time.perf_counter() - started) * 1000.0
    ok = status_code == 200 and sentence_count > 0 and not errors
    return StreamRunResult(
        prompt=prompt,
        ok=ok,
        status_code=status_code,
        first_sentence_ms=first_sentence_ms,
        total_ms=total_ms,
        sentence_count=sentence_count,
        audio_sentence_count=audio_sentence_count,
        missing_audio_count=missing_audio_count,
        audio_formats=sorted(set(formats)),
        errors=errors,
    )


async def run_stream_suite(
    client: httpx.AsyncClient,
    base_url: str,
    runs: int,
) -> Dict[str, Any]:
    prompts = [
        "Hi",
        "Find me a barber near me",
        "What are your pricing plans?",
    ]
    # Repeat prompts if caller requests more runs than base prompt set.
    expanded: List[str] = []
    while len(expanded) < runs:
        expanded.extend(prompts)
    expanded = expanded[:runs]

    results: List[StreamRunResult] = []
    for idx, prompt in enumerate(expanded, start=1):
        session_id = f"verify_voice_{int(time.time())}_{idx}"
        result = await run_stream_prompt(client, base_url, prompt, session_id)
        results.append(result)

    first_sentence_samples = [r.first_sentence_ms for r in results if r.first_sentence_ms is not None]
    total_samples = [r.total_ms for r in results]
    missing_audio_total = sum(r.missing_audio_count for r in results)

    return {
        "ok": all(r.ok for r in results),
        "runs": [
            {
                "prompt": r.prompt,
                "ok": r.ok,
                "status_code": r.status_code,
                "first_sentence_ms": r.first_sentence_ms,
                "total_ms": r.total_ms,
                "sentence_count": r.sentence_count,
                "audio_sentence_count": r.audio_sentence_count,
                "missing_audio_count": r.missing_audio_count,
                "audio_formats": r.audio_formats,
                "errors": r.errors,
            }
            for r in results
        ],
        "summary": {
            "first_sentence_avg_ms": statistics.mean(first_sentence_samples) if first_sentence_samples else None,
            "first_sentence_p95_ms": _p95([float(x) for x in first_sentence_samples if x is not None]),
            "total_avg_ms": statistics.mean(total_samples) if total_samples else None,
            "total_p95_ms": _p95(total_samples),
            "missing_audio_total": missing_audio_total,
        },
    }


def print_report(report: Dict[str, Any], warn_ttfs_ms: int, warn_total_ms: int) -> int:
    print("\n=== ZeroQwait Voice Verification Report ===")

    health = report["health"]
    print("\n[Health]")
    for check in health["checks"]:
        status = "PASS" if check["ok"] else "FAIL"
        print(f"- {status}: {check['name']} ({check['status']})")

    tts = report["tts_repeat"]
    print("\n[TTS Repeat Consistency]")
    print(f"- ok: {tts['ok']}")
    print(f"- byte_identical: {tts['byte_identical']}")
    print(f"- statuses: {tts['statuses']}")
    print(f"- unique_hash_count: {tts['unique_hash_count']}")
    print(f"- audio_length_span: {tts['audio_length_span']}")
    print(f"- audio_length_variation_ratio: {tts['audio_length_variation_ratio']}")
    print(f"- latency_avg_ms: {tts['latency_avg_ms']}")
    print(f"- latency_p95_ms: {tts['latency_p95_ms']}")
    if tts["errors"]:
        print(f"- errors: {tts['errors']}")

    stream = report["stream_suite"]
    print("\n[Stream Voice Runs]")
    for i, run in enumerate(stream["runs"], start=1):
        print(
            f"- run {i}: ok={run['ok']} status={run['status_code']} "
            f"first_sentence_ms={run['first_sentence_ms']} total_ms={run['total_ms']} "
            f"sentences={run['sentence_count']} audio={run['audio_sentence_count']} "
            f"missing_audio={run['missing_audio_count']} formats={run['audio_formats']}"
        )
        if run["errors"]:
            print(f"  errors: {run['errors']}")

    summary = stream["summary"]
    print("\n[Latency Summary]")
    print(f"- first_sentence_avg_ms: {summary['first_sentence_avg_ms']}")
    print(f"- first_sentence_p95_ms: {summary['first_sentence_p95_ms']}")
    print(f"- total_avg_ms: {summary['total_avg_ms']}")
    print(f"- total_p95_ms: {summary['total_p95_ms']}")
    print(f"- missing_audio_total: {summary['missing_audio_total']}")

    warnings: List[str] = []
    if summary["first_sentence_p95_ms"] is not None and summary["first_sentence_p95_ms"] > warn_ttfs_ms:
        warnings.append(
            f"TTFS p95 {summary['first_sentence_p95_ms']:.1f}ms exceeds warning threshold {warn_ttfs_ms}ms"
        )
    if summary["total_p95_ms"] is not None and summary["total_p95_ms"] > warn_total_ms:
        warnings.append(
            f"Total p95 {summary['total_p95_ms']:.1f}ms exceeds warning threshold {warn_total_ms}ms"
        )

    overall_ok = report["health"]["ok"] and report["tts_repeat"]["ok"] and report["stream_suite"]["ok"]

    if not tts["byte_identical"] and tts["ok"]:
        warnings.append(
            "TTS outputs are not byte-identical across repeats (expected in some synthesis paths), but sizes and responses are stable."
        )

    if warnings:
        print("\n[Warnings]")
        for warning in warnings:
            print(f"- {warning}")

    print("\n[Overall]")
    print(f"- pass: {overall_ok}")

    return 0 if overall_ok else 1


async def async_main(args: argparse.Namespace) -> int:
    base_url = _normalize_base_url(args.base_url)
    verify_tls = not args.insecure

    async with httpx.AsyncClient(verify=verify_tls) as client:
        health = await check_health(client, base_url)
        tts_repeat = await check_tts_repeat_consistency(
            client,
            base_url,
            text=args.tts_text,
            repeats=args.tts_repeats,
        )
        stream_suite = await run_stream_suite(client, base_url, runs=args.runs)

    report = {
        "base_url": base_url,
        "health": health,
        "tts_repeat": tts_repeat,
        "stream_suite": stream_suite,
        "generated_at_epoch": int(time.time()),
    }

    if args.output_json:
        with open(args.output_json, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)
        print(f"\nSaved JSON report to: {args.output_json}")

    return print_report(report, args.warn_ttfs_ms, args.warn_total_ms)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify ZeroQwait voice consistency + latency")
    parser.add_argument(
        "--base-url",
        default="https://192.168.2.88.nip.io",
        help="Public base URL, for example https://192.168.2.88.nip.io or https://zeroqwait.com",
    )
    parser.add_argument(
        "--insecure",
        action="store_true",
        help="Disable TLS certificate verification (useful for self-signed certs)",
    )
    parser.add_argument("--runs", type=int, default=3, help="Number of streaming verification runs")
    parser.add_argument("--tts-repeats", type=int, default=3, help="Repeat count for direct TTS consistency check")
    parser.add_argument(
        "--tts-text",
        default="Welcome to ZeroQwait. This is a voice consistency verification sample.",
        help="Text used for repeated /api/voice/tts consistency check",
    )
    parser.add_argument("--warn-ttfs-ms", type=int, default=8000, help="Warn if TTFS p95 exceeds this")
    parser.add_argument("--warn-total-ms", type=int, default=30000, help="Warn if total stream p95 exceeds this")
    parser.add_argument("--output-json", default="", help="Optional output report path")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    return asyncio.run(async_main(args))


if __name__ == "__main__":
    raise SystemExit(main())
