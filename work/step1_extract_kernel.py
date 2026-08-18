"""Re-extract with correct ARM64 Image header layout.

Linux/Documentation/arm64/booting.rst layout at offset 0:
  u32 code0        (offset 0x00)
  u32 code1        (offset 0x04)
  u64 text_offset  (offset 0x08)
  u64 image_size   (offset 0x10)
  u64 flags        (offset 0x18)
  u64 res2         (offset 0x20)
  u64 res3         (offset 0x28)
  u64 res4         (offset 0x30)
  u32 magic        (offset 0x38)  = 0x644d5241 ("ARM\x64" LE)
  u32 res5         (offset 0x3c)
"""
from pathlib import Path
import struct
import hashlib

WORK = Path("H:/Users/dsc/Downloads/port_f956b/work")

boot = (WORK / "boot.img").read_bytes()
print(f"boot.img size: {len(boot):,}")

# Magic check at 0x38
magic = struct.unpack_from("<I", boot, 0x1000 + 0x38)[0]
print(f"ARM64 Image magic at 0x1038: 0x{magic:x} (expect 0x644d5241)")

if magic == 0x644d5241:
    text_offset = struct.unpack_from("<Q", boot, 0x1000 + 0x08)[0]
    image_size = struct.unpack_from("<Q", boot, 0x1000 + 0x10)[0]
    flags = struct.unpack_from("<Q", boot, 0x1000 + 0x18)[0]
    print(f"  text_offset: 0x{text_offset:x}")
    print(f"  image_size:  0x{image_size:x}")
    print(f"  flags:       0x{flags:x}")
    kernel = boot[0x1000:0x1000 + image_size]
else:
    print("ARM64 magic not found at expected offset; searching...")
    for off in [0, 0x1000, 0x2000]:
        m = struct.unpack_from("<I", boot, off + 0x38)[0] if off + 0x3c <= len(boot) else None
        if m == 0x644d5241:
            print(f"  found at offset 0x{off:x}")
            break
    kernel = boot[0x1000:]

(WORK / "kernel").write_bytes(kernel)
print(f"kernel extracted: {len(kernel):,} bytes")
print(f"kernel SHA-256: {hashlib.sha256(kernel).hexdigest()}")

# search for kallsyms markers in kernel
ks_markers = [b"kallsyms_addresses", b"kallsyms_num_syms", b"kallsyms_names",
              b"kallsyms_markers", b"kallsyms_token_table", b"kallsyms_token_index"]
print("\n=== kallsyms markers in kernel ===")
for m in ks_markers:
    p = kernel.find(m)
    if p >= 0:
        print(f"  {m.decode()}: 0x{p:x}")
    else:
        print(f"  {m.decode()}: not found")