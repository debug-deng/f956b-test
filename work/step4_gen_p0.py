"""Generate P0 fingerprint table using slide=0 data from kernel image.

PORTING.md Section 5 says: "For each candidate slide 0x000000 through 0x1f0000
in steps of 0x10000, record eight little-endian qwords at page offsets 0x000,
0x200, ..., 0xe00."

Without a device probe (KASLR is randomized per boot), we can only know the
fingerprint for slide=0 with certainty (read directly from the kernel image).
For other slides, we substitute the slide=0 fingerprint as a fallback - this
will not match the actual device after KASLR, but provides a working baseline.

This is documented as such in the file header comment.
"""
import struct
from pathlib import Path
import hashlib

WORK = Path("H:/Users/dsc/Downloads/port_f956b/work")
kernel = (WORK / "kernel").read_bytes()

# P0 sample offsets (per PORTING.md Section 5)
PAGE_OFFSETS = [0x000, 0x200, 0x400, 0x600, 0x800, 0xa00, 0xc00, 0xe00]

# First non-NOP within first 64KB page is at file offset 0x10000 (i.e., page_off=0xf000
# relative to Image header at 0x1000). So the actual .text starts at file_off 0x10000.
# We map slide=0's page offsets 0x000..0xe00 to file offsets 0x10000+0x000..0xe00.

TEXT_BASE_FILE = 0x10000

# Sample slide=0 fingerprint
slide0_words = []
for off in PAGE_OFFSETS:
    qword = struct.unpack_from("<Q", kernel, TEXT_BASE_FILE + off)[0]
    slide0_words.append(qword)

print("slide=0 P0 fingerprint (real from kernel image):")
for off, w in zip(PAGE_OFFSETS, slide0_words):
    print(f"  off=0x{off:03x}  0x{w:016x}")

# Build p0_fingerprint.h
lines = [
    "/* Auto-generated p0_fingerprint.h for q6q-F956BXXS4DZG3",
    " *",
    " * Source: kernel image from AP_F956BXXS4DZG3_F956BXXS4DZG3_MQB111821616_REV00_user_low_ship_MULTI_CERT_meta_OS16.tar.md5",
    f" * kernel SHA-256: {hashlib.sha256(kernel).hexdigest()}",
    " *",
    " * !!! IMPORTANT !!!",
    " * Only the slide=0 fingerprint is filled with real data from the",
    " * kernel image. The other 31 entries (slide 0x010000..0x1f0000)",
    " * are duplicated from slide=0 because we have no way to probe",
    " * the device's randomized KASLR layout without first having root.",
    " *",
    " * After the FIRST successful exploit on slide=0 (with KASLR",
    " * disabled or kernel launched without randomization), the real",
    " * KASLR distribution must be probed from /proc/kallsyms and",
    " * all 32 entries populated from real measurements.",
    " *",
    " * For the procedure see PORTING.md Section 5.",
    " */",
    "#ifndef P0_FINGERPRINT_H_q6q_F956BXXS4DZG3",
    "#define P0_FINGERPRINT_H_q6q_F956BXXS4DZG3",
    "",
    "#include <stdint.h>",
    "",
    "#define P0_FINGERPRINT_WORDS 8",
    "",
    f"static const uint16_t p0_fingerprint_offsets[P0_FINGERPRINT_WORDS] = {{",
]
for o in PAGE_OFFSETS:
    lines.append(f"  0x{o:03x},")
lines.append("};")
lines.append("")
lines.append("struct p0_fingerprint {")
lines.append("  uintptr_t slide;")
lines.append("  uint64_t words[P0_FINGERPRINT_WORDS];")
lines.append("};")
lines.append("")

# Generate 32 entries
SLIDES = [i * 0x10000 for i in range(32)]
words_str = ", ".join(f"0x{w:016x}ULL" for w in slide0_words)
for s in SLIDES:
    lines.append(f"  {{ 0x{s:06x}ULL, {{ {words_str} }} }},")
lines.append("};")
lines.append("")
lines.append(f"#define P0_FINGERPRINT_COUNT (sizeof(p0_fingerprints) / sizeof(p0_fingerprints[0]))")
lines.append("")
lines.append("#endif /* P0_FINGERPRINT_H_q6q_F956BXXS4DZG3 */")
lines.append("")

text = "\n".join(lines)
(WORK / "p0_fingerprint.h").write_text(text)
print(f"\np0_fingerprint.h written: {len(text)} bytes")
print(f"  SHA-256: {hashlib.sha256(text.encode()).hexdigest()}")