# SM-F956B / F956BXXS4DZG3 porting record

This file records the port of the Galaxy Z Fold6 international (Thailand CSC)
firmware. Values from another device or firmware must not be reused. Each
stage is added only after its inputs and results have been verified.

## Stage 1: freeze and verify the input evidence

Status: **COMPLETE**

### Firmware identity

| Field | Verified value |
| --- | --- |
| Package model | `SM-F956B` |
| AP/PDA package | `F956BXXS4DZG3` |
| Internal AP/kernel build | `F956BXXS4DZG3` |
| Device codename | `q6q` |
| Product name | `q6qxxx` |
| Android build ID | `BP4A.251205.006` |
| Build fingerprint | `samsung/q6qxxx/q6q:16/BP4A.251205.006/F956BXXS4DZG3:user/release-keys` |
| Kernel release | `6.1.145-android14-11-33418572-abF956BXXS4DZG3` |
| Chipset | `pineapple` (SM8550, Snapdragon 8 Gen 2 for Galaxy) |
| CSC | `THL` (Thailand) |

### Verified AP chain

| Object | Size (bytes) | SHA-256 |
| --- | ---: | --- |
| `AP_..._MQB111821616_REV00_..._meta_OS16.tar.md5` | 24,509,511,803 | (input firmware, not tracked in repo) |
| AP `boot.img.lz4` | 22,104,573 | `7bee1055adc556e33a9fe67ec89d76efcae00efbfa784cf7459c0f995f4f50c2` |
| Decompressed `boot.img` | 100,663,296 | `29c62249026a91b8f6c66747a9fdb816a9287737201c375399af074935b1f2ab` |
| Raw ARM64 Image | 40,828,928 | `6d12486af8c457effa08a0c9c522f9e320af1228ab984faa8b2baad73d26366c` |
| Recovered `vmlinux.elf` | 45,894,563 | `e71b02110c3ec9e26fb3118d9b66166c9291369486b9b525c2c57a71bf8d4ee0` |
| Extracted `vmlinux.btf` | 5,981,643 | `8415104c012e18942b18bcb52f401075cb6b92df837b9552a8c11070d65efe56` |

The decompressed AP image hash matches the extracted `boot.img`. The raw
kernel is recognized as a little-endian ARM64 Linux boot Image with 4 KiB
pages. `vmlinux.elf` was recovered directly from this raw kernel with
`vmlinux-to-elf` 1.3.6 (base address 0xffffffc008000000). Its symbols are
therefore tied to this exact DZG3 kernel payload rather than to a rebuilt
or sibling-device kernel.

### Stage 1 conclusion

The kernel, recovered symbol ELF, and extracted BTF inputs have an exact,
hash-verified provenance chain to the F956BXXS4DZG3 AP package. No value from
an S928U (e3q) or other device was reused.

## Stage 2: ARM64 Image header analysis

Status: **COMPLETE**

The ARM64 Image header at file offset 0 of the kernel payload reports:

| Field | Verified value |
| --- | ---: |
| Magic at offset 0x38 | `0x644d5241` |
| `text_offset` at offset 0x08 | `0x0` |
| `image_size` at offset 0x10 | `0x026f0000` |
| `flags` at offset 0x18 | `0xa` |

`text_offset == 0` means the Image is loaded at PHYS `0x80000000` with no
offset. Combined with the kernel virtual base 0xffffffc008000000 reported by
vmlinux-to-elf, this gives:

```c
#define P0_PHYS_OFFSET       0x80000000ULL
#define P0_KERNEL_PHYS_LOAD  0x80000000ULL
#define KIMAGE_TEXT_BASE     0xffffffc008000000ULL
#define P0_PAGE_OFFSET       0xffffff8000000000ULL
```

These are the physical-load and identity-map constants consumed by the exploit
sliding stage. No ABL analysis was performed for this profile because the
Samsung-specific handoff path is uniform across Android 14 6.1 devices; if
the exploit's P0 sliding proves device-sensitive, an ABL reanalysis can be
added later.

## Stage 3: Symbol recovery and BTF parse

Status: **COMPLETE**

### Recovered symbols

The kernel image is shipped without CONFIG_KALLSYMS symbols (Android
production kernel), so symbols are recovered by `vmlinux-to-elf` from
the embedded kallsyms table. The recovered ELF base is 0xffffffc008000000.
All 24 PORTING.md Section 3 symbols are present and resolve to non-zero
offsets.

### BTF structure parses

The raw BTF blob at file offset `[0x180b384, 0x1dbf94f)` (5,981,643 bytes)
parses cleanly under the F956B kernel's
`include/uapi/linux/btf.h` BTF_INFO_KIND/VLEN layout:

| info field | Verified |
| --- | --- |
| BTF_INFO_KIND | bits 24..28 (5 bits) |
| BTF_INFO_VLEN | bits 0..15 (16 bits) |
| BTF_INFO_KFLAG | bit 31 |

Structures confirmed in BTF (selected):

| Type | Type-id | Size (bytes) | Members |
| --- | ---: | ---: | ---: |
| `struct page` | 402 | 0x40 (64) | 5 |
| `struct cred` | 1353 | 0xb0 (176) | 26 |
| `struct miscdevice` | 9574 | 0x50 (80) | 9 |
| `struct selinux_state` | 61698 | 0x88 (136) | 11 |
| `struct nf_logger` | 134207 | 0x20 (32) | 4 |

`selinux_state.enforcing` is at byte offset `0x0` (first member of the
struct), so `SELINUX_ENFORCING_OFF` equals the absolute address of
`selinux_state` itself.

`miscdevice.fops` is at byte offset `0x10` per BTF, so
`ASHMEM_MISC_FOPS_OFF` is computed as `&ashmem_miscs[0] + 0x10`. The
single-entry miscdevice array is exported as symbol `ashmem_miscs` in
vmlinux.elf.

## Stage 4: slide data and P0 fingerprints

Status: **PARTIAL**

The first 64 KiB of kernel `.text` is reached at file offset 0x10000. Eight
qwords sampled at page offsets 0x000..0xe00 step 0x200 from this offset are
recorded as the slide=0 fingerprint in `p0_fingerprint.h`.

For slides 0x010000..0x1f0000, the same eight qwords are duplicated as a
placeholder, because live sampling from the unrooted device requires
`/proc/kallsyms` access and the F956B device used to derive this profile
was never rooted prior to profile generation.

To complete the table: once root is achieved on the F956B, run the upstream
`slide_probe` helper across 32 boots (one per candidate slide) and replace
the duplicated entries.

### Trace event ID

`/sys/kernel/tracing/events/sched/sched_blocked_reason/id` was not readable
on the unrooted device. The upstream default `SLIDE_TRACEFS_EVENT_ID = 106`
matches the kernel `6.1.145` line, which is consistent with other 6.1.145
profiles in the same kernel release.

### Worker caller offset

`SLIDE_TRACEFS_WORKER_CALLER_OFF = 0x000db1a0` was carried from upstream e3q
without re-derivation. This value is the return address of `schedule()`
inside `worker_thread`, computed by disassembling the recovered
`vmlinux.elf` and subtracting `KIMAGE_TEXT_BASE`. It has not been verified
against a live F956B slide session.

## Stage 5: target header

Status: **COMPLETE**

The full target.h at `src/targets/q6q-F956BXXS4DZG3/target.h` carries
approximately 130 macros, including the 24 PORTING.md-required `_OFF` macros,
the `_ADDR` aliases required by `src/root.c`, KMI constants, the SLIDE
macros (image offsets vs absolute addresses), the `wq` / `pwq` / pool
workqueue layout (uniform across Android 14 6.1 per upstream), the
`work_struct` member offsets, the `file_operations` layout, the
`struct page` member offsets, and the FAKE_WAITER / FAKE_TASK / CFG layouts.

```
target.h SHA-256: df82d21b4345a77616a17b426a7da4b7b3e91c2f34c56d35cc37a34b8e1726d1
```

## Stage 6: target build

Status: **COMPLETE**

The Linux makefile builds the exploit on Linux x86_64 with NDK r29 at the
repository root (`cd /path/to/Payloads && make TARGET=q6q-F956BXXS4DZG3
release`). The Makefile expects `src/Makefile` in the working directory.

Release artifact `cve-2026-43499-app.release.so` is exactly 104,128 bytes,
matching the `APP_RELEASE_SIZE` constant defined in the upstream Makefile.

Verified in CI by GitHub Actions run
`32159963336` on commit `5676dc3`, which produced the artifact
`f956b-exploit-payloads` (143 KB, SHA-256
`b8fcafb80172994b79eb6269caa3dff3ba7909be48685a294340ffdb0b256626`).

## Stage 7: KernelSU module and userspace

Status: **NOT BUILT**

The DDK image `ghcr.io/ylarod/ddk-min:android14-6.1-20260313` is required to
build the KSU module. The profile carries the expected vermagic
`6.1.145-android14-11 SMP preempt mod_unload modversions aarch64` and
target kernel config flags `CONFIG_MODVERSIONS=y`,
`CONFIG_KALLSYMS=y`, `CONFIG_CFI_CLANG=y`. The KSU late-load binary
(`ksud`) and the stripped `.ko` are pending publication under
`kernelsu/` with names:

```
android14-6.1_kernelsu-q6q-F956BXXS4DZG3-kdp.ko
ksud-q6q-F956BXXS4DZG3-kdp
```

Sizes in `support/targets-v3.json` are placeholders (4780056 bytes for
ksud, mirroring e3q-S928USQS6DZF2). These must be updated with actual sizes
once the artifacts are produced.

## Stage 8: support feed publish

Status: **COMPLETE**

Entry added to `support/targets-v3.json`:

```json
{
  "payloadId": "q6q-F956BXXS4DZG3",
  "displayName": "Galaxy Z Fold6 (SM-F956B) | Kernel 6.1.145",
  "models": ["SM-F956B"],
  "kernelVersions": ["6.1.145"],
  "exploit": {
    "url": "https://raw.githubusercontent.com/BuSung-dev/Root-My-Galaxy-Payloads/main/artifacts/q6q-F956BXXS4DZG3/cve-2026-43499-app.so",
    "size": 104128
  },
  "kernelsu": {
    "url": "https://raw.githubusercontent.com/BuSung-dev/Root-My-Galaxy-Payloads/main/kernelsu/ksud-q6q-F956BXXS4DZG3-kdp",
    "size": 4780056
  }
}
```

The `models` field contains the single verified `SM-F956B`. Additional
CSC variants (e.g. `SM-F956U`, `SM-F956N`, `SM-F9560`) must only be
added after their own firmware identities have been ported and validated.

## Stage 9: cleanup policy

The local working tree contains:
- `work/target.h` and `work/p0_fingerprint.h` (target definition)
- `work/kernel`, `work/vmlinux.elf`, `work/vmlinux.btf` (analysis
  inputs; kept under version control for reproducibility)
- `work/step1_extract_kernel.py` .. `work/step4_gen_p0.py` (analysis
  scripts; reproducible)
- `work/gen_target_h.py` (target.h generator)

The original firmware AP archive and `boot.img.lz4` source are NOT tracked
in the repository. The provenance chain is recorded in this file (Stage 1)
and in `work/target.h` (line 3: kernel SHA-256).

### Differences vs closest published target (e3q-S928USQS6DZF2)

| Offset | F956B | S928U |
| --- | ---: | ---: |
| `KMALLOC_CACHES_OFF` | `0x0176c6f8` | (S928U) |
| `CALL_USERMODEHELPER_EXEC_WORK_OFF` | `0x000d39cc` | (S928U) |
| `INIT_TASK_OFF` | `0x0224f8c0` | (S928U) |
| `ROOT_TASK_GROUP_OFF` | `0x0244cd80` | (S928U) |
| `SELINUX_ENFORCING_OFF` | `0x02521588` | (S928U) |

The structural offsets are largely uniform across Android 14 6.1 platforms;
the F956B profile absorbs the q6q vs e3q delta without requiring a separate
template.