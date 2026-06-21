#!/usr/bin/env python3
"""
Modbus Register Scanner for Sofar inverter via LSW-3/LSE datalogger.
Scans a range of registers and shows which ones return non-zero values.

Usage:
  python3 modbus_scan.py [start_addr] [end_addr]

Examples:
  python3 modbus_scan.py 0x0400 0x04FF
  python3 modbus_scan.py 0x0480 0x04BC
"""

import sys
import os
import socket
import binascii
import configparser
import time
import libscrc

script_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
os.chdir(script_dir)

# Read config
configParser = configparser.RawConfigParser()
configParser.read('./config.cfg')
inverter_ip = configParser.get('SofarInverter', 'inverter_ip')
inverter_port = int(configParser.get('SofarInverter', 'inverter_port'))
inverter_sn = int(configParser.get('SofarInverter', 'inverter_sn'))

# Parse args
if len(sys.argv) >= 3:
    scan_start = int(sys.argv[1], 0)
    scan_end = int(sys.argv[2], 0)
else:
    scan_start = 0x0400
    scan_end = 0x06FF

CHUNK_SIZE = 50  # registers per request

def twos_complement(hexval):
    bits = 16
    val = int(hexval, 16)
    if val >= 2**(bits-1):
        val -= 2**bits
    return val

def build_frame(sn, pini, count):
    start = binascii.unhexlify('A5')
    length = binascii.unhexlify('1700')
    controlcode = binascii.unhexlify('1045')
    serial = binascii.unhexlify('0000')
    datafield = binascii.unhexlify('020000000000000000000000000000')

    inverter_sn2 = bytearray.fromhex(
        hex(sn)[8:10] + hex(sn)[6:8] + hex(sn)[4:6] + hex(sn)[2:4]
    )

    pos_ini = str(hex(pini)[2:].zfill(4))
    pos_count = str(hex(count)[2:].zfill(4))
    businessfield = binascii.unhexlify('0103' + pos_ini + pos_count)
    crc_val = libscrc.modbus(businessfield)
    crc = binascii.unhexlify(hex(crc_val)[2:].zfill(4)[2:4] + hex(crc_val)[2:].zfill(4)[0:2])
    checksum = binascii.unhexlify('00')
    endCode = binascii.unhexlify('15')

    frame = bytearray(start + length + controlcode + serial + inverter_sn2 +
                      datafield + businessfield + crc + checksum + endCode)

    cs = 0
    for i in range(1, len(frame) - 2):
        cs += frame[i] & 255
    frame[len(frame) - 2] = int(cs & 255)

    return bytes(frame)

def scan_range(sock, sn, start, end):
    results = {}
    addr = start
    while addr <= end:
        count = min(CHUNK_SIZE, end - addr + 1)
        frame = build_frame(sn, addr, count)

        try:
            sock.sendall(frame)
            time.sleep(0.5)
            data = sock.recv(2048)
        except socket.timeout:
            print(f"  Timeout at 0x{addr:04X}-0x{addr+count-1:04X}")
            addr += count
            continue
        except Exception as e:
            print(f"  Error at 0x{addr:04X}: {e}")
            addr += count
            continue

        # Parse response - data starts at byte 56 (28*2), each register is 4 hex chars
        hex_data = ''.join(hex(x)[2:].zfill(2) for x in bytearray(data))

        for i in range(count):
            pos = 56 + (i * 4)
            if pos + 4 <= len(hex_data):
                raw_hex = hex_data[pos:pos+4]
                val = twos_complement(raw_hex)
                reg_addr = addr + i
                results[reg_addr] = (raw_hex, val)

        addr += count
        time.sleep(0.3)

    return results

# Connect
print(f"Connecting to {inverter_ip}:{inverter_port}...")
sock = None
for res in socket.getaddrinfo(inverter_ip, inverter_port, socket.AF_INET, socket.SOCK_STREAM):
    family, socktype, proto, _, sockaddr = res
    try:
        sock = socket.socket(family, socktype, proto)
        sock.settimeout(15)
        sock.connect(sockaddr)
        break
    except socket.error as e:
        print(f"Connection failed: {e}")
        sys.exit(1)

if not sock:
    print("Could not connect to inverter/logger")
    sys.exit(1)

print(f"Connected! Scanning 0x{scan_start:04X} - 0x{scan_end:04X}...\n")
print(f"{'Register':<12} {'Raw Hex':<10} {'Value (unsigned)':<18} {'Value (signed)':<15}")
print("-" * 60)

results = scan_range(sock, inverter_sn, scan_start, scan_end)
sock.close()

# Display results - only non-zero
found = 0
for addr in sorted(results.keys()):
    raw_hex, signed_val = results[addr]
    unsigned_val = int(raw_hex, 16)
    if unsigned_val != 0:
        found += 1
        print(f"0x{addr:04X}       {raw_hex:<10} {unsigned_val:<18} {signed_val:<15}")

print(f"\n{'='*60}")
print(f"Total registers scanned: {len(results)}")
print(f"Non-zero registers found: {found}")
