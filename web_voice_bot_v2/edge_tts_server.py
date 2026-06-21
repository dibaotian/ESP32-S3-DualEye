#!/usr/bin/env python3
"""
Minimal edge-tts HTTP server running on the host.
POST /tts  {"text": "...", "voice": "zh-CN-XiaoxiaoNeural"}  → WAV bytes
GET  /health → {"ok": true}
"""

import asyncio
import io
import json
import subprocess
import tempfile
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HOST = "0.0.0.0"
PORT = 8200
DEFAULT_VOICE = "zh-CN-XiaoxiaoNeural"


async def synthesize(text: str, voice: str) -> bytes:
    import edge_tts
    communicate = edge_tts.Communicate(text, voice)
    chunks = []
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            chunks.append(chunk["data"])
    return b"".join(chunks)


def mp3_to_wav(mp3_bytes: bytes) -> bytes:
    """Convert MP3 bytes to WAV bytes via ffmpeg."""
    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
        f.write(mp3_bytes)
        mp3_path = f.name
    wav_path = mp3_path.replace(".mp3", ".wav")
    try:
        subprocess.run(
            ["ffmpeg", "-y", "-i", mp3_path, "-ar", "24000", "-ac", "1", wav_path],
            capture_output=True, check=True
        )
        with open(wav_path, "rb") as f:
            return f.read()
    finally:
        for p in [mp3_path, wav_path]:
            if os.path.exists(p):
                os.unlink(p)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        print(f"[tts-server] {fmt % args}")

    def _json(self, code, body):
        data = json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path == "/health":
            self._json(200, {"ok": True, "voice": DEFAULT_VOICE})
        else:
            self._json(404, {"error": "not found"})

    def do_POST(self):
        if self.path != "/tts":
            self._json(404, {"error": "not found"})
            return
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length))
        text = body.get("text", "").strip()
        voice = body.get("voice", DEFAULT_VOICE)

        if not text:
            self._json(400, {"error": "text required"})
            return

        try:
            mp3_bytes = asyncio.run(synthesize(text, voice))
            wav_bytes = mp3_to_wav(mp3_bytes)
            self.send_response(200)
            self.send_header("Content-Type", "audio/wav")
            self.send_header("Content-Length", str(len(wav_bytes)))
            self.end_headers()
            self.wfile.write(wav_bytes)
            print(f"[tts-server] OK: {len(wav_bytes)} bytes for '{text[:40]}'")
        except Exception as e:
            print(f"[tts-server] ERROR: {e}")
            self._json(500, {"error": str(e)})


if __name__ == "__main__":
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"[tts-server] listening on http://{HOST}:{PORT}")
    server.serve_forever()
