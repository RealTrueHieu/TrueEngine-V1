import http.server
import socketserver
import json
import os
import sys
import subprocess
import time

PORT = 8765
METRICS_PATH = "/content/selfplay_100m_metrics.json"
DISTILLED_PATH = "/content/colab_distilled_experience.json"
REPLAY_INBOX = "/content/local_inbox_positions.json"

class CloudBridgeHandler(http.server.BaseHTTPRequestHandler):
    def _send_json(self, data, status=200):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode("utf-8"))

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        if self.path == "/health":
            self._send_json({
                "status": "online",
                "service": "TrueEngine Cloud Bridge",
                "timestamp": int(time.time()),
                "pid": os.getpid()
            })
        elif self.path == "/metrics":
            if os.path.exists(METRICS_PATH):
                with open(METRICS_PATH, "r", encoding="utf-8") as f:
                    try:
                        data = json.load(f)
                    except Exception:
                        data = {"error": "Metrics file currently being written"}
                self._send_json(data)
            else:
                self._send_json({"error": "Metrics not ready yet"}, status=404)
        elif self.path == "/distilled":
            if os.path.exists(DISTILLED_PATH):
                with open(DISTILLED_PATH, "r", encoding="utf-8") as f:
                    try:
                        data = json.load(f)
                    except Exception:
                        data = {}
                self._send_json(data)
            else:
                self._send_json({"error": "Distilled data not ready yet"}, status=404)
        else:
            self._send_json({"error": f"Unknown endpoint: {self.path}"}, status=404)

    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", 0))
        post_data = self.rfile.read(content_length)
        try:
            body = json.loads(post_data.decode("utf-8"))
        except Exception:
            body = {}

        if self.path == "/push_blunder":
            # Receive blunder lines from Local En Croissant matches to prioritize in training
            try:
                existing = []
                if os.path.exists(REPLAY_INBOX):
                    with open(REPLAY_INBOX, "r", encoding="utf-8") as f:
                        existing = json.load(f)
                existing.append({
                    "data": body,
                    "received_at": int(time.time())
                })
                with open(REPLAY_INBOX, "w", encoding="utf-8") as f:
                    json.dump(existing, f, indent=2)
                self._send_json({"status": "received", "total_inbox": len(existing)})
            except Exception as e:
                self._send_json({"error": str(e)}, status=500)
        else:
            self._send_json({"error": f"Unknown POST endpoint: {self.path}"}, status=404)

def run():
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("127.0.0.1", PORT), CloudBridgeHandler) as httpd:
        print(f"[CloudBridge] Local HTTP server listening on http://127.0.0.1:{PORT}", flush=True)
        httpd.serve_forever()

if __name__ == "__main__":
    run()
