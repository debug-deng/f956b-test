"""PORTING.md Section 3 — extract raw BTF and create analyzable ELF."""
from pathlib import Path
import struct
import hashlib
import subprocess

WORK = Path("H:/Users/dsc/Downloads/port_f956b/work")
kernel = (WORK / "kernel").read_bytes()
print(f"kernel size: {len(kernel):,}")
print(f"kernel SHA-256: {hashlib.sha256(kernel).hexdigest()}")

# Extract raw BTF: magic 0xEB9F little-endian = bytes 9f eb
prefix = b"\x9f\xeb\x01\x00"
candidates = []
cursor = 0
while True:
    start = kernel.find(prefix, cursor)
    if start < 0:
        break
    cursor = start + 1
    if start + 24 > len(kernel):
        continue
    header = struct.unpack_from("<HBBIIIII", kernel, start)
    magic, version, flags, header_len, type_off, type_len, str_off, str_len = header
    if magic != 0xEB9F or version != 1 or flags != 0 or header_len < 24:
        continue
    payload_len = max(type_off + type_len, str_off + str_len)
    end = start + header_len + payload_len
    string_start = start + header_len + str_off
    if end > len(kernel) or string_start >= end or kernel[string_start] != 0:
        continue
    candidates.append((start, end))

print(f"\nraw BTF candidates: {len(candidates)}")
for i, (s, e) in enumerate(candidates):
    print(f"  [{i}] [0x{s:x}, 0x{e:x}) {e-s:,} bytes")

if len(candidates) == 1:
    s, e = candidates[0]
    (WORK / "vmlinux.btf").write_bytes(kernel[s:e])
    print(f"\nvmlinux.btf written: {e-s:,} bytes")
    print(f"vmlinux.btf SHA-256: {hashlib.sha256(kernel[s:e]).hexdigest()}")
else:
    print(f"\nWARNING: expected exactly 1 raw BTF blob, got {len(candidates)}")
    # Pick the largest if multiple
    if candidates:
        s, e = max(candidates, key=lambda x: x[1] - x[0])
        (WORK / "vmlinux.btf").write_bytes(kernel[s:e])
        print(f"picked largest: {e-s:,} bytes")