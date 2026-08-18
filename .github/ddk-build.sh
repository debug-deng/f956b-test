#!/bin/bash
# Build KernelSU.ko inside the DDK container against the Samsung
# open-source kernel source. Called from .github/workflows/build.yml.
set -euo pipefail

export KDIR=/kernel_src
export ARCH=arm64
export CROSS_COMPILE=aarch64-linux-gnu-
export LLVM=1
export LLVM_IAS=1

cd "$KDIR"

echo "== DDK env =="
uname -a
clang --version | head -1
echo "KDIR=$KDIR"
echo "== source layout =="
ls "$KDIR/drivers/kernelsu/" 2>&1 | head -5
grep -E "^VERSION|^PATCHLEVEL|^SUBLEVEL" "$KDIR/Makefile" | head -3

# Patch drivers/Makefile + drivers/Kconfig (KernelSU setup.sh does this).
if ! grep -q 'obj-$(CONFIG_KSU)' "$KDIR/drivers/Makefile"; then
  echo "" >> "$KDIR/drivers/Makefile"
  echo 'obj-$(CONFIG_KSU) += kernelsu/' >> "$KDIR/drivers/Makefile"
  echo "  patched drivers/Makefile"
fi
if ! grep -q "drivers/kernelsu/Kconfig" "$KDIR/drivers/Kconfig"; then
  sed -i '/endmenu/i\source "drivers/kernelsu/Kconfig"' "$KDIR/drivers/Kconfig"
  echo "  patched drivers/Kconfig"
fi

# Samsung open-source Kernel.tar.gz does not ship a populated .config.
if [ ! -f "$KDIR/.config" ]; then
  cp "$KDIR/arch/arm64/configs/gki_defconfig" "$KDIR/.config"
  echo "  copied gki_defconfig"
fi

# Force CONFIG_KSU=m and Samsung KDP/RKP/DEFEX = y. CONFIG_KSU's
# 'default y' in the Kconfig means olddefconfig would normalize 'm' to
# 'y'; we set 'm' anyway and also override KSU's default in its
# Kconfig file so the obj-$(CONFIG_KSU) += kernelsu/ entry produces a
# loadable .ko rather than a built-in object.
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
# Patch KernelSU Kconfig to default to m so olddefconfig does not
# override our explicit 'm'. The relevant lines are:
#   config KSU
#       tristate "KernelSU function support"
#       ...
#       default y
# Replace 'default y' with 'default m'. Use a more permissive regex.
sed -i "s/^[[:space:]]*default[[:space:]]*y[[:space:]]*$/default m/" \
    "$KDIR/drivers/kernelsu/Kconfig" 2>&1 | head
# Verify
echo "KernelSU Kconfig after patch:"
grep -B 1 -A 1 "default" "$KDIR/drivers/kernelsu/Kconfig" | head -10

cd "$KDIR"
make olddefconfig > /tmp/m1.log 2>&1; echo "olddefconfig rc=$?"
make prepare     > /tmp/m2.log 2>&1; echo "prepare rc=$?"
grep -E "^CONFIG_KSU\b" include/config/auto.conf \
  && echo "  auto.conf has KSU" \
  || echo "WARN: auto.conf missing CONFIG_KSU"
make modules_prepare > /tmp/m3.log 2>&1; echo "modules_prepare rc=$?"

cd "$KDIR"
make M=drivers/kernelsu modules -j"$(nproc)" > /tmp/m4.log 2>&1; echo "build rc=$?"
echo "tail of make log:"
tail -60 /tmp/m4.log
echo "errors:"
grep -iE "error:|undefined" /tmp/m4.log | head -10 || echo "  none"
echo "warnings:"
grep -iE "warning:" /tmp/m4.log | head -10 || echo "  none"

echo "== build artifacts =="
find drivers/kernelsu/ -maxdepth 2 -name "*.o" -o -name "*.ko" 2>&1 | head -20
ls -la drivers/kernelsu/kernelsu.ko 2>&1 || echo "ERROR: kernelsu.ko not built"
if [ -f drivers/kernelsu/kernelsu.ko ]; then
  modinfo drivers/kernelsu/kernelsu.ko 2>&1 | grep -E "vermagic|depends" || true
fi
