#!/usr/bin/env python3
"""
Convert historical CSV files to OpenMetrics format for Prometheus backfilling.

Usage:
  python3 csv_to_openmetrics.py
  promtool tsdb create-blocks-from openmetrics openmetrics_output.txt /path/to/prometheus/data

The output file can be imported into Prometheus using promtool.
"""

import csv
import glob
import os
from datetime import datetime
from zoneinfo import ZoneInfo

# Timezone for timestamps in CSV (same as config.cfg)
TZ = ZoneInfo("America/Sao_Paulo")

# Mapping: CSV column -> (metric_name, metric_type, label_name, label_value)
COLUMN_MAP = {
    "DC Voltage PV1(V)":                ("SolarVoltage_volts", "gauge", "Voltage", "PV1"),
    "DC Voltage PV2(V)":                ("SolarVoltage_volts", "gauge", "Voltage", "PV2"),
    "DC Current PV1(A)":                ("SolarCurrent_ampers", "gauge", "Current", "PV1"),
    "DC Current PV2(A)":                ("SolarCurrent_ampers", "gauge", "Current", "PV2"),
    "DC Power PV1(W)":                  ("SolarPower", "gauge", "Power", "PV1"),
    "DC Power PV2(W)":                  ("SolarPower", "gauge", "Power", "PV2"),
    "Total AC Output Power(W)":         ("OutputPower_watts", "gauge", "Power", "Active"),
    "AC Output Frequency R(Hz)":        ("OutputFreq", "gauge", "Grid", "Frequency"),
    "AC Voltage R/U/A(V)":              ("OutputVoltage_volts", "gauge", "Voltage", "L1"),
    "AC Current R/U/A(A)":              ("OutputCurrent_ampers", "gauge", "Current", "L1"),
    "Cumulative Production (Active)(kWh)": ("SolarProduction_watts_total", "counter", "Production", "Total"),
    "Daily Production (Active)(kWh)":   ("SolarProduction_watts_total", "counter", "Production", "Today"),
    "Generation Time Today(Min)":       ("SolarTime", "summary", "GenerationTime", "Today"),
    "Generation Time Total(Min)":       ("SolarTime", "summary", "GenerationTime", "Total"),
    "Single Plate Ambient Temperature(\u2103)": ("InverterTemp_celsius", "gauge", "Temp", "Ambient"),
    "Radiator Temperature 1(\u2103)":         ("InverterTemp_celsius", "gauge", "Temp", "Inner"),
    "Bus Voltage(V)":                   ("InverterVoltage_volts", "gauge", "Voltage", "Bus"),
}

def parse_timestamp(ts_str):
    """Parse CSV timestamp to unix epoch in milliseconds."""
    try:
        dt = datetime.strptime(ts_str.strip(), "%Y/%m/%d %H:%M:%S")
    except ValueError:
        try:
            dt = datetime.strptime(ts_str.strip(), "%Y-%m-%d %H:%M:%S")
        except ValueError:
            return None
    dt = dt.replace(tzinfo=TZ)
    return int(dt.timestamp() * 1000)

def parse_value(val):
    """Parse numeric value from CSV field."""
    try:
        return float(val)
    except (ValueError, TypeError):
        return None

def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    data_dir = os.path.join(script_dir, "historical_data")
    output_file = os.path.join(script_dir, "openmetrics_output.txt")

    csv_files = sorted(glob.glob(os.path.join(data_dir, "2*.csv")))
    if not csv_files:
        print("No CSV files found in historical_data/")
        return

    # Collect all samples grouped by metric series
    # series key: (metric_name, label_name, label_value)
    series_data = {}

    for csv_file in csv_files:
        print(f"Processing {os.path.basename(csv_file)}...")
        with open(csv_file, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                ts_str = row.get("Updated Time") or row.get("System Time")
                if not ts_str:
                    continue
                ts = parse_timestamp(ts_str)
                if ts is None:
                    continue

                for col, (mname, mtype, lname, lvalue) in COLUMN_MAP.items():
                    val = parse_value(row.get(col))
                    if val is None:
                        continue
                    key = (mname, mtype, lname, lvalue)
                    if key not in series_data:
                        series_data[key] = []
                    series_data[key].append((ts, val))

    # Sort all series by timestamp
    for key in series_data:
        series_data[key].sort(key=lambda x: x[0])

    # Write OpenMetrics format
    # Format: https://prometheus.io/docs/instrumenting/exposition_formats/#openmetrics-text-format
    with open(output_file, "w") as f:
        for (mname, mtype, lname, lvalue), samples in sorted(series_data.items()):
            om_type = "gauge" if mtype in ("gauge", "summary") else "counter"
            f.write(f"# TYPE {mname} {om_type}\n")
            for ts, val in samples:
                # OpenMetrics timestamps are in seconds (float)
                ts_sec = ts / 1000.0
                f.write(f'{mname}{{{lname}="{lvalue}"}} {val} {ts_sec:.3f}\n')
            f.write("\n")
        f.write("# EOF\n")

    total_samples = sum(len(v) for v in series_data.values())
    print(f"\nDone! Wrote {total_samples} samples to {output_file}")
    print(f"\nTo import into Prometheus:")
    print(f"  promtool tsdb create-blocks-from openmetrics openmetrics_output.txt /path/to/prometheus/data")

if __name__ == "__main__":
    main()
