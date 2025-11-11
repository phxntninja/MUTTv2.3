#!/usr/bin/env python3
"""
Simple Mock Moog Webhook service for integration testing.

Endpoints:
- POST /events  -> accepts JSON payloads, increments counters
- GET  /health  -> basic health
- GET  /stats   -> returns counts

Env:
- PORT (default 8080)
"""

from flask import Flask, request, jsonify
import threading

app = Flask(__name__)

class Stats:
    def __init__(self):
        self.lock = threading.Lock()
        self.count = 0
        self.last = None

    def inc(self, payload):
        with self.lock:
            self.count += 1
            self.last = payload

stats = Stats()

@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "healthy", "service": "mock-moog"})

@app.route('/events', methods=['POST'])
def events():
    try:
        payload = request.get_json(force=True, silent=True)
        stats.inc(payload)
        return jsonify({"ok": True}), 200
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 400

@app.route('/stats', methods=['GET'])
def get_stats():
    with stats.lock:
        return jsonify({"count": stats.count, "last": stats.last})

if __name__ == '__main__':
    import os
    port = int(os.environ.get('PORT', '8080'))
    app.run(host='0.0.0.0', port=port)

