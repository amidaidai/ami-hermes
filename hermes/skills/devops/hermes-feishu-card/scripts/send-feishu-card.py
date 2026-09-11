"""Send a Feishu interactive card via the sidecar events API.

Usage:
    python send-feishu-card.py "card text here" [--chat-id CHAT_ID] [--image PATH]

The sidecar at http://127.0.0.1:8765/events receives a sequence of
message.started → answer.delta → message.completed events and sends
a Feishu interactive card.

IMPORTANT:
- Text goes in answer.delta.data.text AND message.completed.data.answer
- MEDIA: references go in message.completed.data.answer
- platform must be "feishu"
"""

import json
import time
import urllib.request
import sys
import argparse

SIDECAR_URL = "http://127.0.0.1:8765/events"
DEFAULT_CHAT_ID = "oc_c4500490614a85b9b5db83f3f25b626a"


def send_event(event_name: str, message_id: str, chat_id: str,
               sequence: int, data: dict, created_at: float) -> bool:
    payload = {
        "schema_version": "1",
        "event": event_name,
        "conversation_id": chat_id,
        "message_id": message_id,
        "chat_id": chat_id,
        "platform": "feishu",
        "sequence": sequence,
        "created_at": created_at,
        "data": data,
    }
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        SIDECAR_URL,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        resp = urllib.request.urlopen(req, timeout=5)
        result = json.loads(resp.read())
        return result.get("ok", False)
    except Exception as e:
        print(f"  ERROR: {e}", file=sys.stderr)
        return False


def send_card(text: str, chat_id: str = DEFAULT_CHAT_ID, image_path: str = None) -> bool:
    """Send a card to Feishu via sidecar API."""
    now = time.time()
    mid = f"card_{int(now)}"

    # Include MEDIA: reference in the completed answer if image provided
    answer = text
    if image_path:
        answer += f"\nMEDIA:{image_path}"

    events = [
        ("message.started", {}),
        ("answer.delta", {"text": text}),
        ("message.completed", {
            "answer": answer,
            "duration_ms": 1500,
            "input_tokens": 2000,
            "output_tokens": len(text) // 4,
        }),
    ]

    success = True
    for i, (name, data) in enumerate(events):
        ok = send_event(name, mid, chat_id, i, data, now + i)
        tag = "OK" if ok else "FAIL"
        print(f"  {tag}  {name}", file=sys.stderr)
        if not ok:
            success = False

    return success


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Send a Feishu card via sidecar API")
    parser.add_argument("text", nargs="?", help="Card text (or read from stdin)")
    parser.add_argument("--chat-id", default=DEFAULT_CHAT_ID, help="Feishu chat ID")
    parser.add_argument("--image", help="Local image path (included as MEDIA: reference)")
    args = parser.parse_args()

    text = args.text
    if not text:
        text = sys.stdin.read()

    if not text.strip():
        print("Error: no card text provided", file=sys.stderr)
        sys.exit(1)

    print("Sending card...", file=sys.stderr)
    ok = send_card(text, args.chat_id, args.image)
    if ok:
        print("Card sent successfully", file=sys.stderr)
    else:
        print("Card send failed", file=sys.stderr)
        sys.exit(1)
