#!/usr/bin/env python3
"""
Import OpenMetrics data into Prometheus via Remote Write API.

Usage:
  python3 import_to_prometheus.py [--url http://192.168.1.20:9090]

Requires: pip install requests snappy
Note: Prometheus must have --web.enable-remote-write-receiver flag enabled.
"""

import sys
import os
import struct
import time
import requests
import snappy

script_dir = os.path.dirname(os.path.abspath(__file__))
os.chdir(script_dir)

PROMETHEUS_URL = "http://192.168.1.20:9090"
if '--url' in sys.argv:
    PROMETHEUS_URL = sys.argv[sys.argv.index('--url') + 1]

REMOTE_WRITE_URL = f"{PROMETHEUS_URL}/api/v1/write"
BATCH_SIZE = 500  # samples per request


def encode_varint(value):
    """Encode an integer as a varint."""
    bits = value & 0x7f
    value >>= 7
    result = b''
    while value:
        result += bytes([0x80 | bits])
        bits = value & 0x7f
        value >>= 7
    result += bytes([bits])
    return result


def encode_string(field_number, s):
    """Encode a string field in protobuf."""
    encoded = s.encode('utf-8')
    return encode_varint((field_number << 3) | 2) + encode_varint(len(encoded)) + encoded


def encode_label(name, value):
    """Encode a Label message."""
    data = encode_string(1, name) + encode_string(2, value)
    return encode_varint((1 << 3) | 2) + encode_varint(len(data)) + data


def encode_sample(timestamp_ms, value):
    """Encode a Sample message."""
    # field 1: double value, field 2: int64 timestamp
    data = (bytes([0x09]) + struct.pack('<d', value) +
            bytes([0x10]) + encode_varint(timestamp_ms))
    return encode_varint((2 << 3) | 2) + encode_varint(len(data)) + data


def encode_timeseries(labels, samples):
    """Encode a TimeSeries message."""
    data = b''
    for name, value in labels:
        data += encode_label(name, value)
    for ts_ms, val in samples:
        data += encode_sample(ts_ms, val)
    return encode_varint((1 << 3) | 2) + encode_varint(len(data)) + data


def parse_openmetrics(filepath):
    """Parse openmetrics file into series dict: {(metric, labels_tuple): [(ts_ms, value)]}."""
    series = {}
    with open(filepath, 'r') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            # Parse: metric_name{label="value"} number timestamp
            try:
                if '{' in line:
                    metric_part, rest = line.split('}', 1)
                    metric_name, labels_str = metric_part.split('{', 1)
                    # Parse labels
                    labels = [("__name__", metric_name)]
                    for pair in labels_str.split(','):
                        k, v = pair.split('=', 1)
                        labels.append((k.strip(), v.strip().strip('"')))
                else:
                    parts = line.split()
                    metric_name = parts[0]
                    labels = [("__name__", metric_name)]
                    rest = ' '.join(parts[1:])

                parts = rest.strip().split()
                value = float(parts[0])
                ts_sec = float(parts[1])
                ts_ms = int(ts_sec * 1000)

                key = tuple(labels)
                if key not in series:
                    series[key] = []
                series[key].append((ts_ms, value))
            except (ValueError, IndexError):
                continue
    return series


def send_batch(timeseries_data):
    """Send a batch of timeseries via remote write."""
    write_request = b''
    for ts_data in timeseries_data:
        write_request += ts_data

    compressed = snappy.compress(write_request)

    resp = requests.post(
        REMOTE_WRITE_URL,
        data=compressed,
        headers={
            'Content-Type': 'application/x-protobuf',
            'Content-Encoding': 'snappy',
            'X-Prometheus-Remote-Write-Version': '0.1.0'
        }
    )
    return resp.status_code


def main():
    input_file = os.path.join(script_dir, "openmetrics_output.txt")
    if not os.path.exists(input_file):
        print("Run csv_to_openmetrics.py first to generate openmetrics_output.txt")
        sys.exit(1)

    print(f"Parsing {input_file}...")
    series = parse_openmetrics(input_file)
    print(f"Found {len(series)} series, {sum(len(v) for v in series.values())} total samples")
    print(f"Target: {REMOTE_WRITE_URL}")

    # Check connectivity
    try:
        r = requests.get(f"{PROMETHEUS_URL}/api/v1/status/buildinfo", timeout=5)
        if r.status_code != 200:
            print(f"Warning: Prometheus returned {r.status_code}")
    except requests.exceptions.ConnectionError:
        print(f"Error: Cannot connect to {PROMETHEUS_URL}")
        print("Make sure Prometheus is running with --web.enable-remote-write-receiver")
        sys.exit(1)

    # Send in batches
    batch = []
    sent = 0
    total = sum(len(v) for v in series.values())
    errors = 0

    for labels, samples in series.items():
        # Split samples into sub-batches to avoid huge requests
        for i in range(0, len(samples), BATCH_SIZE):
            chunk = samples[i:i + BATCH_SIZE]
            ts_encoded = encode_timeseries(list(labels), chunk)
            batch.append(ts_encoded)
            sent += len(chunk)

            if len(batch) >= 50:
                status = send_batch(batch)
                if status not in (200, 204):
                    errors += 1
                    if errors > 10:
                        print(f"\nToo many errors (last status: {status}). Aborting.")
                        print("Make sure --web.enable-remote-write-receiver is enabled.")
                        sys.exit(1)
                batch = []
                print(f"\r  Sent {sent}/{total} samples ({100*sent//total}%)", end='', flush=True)
                time.sleep(0.05)

    # Send remaining
    if batch:
        send_batch(batch)
        print(f"\r  Sent {sent}/{total} samples (100%)", end='', flush=True)

    print(f"\n\nDone! Imported {sent} samples with {errors} errors.")


if __name__ == "__main__":
    main()
