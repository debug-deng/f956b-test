# Upstream PR Material for BuSung-dev/Root-My-Galaxy-Payloads

This directory contains files ready to be submitted as a PR to
`BuSung-dev/Root-My-Galaxy-Payloads` to add F956B (Galaxy Z Fold6) support.

## Files in this directory

| File | Maps to upstream path |
|---|---|
| `target.h` | `src/targets/q6q-F956BXXS4DZG3/target.h` |
| `p0_fingerprint.h` | `src/targets/q6q-F956BXXS4DZG3/p0_fingerprint.h` |
| `targets-v3.json` | `support/targets-v3.json` (merge with upstream) |
| `SM-F956B-F956BXXS4DZG3.md` | `docs/SM-F956B-F956BXXS4DZG3.md` |

## PR title

```
Add Galaxy Z Fold6 (SM-F956B / F956BXXS4DZG3) target
```

## PR body

```markdown
This PR adds support for the Galaxy Z Fold6 international (Thailand CSC)
running firmware F956BXXS4DZG3 on kernel 6.1.145-android14-11.

### Source firmware

| Field | Value |
|---|---|
| Package | `SM-F956B` |
| Build | `F956BXXS4DZG3` |
| Codename | `q6q` (Snapdragon 8 Gen 2 for Galaxy) |
| Kernel | `6.1.145-android14-11-33418572-abF956BXXS4DZG3` |
| KMI | `android14-6.1` |

### Artifacts

- `cve-2026-43499-app.so` 104,128 bytes, verified by GitHub Actions run
  #32159963336 (CI artifact SHA-256
  `b8fcafb80172994b79eb6269caa3dff3ba7909be48685a294340ffdb0b256626`).
- `ksud-q6q-F956BXXS4DZG3-kdp` is pending publication (Step 7 below).

### Differences from closest published target (e3q-S928USQS6DZF2)

The structural offsets are largely uniform across Android 14 6.1 platforms;
the F956B profile absorbs the q6q vs e3q delta without requiring a separate
template. The recovered `_OFF` macros match the e3q values where the kernel
versions overlap (6.1.145), with `kmalloc_caches` differing per the upstream
PORTING.md note.

### P0 fingerprint caveat

The `p0_fingerprint.h` shipped in this PR has 31 placeholder entries
duplicated from slide=0. The F956B device used to derive this profile was
unrooted at the time, so live KASLR sampling was not possible. Once root is
achieved on the F956B, a follow-up PR will replace the duplicated entries
with real per-slide measurements.
```

## Step-by-step submission procedure

1. **Fork** `BuSung-dev/Root-My-Galaxy-Payloads` on GitHub.
2. **Clone your fork** locally.
3. **Copy** the four files from this directory into the matching upstream
   paths (see table above). For `targets-v3.json`, append the F956B entry
   to the existing `payloads` array (do not overwrite other entries).
4. **Build the KSU module** in your fork's CI:
   - The upstream `kernelsu/` patch must be applied to KernelSU v3.2.5.
   - Use `ghcr.io/ylarod/ddk-min:android14-6.1-20260313`.
   - Build `android14-6.1_kernelsu-q6q-F956BXXS4DZG3-kdp.ko` and
     `ksud-q6q-F956BXXS4DZG3-kdp`.
   - Update the `size` field in `support/targets-v3.json` with the actual
     sizes.
5. **Commit** with a descriptive message.
6. **Push** to your fork.
7. **Open a PR** against `BuSung-dev/Root-My-Galaxy-Payloads:main` with the
   body above.
8. **Address review comments** — the maintainer may require ABL bootloader
   analysis or P0 live sampling before merging.

## What this PR deliberately does NOT include

- Real per-slide P0 measurements (require root; deferred to follow-up PR)
- ABL bootloader analysis (uniform across Android 14 6.1 per upstream
  assumption; can be added later if P0 sliding proves device-sensitive)
- KernelSU `.ko` / `ksud` binaries (requires Docker + DDK image; deferred
  to Step 7 above)

## Provenance evidence

The original firmware AP archive and SHA chain are documented in
`SM-F956B-F956BXXS4DZG3.md` (Stage 1, "Verified AP chain"). All hash values
in this directory can be re-verified against the corresponding files in the
parent `work/` directory of this repository.