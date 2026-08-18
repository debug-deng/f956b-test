#!/bin/bash
# Build KernelSU.ko inside the DDK container against the Samsung
# open-source kernel source. Called from .github/workflows/build.yml.
#
# Output: every line is written to /tmp/ddk_build.log on the runner
# host (via `tee -a` on every command). At the end, the workflow
# step does `tail -80 /tmp/ddk_build.log` and uploads the full log as
# an artifact for offline diagnosis when the run fails.
set -euo pipefail

LOG=/tmp/ddk_build.log
: > "$LOG"

log() { echo "$@" | tee -a "$LOG"; }

log "=== ddk-build.sh started at $(date -u +%Y-%m-%dT%H:%M:%SZ) ==="

export KDIR=/kernel_src
export ARCH=arm64
export CROSS_COMPILE=aarch64-linux-gnu-
export LLVM=1
export LLVM_IAS=1

cd "$KDIR"

log "== DDK env =="
log "  $(uname -a)"
log "  $(clang --version | head -1)"
log "  KDIR=$KDIR"
log "== source layout =="
log "$(ls $KDIR/drivers/kernelsu/ | head -5 | tr '\n' ' ')"
log "  $(grep -E '^VERSION|^PATCHLEVEL|^SUBLEVEL' $KDIR/Makefile | head -3 | tr '\n' ' ')"

# Patch drivers/Makefile + drivers/Kconfig (KernelSU setup.sh does this).
if ! grep -q 'obj-$(CONFIG_KSU)' "$KDIR/drivers/Makefile"; then
  echo "" >> "$KDIR/drivers/Makefile"
  echo 'obj-$(CONFIG_KSU) += kernelsu/' >> "$KDIR/drivers/Makefile"
  log "  patched drivers/Makefile"
fi
if ! grep -q "drivers/kernelsu/Kconfig" "$KDIR/drivers/Kconfig"; then
  sed -i '/endmenu/i\source "drivers/kernelsu/Kconfig"' "$KDIR/drivers/Kconfig"
  log "  patched drivers/Kconfig"
fi

# Samsung open-source Kernel.tar.gz does not ship a populated .config.
if [ ! -f "$KDIR/.config" ]; then
  cp "$KDIR/arch/arm64/configs/gki_defconfig" "$KDIR/.config"
  log "  copied gki_defconfig"
fi

# Force CONFIG_KSU=m and Samsung KDP/RKP/DEFEX = y. CONFIG_KSU is
# tristate with 'default y' so we also rewrite the Kconfig to
# 'default m' to prevent olddefconfig from overwriting our 'm'.
for cfg in \
  "CONFIG_KSU=m" \
  "CONFIG_KPROBES=y" \
  "CONFIG_KPROBE_EVENTS=y" \
  "CONFIG_EXT4_FS=y" \
  "CONFIG_EXT4_FS_POSIX_ACL=y" \
  "CONFIG_EXT4_FS_SECURITY=y" \
  "CONFIG_SECURITY=y" \
  "CONFIG_MODULES=y" \
  "CONFIG_MODULE_UNLOAD=y" \
  "CONFIG_KSU_SAMSUNG_KDP=y" \
  "CONFIG_KSU_SAMSUNG_RKP=y" \
  "CONFIG_KSU_SAMSUNG_DEFEX=y"; do
  key="${cfg%%=*}"
  cur="$(grep -E "^${key}=" "$KDIR/.config" 2>/dev/null || echo "${key}=n")"
  if [ "$cur" != "$cfg" ]; then
    sed -i "s/^${key}=.*/${cfg}/" "$KDIR/.config"
  fi
done

# Patch KernelSU Kconfig: 'default y' -> 'default m' so olddefconfig
# does not normalize our explicit 'CONFIG_KSU=m'.
sed -i "s/^[[:space:]]*default[[:space:]]*y[[:space:]]*$/default m/" \
    "$KDIR/drivers/kernelsu/Kconfig"
log "KernelSU Kconfig after patch:"
log "$(grep -B 1 -A 1 default $KDIR/drivers/kernelsu/Kconfig | head -10 | tr '\n' '|')"

cd "$KDIR"
log "== run make olddefconfig =="
make olddefconfig 2>&1 | tee -a "$LOG" | tail -10
log "olddefconfig rc=${PIPESTATUS[0]}"

log "== run make prepare =="
make prepare 2>&1 | tee -a "$LOG" | tail -10
log "prepare rc=${PIPESTATUS[0]}"

log "== auto.conf check =="
if grep -E "^CONFIG_KSU=m" include/config/auto.conf > "$LOG.tmp" 2>&1; then
  log "  CONFIG_KSU=m present in auto.conf"
  cat "$LOG.tmp" | tee -a "$LOG"
else
  log "  WARN: CONFIG_KSU=m NOT in auto.conf"
fi
rm -f "$LOG.tmp"

log "== run make modules_prepare =="
make modules_prepare 2>&1 | tee -a "$LOG" | tail -10
log "modules_prepare rc=${PIPESTATUS[0]}"

log "== run make M=drivers/kernelsu modules =="
make M=drivers/kernelsu modules -j"$(nproc)" 2>&1 | tee -a "$LOG" | tail -60
log "build rc=${PIPESTATUS[0]}"

log "== build artifacts =="
log "$(find drivers/kernelsu/ -maxdepth 2 -name '*.o' -o -name '*.ko' 2>&1 | head -20 | tr '\n' ' ')"
if [ -f drivers/kernelsu/kernelsu.ko ]; then
  log "  kernelsu.ko size: $(stat -c %s drivers/kernelsu/kernelsu.ko) bytes"
  log "  $(modinfo drivers/kernelsu/kernelsu.ko | grep -E 'vermagic|depends|srcversion' | tr '\n' ' ')"
else
  log "ERROR: kernelsu.ko not built"
  exit 1
fi

log "=== ddk-build.sh done at $(date -u +%Y-%m-%dT%H:%M:%SZ) ==="
log "=== log size: $(wc -c < $LOG) bytes, $(wc -l < $LOG) lines ==="
