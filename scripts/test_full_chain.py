#!/usr/bin/env python3
"""DeepSupport OS — full agent chain test driver (HTTP + SSE + auto HITL/ask resume).

Usage (repo root, after `docker compose up -d`):
    cd backend && uv run python ../scripts/test_full_chain.py \
        --base-url http://127.0.0.1:18000 \
        --message "我的 Outlook 登录不上，邮箱 wei.zhang@contoso.com" \
        --label outlook-wei \
        --timeout 480

For every interrupt it resumes automatically:
  - type=hitl -> POST /api/tasks/resume/stream {approved: true}
  - type=ask  -> POST /api/tasks/resume/stream {answer: <--ask-answer>}

Writes per-run SSE log to --out (default data/test_chain_<label>.jsonl) and
prints a compact summary: events, tools, subagents, final status.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request

# Console may be GBK on Windows; SSE content contains emoji/Chinese.
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):
    pass


def sse_events(url: str, payload: dict, timeout: float):
    """Yield (event, data_dict) parsed from an SSE POST stream."""
    req = urllib.request.Request(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    event = None
    data_lines: list[str] = []
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 (local test API)
        for raw in resp:
            line = raw.decode("utf-8", errors="replace").rstrip("\r\n")
            if line.startswith("event:"):
                event = line[6:].strip()
            elif line.startswith("data:"):
                data_lines.append(line[5:].strip())
            elif line == "":
                if event:
                    raw_data = "\n".join(data_lines)
                    try:
                        parsed = json.loads(raw_data)
                    except json.JSONDecodeError:
                        parsed = {"_raw": raw_data}
                    yield event, parsed
                event = None
                data_lines = []
    if event:
        yield event, {"_raw": "\n".join(data_lines)}


def resume(base: str, thread_id: str, task_id: str, *, approved: bool, answer: str | None) -> None:
    body = {
        "thread_id": thread_id,
        "task_id": task_id,
        "approved": approved,
        "answer": answer,
        "interrupt_type": "hitl" if approved and answer is None else "ask",
    }
    req = urllib.request.Request(
        f"{base}/api/tasks/resume/stream",
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    urllib.request.urlopen(req, timeout=10).read()  # noqa: S310 — resume stream consumed below


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default="http://127.0.0.1:18000")
    ap.add_argument("--message", required=True)
    ap.add_argument("--label", default="scenario")
    ap.add_argument("--timeout", type=float, default=480.0)
    ap.add_argument("--ask-answer", default="请继续排查，我提供的信息已经足够", help="canned answer for ask_user interrupts")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    out_path = args.out or f"data/test_chain_{args.label}.jsonl"
    log = open(out_path, "w", encoding="utf-8")
    summary = {
        "label": args.label,
        "message": args.message,
        "events": {},
        "tools": [],
        "subagents": [],
        "skills": [],
        "interrupts": [],
        "final_status": None,
        "final_message": None,
        "duration_ms": None,
    }
    start = time.time()
    deadline = start + args.timeout
    try:
        for event, data in sse_events(f"{args.base_url}/api/tasks/stream", {"message": args.message}, args.timeout):
            summary["events"][event] = summary["events"].get(event, 0) + 1
            log.write(json.dumps({"event": event, "data": data}, ensure_ascii=False) + "\n")
            log.flush()
            d = data if isinstance(data, dict) else {}

            if event == "tool_start":
                name = d.get("name") or d.get("tool") or "?"
                summary["tools"].append(name)
            if event == "subagent":
                summary["subagents"].append(str(d.get("agent") or d.get("name") or "?"))
            if event == "message":
                content = d.get("content") or ""
                if isinstance(content, str) and content.strip():
                    summary["final_message"] = content

            if event == "interrupt":
                itype = d.get("type", "hitl")
                thread_id = d.get("thread_id")
                task_id = d.get("task_id")
                summary["interrupts"].append({"type": itype, "thread_id": thread_id, "task_id": task_id})
                print(f"  [interrupt] type={itype} thread={thread_id} task={task_id}", flush=True)
                if itype == "ask":
                    resume(args.base_url, thread_id, task_id, approved=True, answer=args.ask_answer)
                else:
                    resume(args.base_url, thread_id, task_id, approved=True, answer=None)

            if event == "done":
                summary["final_status"] = d.get("status")
                summary["duration_ms"] = d.get("overview", {}).get("duration_ms")
                break

            if time.time() > deadline:
                summary["final_status"] = "TIMEOUT"
                break
    except urllib.error.HTTPError as exc:
        summary["final_status"] = f"HTTP_ERROR_{exc.code}"
        print(f"  [http error] {exc.code}: {exc.read().decode('utf-8', 'replace')[:300]}", flush=True)
    except Exception as exc:  # noqa: BLE001
        summary["final_status"] = f"EXCEPTION {type(exc).__name__}"
        print(f"  [exception] {type(exc).__name__}: {exc}", flush=True)

    summary["tools"] = sorted(set(summary["tools"]))
    summary["subagents"] = sorted(set(summary["subagents"]))
    log.close()

    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"log -> {out_path}")
    return 0 if summary["final_status"] in ("completed", "interrupted") else 1


if __name__ == "__main__":
    sys.exit(main())
