#!/usr/bin/env python3
"""Lightweight system poller for cron.

Usage: run without args to collect a default set of metrics, or pass
one or more comma-separated categories on the command line.

Categories: cpu, memory, disk, net_if, net_errors, bandwidth

Output format (one line per category):
  <ISOtimestamp> <scriptname> <category> collected <k1>=<v1>,<k2>=<v2>

Designed to be cron-friendly (emit single-line records to stdout).
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import time
from typing import Dict, List

import psutil


SCRIPT_NAME = os.path.basename(__file__)


def ts() -> str:
    return datetime.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def fmt_line(category: str, data: Dict[str, object]) -> str:
    # Flatten data into comma-separated key=repr(value) pairs. For nested dicts,
    # JSON-encode the value so it's a single token.
    pairs: List[str] = []
    for k, v in data.items():
        if isinstance(v, (dict, list)):
            sval = json.dumps(v, separators=(",", ":"))
        else:
            sval = str(v)
        pairs.append(f"{k}={sval}")
    return f"{ts()} {SCRIPT_NAME} {category} collected {', '.join(pairs)}"


def collect_cpu() -> Dict[str, object]:
    return {
        "cpu_percent": psutil.cpu_percent(interval=0.5),
        "cpu_count_logical": psutil.cpu_count(logical=True),
        "cpu_count_physical": psutil.cpu_count(logical=False),
    }


def collect_memory() -> Dict[str, object]:
    mem = psutil.virtual_memory()
    return {
        "total": mem.total,
        "available": mem.available,
        "percent": mem.percent,
        "used": mem.used,
    }


def collect_disk(path: str = "/") -> Dict[str, object]:
    d = psutil.disk_usage(path)
    return {"path": path, "total": d.total, "free": d.free, "percent": d.percent}


def collect_net_if() -> Dict[str, object]:
    stats = psutil.net_if_stats()
    addrs = psutil.net_if_addrs()
    out = {}
    for ifname, st in stats.items():
        a = addrs.get(ifname, [])
        # collect IPs
        ips = []
        for addr in a:
            try:
                famname = addr.family.name
            except Exception:
                famname = ""
            ips.append(addr.address)
        out[ifname] = {
            "isup": bool(st.isup),
            "mtu": getattr(st, "mtu", None),
            "speed_mbps": getattr(st, "speed", None),
            "ips": ips,
        }
    return out


def collect_net_errors() -> Dict[str, object]:
    counters = psutil.net_io_counters(pernic=True)
    out = {}
    for ifname, c in counters.items():
        out[ifname] = {
            "errin": getattr(c, "errin", 0),
            "errout": getattr(c, "errout", 0),
            "dropin": getattr(c, "dropin", 0),
            "dropout": getattr(c, "dropout", 0),
        }
    return out


def measure_bandwidth(interval: float = 1.0, ifname: str | None = None) -> Dict[str, object]:
    # sample net io counters, wait interval, sample again and compute bytes/sec
    before = psutil.net_io_counters(pernic=True)
    time.sleep(interval)
    after = psutil.net_io_counters(pernic=True)
    out = {}
    names = [ifname] if ifname else list(after.keys())
    for name in names:
        b0 = before.get(name)
        b1 = after.get(name)
        if not b0 or not b1:
            continue
        sent_per_s = (b1.bytes_sent - b0.bytes_sent) / interval
        recv_per_s = (b1.bytes_recv - b0.bytes_recv) / interval
        out[name] = {"sent_Bps": int(sent_per_s), "recv_Bps": int(recv_per_s)}
    return out


DEFAULT_CATEGORIES = ["cpu", "memory", "disk", "net_if", "net_errors"]


def run_categories(categories: List[str]) -> None:
    for cat in categories:
        if cat == "cpu":
            print(fmt_line("cpu", collect_cpu()))
        elif cat == "memory":
            print(fmt_line("memory", collect_memory()))
        elif cat == "disk":
            print(fmt_line("disk", collect_disk()))
        elif cat == "net_if":
            print(fmt_line("net_if", collect_net_if()))
        elif cat == "net_errors":
            print(fmt_line("net_errors", collect_net_errors()))
        elif cat.startswith("bandwidth"):
            # allow optional interface: bandwidth or bandwidth:eth0
            parts = cat.split(":", 1)
            iface = parts[1] if len(parts) > 1 else None
            print(fmt_line("bandwidth", measure_bandwidth(ifname=iface)))
        else:
            print(fmt_line("unknown", {"requested": cat}))


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Simple cron-friendly system poller")
    p.add_argument("categories", nargs="?", help="Comma-separated categories to collect")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    if args.categories:
        cats = [c.strip() for c in args.categories.split(",") if c.strip()]
    else:
        cats = DEFAULT_CATEGORIES
    run_categories(cats)


if __name__ == "__main__":
    main()
