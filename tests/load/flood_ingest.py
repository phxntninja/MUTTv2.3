#!/usr/bin/env python3
"""
MUTT v2.5 - Simple Ingest Load Generator

Sends concurrent POSTs to /api/v2/ingest and reports rate/success.

Usage:
  python tests/load/flood_ingest.py --url http://localhost:8080/api/v2/ingest \
    --api-key test-ingest --count 10000 --threads 10
"""

import argparse
import concurrent.futures
import json
import random
import time
from typing import Tuple

import requests


def send(i: int, url: str, api_key: str, timeout: float) -> Tuple[int, int]:
    payload = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "message": f"Load test message {i}",
        "hostname": f"load-host-{i % 100}",
        "syslog_severity": random.choice([3, 4, 5])
    }
    try:
        r = requests.post(url, json=payload, headers={"X-API-KEY": api_key}, timeout=timeout)
        return (1 if r.status_code == 200 else 0), 1
    except Exception:
        return 0, 1


def main():
    p = argparse.ArgumentParser(description="MUTT ingest load generator")
    p.add_argument('--url', required=True, help='Ingest endpoint URL (e.g., http://localhost:8080/api/v2/ingest)')
    p.add_argument('--api-key', required=True, help='API key for ingest')
    p.add_argument('--count', type=int, default=1000, help='Total messages to send')
    p.add_argument('--threads', type=int, default=10, help='Concurrent workers')
    p.add_argument('--timeout', type=float, default=5.0, help='Request timeout in seconds')
    args = p.parse_args()

    start = time.time()
    success = 0
    total = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.threads) as ex:
        futs = [ex.submit(send, i, args.url, args.api_key, args.timeout) for i in range(args.count)]
        for f in concurrent.futures.as_completed(futs):
            ok, one = f.result()
            success += ok
            total += one

    dur = time.time() - start
    eps = total / dur if dur > 0 else 0
    print(json.dumps({
        "sent": total,
        "success": success,
        "fail": total - success,
        "duration_sec": round(dur, 3),
        "rate_eps": round(eps, 2)
    }, indent=2))


if __name__ == '__main__':
    main()

