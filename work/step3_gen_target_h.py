"""Generate target.h for q6q-F956BXXS4DZG3 by combining ELF symbols + BTF parsing."""
from pathlib import Path
import subprocess
import struct
import re

WORK = Path("H:/Users/dsc/Downloads/port_f956b/work")
NM = Path("D:/Android/ndk/30.0.15729638/toolchains/llvm/prebuilt/windows-x86_64/bin/llvm-nm.exe")
BASE = 0xffffffc008000000

# 1. ELF symbols
nm_out = subprocess.run([str(NM), "--numeric-sort", str(WORK / "vmlinux.elf")],
    capture_output=True, text=True).stdout
sym_map = {}
for line in nm_out.splitlines():
    parts = line.split()
    if len(parts) >= 3:
        try:
            sym_map[parts[2]] = int(parts[0], 16)
        except ValueError:
            pass

def off(name):
    a = sym_map.get(name)
    if a is None:
        # try tail match
        for k, v in sym_map.items():
            if k == name or k.endswith(f".{name}") or k.endswith(f"_{name}"):
                return v - BASE
        return None
    return a - BASE

# 2. BTF parser for selinux_state.enforcing and miscdevice.fops offset
btf = (WORK / "vmlinux.btf").read_bytes()
hdr_fmt = "<HBBIIIII"
magic, ver, flags, hdr_len, type_off, type_len, str_off, str_len = \
    struct.unpack_from(hdr_fmt, btf, 0)
strtab = btf[hdr_len + str_off : hdr_len + str_off + str_len]
type_base = hdr_len + type_off

def get_str(off):
    if off >= len(strtab): return ""
    end = strtab.find(b"\x00", off)
    return strtab[off:end].decode(errors='replace') if end > 0 else ""

def kind_size(kind, vlen):
    base = 12
    if kind in (2, 7, 8, 9, 10, 11, 12): return base
    if kind in (1, 16): return base + 4
    if kind == 3: return base + 12
    if kind in (4, 5): return base + vlen * 12
    if kind == 6: return base + vlen * 8
    if kind == 13: return base + vlen * 8
    if kind == 14: return base + 4
    if kind == 15: return base + vlen * 12
    return base

def find_struct(name):
    pos = type_base
    tid = 0
    while pos + 12 <= btf[hdr_len + type_off + type_len:].__len__() + pos:
        if pos + 12 > hdr_len + type_off + type_len:
            break
        name_off, info, sz = struct.unpack_from("<III", btf, pos)
        kind = (info >> 24) & 0x1f
        vlen = info & 0xffff
        nm = get_str(name_off)
        if nm == name and kind == 4 and vlen > 0:
            return tid, sz, vlen, pos
        pos += kind_size(kind, vlen)
        tid += 1
    return None

# Find selinux_state and get enforcing offset
ss = find_struct("selinux_state")
selinux_enforcing_off = None
if ss:
    tid, sz, vlen, p = ss
    for m in range(vlen):
        m_pos = p + 12 + m * 12
        m_name_off, m_type, m_offs = struct.unpack_from("<III", btf, m_pos)
        m_name = get_str(m_name_off)
        if m_name == "enforcing":
            selinux_enforcing_off = m_offs >> 3  # byte offset
            print(f"  selinux_state.enforcing byte offset = 0x{selinux_enforcing_off:x}")

# Find miscdevice and get fops member offset
md = find_struct("miscdevice")
miscdevice_fops_off = None
if md:
    tid, sz, vlen, p = md
    for m in range(vlen):
        m_pos = p + 12 + m * 12
        m_name_off, m_type, m_offs = struct.unpack_from("<III", btf, m_pos)
        m_name = get_str(m_name_off)
        if m_name == "fops":
            miscdevice_fops_off = m_offs >> 3
            print(f"  miscdevice.fops byte offset = 0x{miscdevice_fops_off:x}")

# 3. Search 'nfnetlink_log' string in kernel
kernel = (WORK / "kernel").read_bytes()
nfnetlink_str = kernel.find(b"nfnetlink_log\x00")
sl = sym_map.get("selinux_state", 0)

# 4. compose target.h
TARGET = "q6q-F956BXXS4DZG3"
DISPLAY = "q6q-F956B-XX-S4-DZG3"

# Resolve all offsets
def sym_off(name):
    o = off(name)
    if o is None:
        print(f"  WARN: {name} not found")
        return 0
    return o

fields = {
    "CALL_USERMODEHELPER_EXEC_WORK_OFF":  sym_off("call_usermodehelper_exec_work"),
    "NOOP_LLSEEK_OFF":                     sym_off("noop_llseek"),
    "COPY_SPLICE_READ_OFF":                sym_off("generic_file_splice_read"),
    "CONFIGFS_READ_ITER_OFF":              sym_off("configfs_read_iter"),
    "CONFIGFS_BIN_WRITE_ITER_OFF":         sym_off("configfs_bin_write_iter"),
    "ASHMEM_IOCTL_OFF":                    sym_off("ashmem_ioctl"),
    "ASHMEM_COMPAT_IOCTL_OFF":             sym_off("compat_ashmem_ioctl"),
    "ASHMEM_MMAP_OFF":                     sym_off("ashmem_mmap"),
    "ASHMEM_OPEN_OFF":                     sym_off("ashmem_open"),
    "ASHMEM_RELEASE_OFF":                  sym_off("ashmem_release"),
    "ASHMEM_SHOW_FDINFO_OFF":              sym_off("ashmem_show_fdinfo"),
    "ANON_PIPE_BUF_OPS_OFF":               sym_off("anon_pipe_buf_ops"),
    "ASHMEM_FOPS_OFF":                     sym_off("ashmem_fops"),
    "KMALLOC_CACHES_OFF":                  sym_off("kmalloc_caches"),
    "SYSTEM_UNBOUND_WQ_OFF":               sym_off("system_unbound_wq"),
    "INIT_TASK_OFF":                       sym_off("init_task"),
    "ROOT_TASK_GROUP_OFF":                 sym_off("root_task_group"),
    "SLIDE_NFULNL_LOGGER_NAME_OFF":        nfnetlink_str,
    "SLIDE_NFULNL_LOGGER_OBJECT_OFF":      sym_off("nfulnl_logger"),
    "LOGGERS_ARRAY_OFF":                   sym_off("loggers"),
    "SLIDE_SYSCTL_BOOTID_OFF":             sym_off("sysctl_bootid"),
    "SLIDE_RANDOM_TABLE_BOOT_ID_DATA_PTR_OFF": sym_off("random_table"),
}

# Selinux enforcing = selinux_state + 0
if selinux_enforcing_off is not None and "selinux_state" in sym_map:
    fields["SELINUX_ENFORCING_OFF"] = sym_map["selinux_state"] - BASE + selinux_enforcing_off
else:
    fields["SELINUX_ENFORCING_OFF"] = 0

# ashmem_misc_fops = ashmem_miscs (single-entry array) + 0x10 (fops member offset)
if miscdevice_fops_off is not None and "ashmem_miscs" in sym_map:
    fields["ASHMEM_MISC_FOPS_OFF"] = sym_map["ashmem_miscs"] - BASE + miscdevice_fops_off
else:
    fields["ASHMEM_MISC_FOPS_OFF"] = 0

# P0 macros (placeholder - real P0 needs device probe)
P0_FINGERPRINT = 0  # will fill from p0_fingerprint.h

# Physical load addresses
P0_PHYS_OFFSET = 0x80000000
P0_KERNEL_PHYS_LOAD = 0x80000000

# Print all
print("\n=== Resolved offsets ===")
for k, v in fields.items():
    print(f"  {k:48s} = 0x{v:08x}")

# Write target.h
lines = [f"/* Auto-generated target.h for {TARGET}", ""]
lines.append(f"#ifndef TARGET_H_{TARGET.replace('-', '_')}")
lines.append(f"#define TARGET_H_{TARGET.replace('-', '_')}")
lines.append("")
lines.append(f"/* Display name */")
lines.append(f"#define TARGET_DISPLAY_NAME \"{DISPLAY}\"")
lines.append("")
lines.append(f"/* Physical load addresses */")
lines.append(f"#define P0_PHYS_OFFSET 0x{P0_PHYS_OFFSET:x}ULL")
lines.append(f"#define P0_KERNEL_PHYS_LOAD 0x{P0_KERNEL_PHYS_LOAD:x}ULL")
lines.append("")
lines.append(f"/* Symbol offsets from kernel base 0x{BASE:x} */")
for k, v in fields.items():
    lines.append(f"#define {k} 0x{v:x}ULL")
lines.append("")
lines.append(f"/* KMI (KernelSU) */")
lines.append(f'#define KMI_NAME "android14-6.1"')
lines.append(f'#define KMI_VERMAGIC "6.1.145-android14-11 SMP preempt mod_unload modversions aarch64"')
lines.append("")
lines.append(f"#endif /* TARGET_H_{TARGET.replace('-', '_')} */")
lines.append("")

target_h = "\n".join(lines)
(WORK / "target.h").write_text(target_h)
print(f"\ntarget.h written: {len(target_h)} bytes")
print(f"  SHA-256: {__import__('hashlib').sha256(target_h.encode()).hexdigest()}")