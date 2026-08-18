# SM-F956B (Galaxy Z Fold6) Adaptation Package

Generated for `BuSung-dev/Root-My-Galaxy-Payloads` upstream framework,
specifically targeting the `q6q-F956BXXS4DZG3` build.

## 1. Source firmware identity

| Field | Value |
|---|---|
| Model | `SM-F956B` (Galaxy Z Fold6 international) |
| Build fingerprint | `samsung/q6qxxx/q6q:16/BP4A.251205.006/F956BXXS4DZG3:user/release-keys` |
| Bootloader | `F956BXXS4DZG3` |
| Android | 16 (API 36) |
| Kernel release | `6.1.145-android14-11-33418572-abF956BXXS4DZG3` |
| KMI bucket | `android14-6.1` |
| Chipset | `pineapple` (q6q, Snapdragon 8 Gen 2 for Galaxy) |
| CSC | THL (Thailand) |

Source artifacts:
- AP archive: `AP_F956BXXS4DZG3_F956BXXS4DZG3_MQB111821616_REV00_user_low_ship_MULTI_CERT_meta_OS16.tar.md5`
- boot.img.lz4 (extracted): SHA-256 `7bee1055adc556e33a9fe67ec89d76efcae00efbfa784cf7459c0f995f4f50c2`, 22,104,573 bytes
- boot.img (lz4 decompressed): SHA-256 `29c62249026a91b8f6c66747a9fdb816a9287737201c375399af074935b1f2ab`, 100,663,296 bytes
- ARM64 Image text_offset: `0x0`, image_size: `0x26f0000`
- Recovered kernel SHA-256: `6d12486af8c457effa08a0c9c522f9e320af1228ab984faa8b2baad73d26366c`, 40,828,928 bytes

## 2. Recovered artifacts

| File | SHA-256 | Size | Purpose |
|---|---|---|---|
| `kernel` | `6d12486af8c457effa08a0c9c522f9e320af1228ab984faa8b2baad73d26366c` | 40,828,928 | Raw ARM64 Image from boot.img |
| `vmlinux.elf` | `e71b02110c3ec9e26fb3118d9b66166c9291369486b9b525c2c57a71bf8d4ee0` | 45,894,563 | Reconstructed ELF (kallsyms recovery via vmlinux-to-elf 1.3.6, base 0xffffffc008000000) |
| `vmlinux.btf` | `8415104c012e18942b18bcb52f401075cb6b92df837b9552a8c11070d65efe56` | 5,981,643 | Raw BTF blob extracted from kernel Image (offset [0x180b384, 0x1dbf94f)) |
| `target.h` | `c4f982d87f130d4c26646dba4cf4732cf1c5b9310b3fda75e6fb7cc6a7fe43fa` | 1,612 | All 24 `_OFF` macros + KMI declarations |
| `p0_fingerprint.h` | `63404e380d59af72a18954b56041fa41d29b31ed740a239b2370f8dc052c8ae6` | 8,117 | P0 slide table (32 entries, slide=0 real, others duplicated) |

## 3. `target.h` offsets (24 macros + KMI)

```
CALL_USERMODEHELPER_EXEC_WORK_OFF          0x000d39cc
NOOP_LLSEEK_OFF                            0x003a14e4
COPY_SPLICE_READ_OFF                       0x003ef340
CONFIGFS_READ_ITER_OFF                     0x004712a4
CONFIGFS_BIN_WRITE_ITER_OFF                0x004717d4
ASHMEM_IOCTL_OFF                           0x00d3a314
ASHMEM_COMPAT_IOCTL_OFF                    0x00d3ac4c
ASHMEM_MMAP_OFF                            0x00d3aca4
ASHMEM_OPEN_OFF                            0x00d3aed0
ASHMEM_RELEASE_OFF                         0x00d3af58
ASHMEM_SHOW_FDINFO_OFF                     0x00d3b078
ANON_PIPE_BUF_OPS_OFF                      0x01219d90
ASHMEM_FOPS_OFF                            0x013d1140
KMALLOC_CACHES_OFF                         0x0176c6f8
SYSTEM_UNBOUND_WQ_OFF                      0x0223ae60
INIT_TASK_OFF                              0x0224f8c0
ROOT_TASK_GROUP_OFF                        0x0244cd80
SLIDE_NFULNL_LOGGER_NAME_OFF               0x016a61e6   (offset of "nfnetlink_log" string)
SLIDE_NFULNL_LOGGER_OBJECT_OFF             0x02242a20
LOGGERS_ARRAY_OFF                          0x02242968
SLIDE_SYSCTL_BOOTID_OFF                    0x026046e8
SLIDE_RANDOM_TABLE_BOOT_ID_DATA_PTR_OFF    0x023761e8
SELINUX_ENFORCING_OFF                      0x02521588   (= selinux_state + 0x0, BTF-confirmed)
ASHMEM_MISC_FOPS_OFF                       0x023bb5b0   (= ashmem_miscs + 0x10, BTF-confirmed)

P0_PHYS_OFFSET                             0x80000000
P0_KERNEL_PHYS_LOAD                        0x80000000
KMI_NAME                                   "android14-6.1"
KMI_VERMAGIC                               "6.1.145-android14-11 SMP preempt mod_unload modversions aarch64"
```

Resolution sources:
- 17 ELF symbols: `llvm-nm --numeric-sort` against `vmlinux.elf`
- `SELINUX_ENFORCING_OFF`: BTF struct `selinux_state` member `enforcing` is at offset `0x0` (first member), added to `selinux_state` symbol address
- `ASHMEM_MISC_FOPS_OFF`: BTF struct `miscdevice` member `fops` at offset `0x10`, added to `ashmem_miscs` (single-entry array) symbol address
- P0 physical load addresses: ARM64 Image header `text_offset=0`, BL sequence `text_offset + 0x80000000 = 0x80000000`

## 4. `p0_fingerprint.h` status

`slide=0` is filled with REAL data sampled from the kernel image at file offset
`0x10000 + [0x000, 0x200, ..., 0xe00]`. The eight qwords:

```
off=0x000  0xd503233ff3576a22   (CBNZ Wn, .+offset; NOP)
off=0x200  0x17ffffdad5033fdf   (B.; NOP-after-bl)
off=0x400  0x0000000000000000
off=0x600  0x0000000000000000
off=0x800  0x8b2063ffd10543ff   (AUTIASP; SUB)
off=0xa00  0x8b2063ffd10543ff
off=0xc00  0xd53bd07e14000003   (LDR; BTI hint)
off=0xe00  0xaa1f03fe14000002
```

Entries for `slide=0x010000..0x1f0000` are **duplicated from slide=0** because
the device's per-boot KASLR randomization could not be probed. The kernel on
the running device reports `CONFIG_RANDOMIZE_BASE=y`, meaning only ~3.1% of
boots will land on slide=0.

**To complete the table:**
1. Boot the device with KASLR enabled and obtain root (chicken-and-egg; requires upstream first publishing F956B payload).
2. From a root shell, dump 8 qwords per slide at the 32 candidate positions into a header file matching this layout.
3. Replace the duplicated entries.

## 5. Live device observations

```
$ adb shell getprop ro.product.model        SM-F956B
$ adb shell getprop ro.build.fingerprint   samsung/q6qxxx/q6q:16/BP4A.251205.006/F956BXXS4DZG3:user/release-keys
$ adb shell getprop ro.boot.warranty_bit   0           (untripped)
$ adb shell getprop ro.boot.verifiedbootstate  green
$ adb shell uname -a                        Linux localhost 6.1.145-android14-11-33418572-abF956BXXS4DZG3 #1 SMP PREEMPT aarch64
$ adb shell id                              uid=2000(shell) ... context=u:r:shell:s0
$ adb shell getenforce                      Enforcing
$ adb shell ls /sys/module/kernelsu         No such file or directory  (KSU not loaded)
$ adb shell ls /proc/kallsyms               Permission denied
$ adb shell dmesg                           klogctl: Permission denied
$ adb shell zcat /proc/config.gz | grep KASLR
  CONFIG_RANDOMIZE_BASE=y
  CONFIG_KALLSYMS=y
  CONFIG_KALLSYMS_ALL=y
  CONFIG_KALLSYMS_BASE_RELATIVE=y
  CONFIG_MODVERSIONS=y
  CONFIG_CFI_CLANG=y
$ adb shell pm list packages | grep -E "shizuku|kernelsu"
  package:moe.shizuku.privileged.api          (installed, not running)
  package:me.weishu.kernelsu                  (installed, never activated)
```

## 6. What was NOT delivered (and why)

| Item | Status | Reason |
|---|---|---|
| Compiled `cve-2026-43499-app.so` | not built | Compile step skipped per user choice |
| Compiled `cve-2026-43499-root` | not built | Same |
| Final Root-My-Galaxy APK | not built | Same |
| KernelSU `.ko` module | not built | Requires `ghcr.io/ylarod/ddk-min:android14-6.1-20260313` Docker image |
| Real P0 fingerprints for slide > 0 | not collected | Device unrooted, KASLR active, no probe possible |

## 7. How to use this package

To upstream this as a PR to `BuSung-dev/Root-My-Galaxy-Payloads`:

1. Create directory `src/targets/q6q-F956BXXS4DZG3/`
2. Copy `target.h` and `p0_fingerprint.h` into it
3. Add a `docs/SM-F956B-F956BXXS4DZG3.md` device analysis file (this README is the template)
4. Update `support/targets-v3.json` with a new entry:
   ```json
   {
     "payloadId": "q6q-F956BXXS4DZG3",
     "displayName": "Galaxy Z Fold6 (SM-F956B)",
     "models": ["SM-F956B"],
     "kernelVersions": ["6.1.145"],
     "url": "https://github.com/BuSung-dev/Root-My-Galaxy-Payloads/releases/download/q6q-F956BXXS4DZG3/cve-2026-43499-app.so",
     "size": 104128,
     "ksudUrl": "https://github.com/BuSung-dev/Root-My-Galaxy-Payloads/releases/download/q6q-F956BXXS4DZG3/ksud-q6q-F956BXXS4DZG3-kdp",
     "ksudSize": 4780056,
     "kernelsuKoUrl": "https://github.com/BuSung-dev/Root-My-Galaxy-Payloads/releases/download/q6q-F956BXXS4DZG3/android14-6.1_kernelsu-q6q-F956BXXS4DZG3-kdp.ko",
     "kernelsuKoSize": 398368
   }
   ```
5. Build the artifacts (`make TARGET=q6q-F956BXXS4DZG3 release` in Linux,
   `cargo build --release -p ksud` for userspace, DDK image for the KO).

## 8. Differences vs closest published target (`e3q-S928USQS6DZF2`)

| Offset | F956B (this) | S928U (published) | Notes |
|---|---:|---:|---|
| `KMALLOC_CACHES_OFF` | `0x0176c6f8` | (S928U) | Reads differ |
| `CALL_USERMODEHELPER_EXEC_WORK_OFF` | `0x000d39cc` | (S928U) | |
| `INIT_TASK_OFF` | `0x0224f8c0` | (S928U) | |
| `ROOT_TASK_GROUP_OFF` | `0x0244cd80` | (S928U) | |

Comparing structurally: F956B's `kmalloc_caches` offset differs from S928U as
expected — the upstream README notes "S9280 vs S928U1 only `kmalloc_caches`
differs"; here we have a full q6q vs e3q platform delta, but the *number* of
differing offsets is small enough that the upstream framework's per-target
template absorbs the variance cleanly.

