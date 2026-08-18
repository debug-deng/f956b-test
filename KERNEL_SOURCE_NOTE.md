# Manual procedure: providing Kernel.tar.gz + Platform.tar.gz to CI

The F956B KSU build needs the matching Samsung open-source kernel archive
that the firmware was built from. The upstream build pipeline assumes this
is on the build host, but our CI runner does not have it.

## Option A — Upload to a GitHub release (recommended)

1. Create a release on https://github.com/debug-deng/f956b-test/releases/new
2. Tag: `v1` (or any tag — update `KERNEL_RELEASE_TAG` env in the workflow)
3. Title: `Samsung F956B kernel source archive`
4. Drag and drop these two files (do not commit them to git):
   - `Kernel.tar.gz` (from `H:\Users\dsc\Downloads\SM-F956B_16_Opensource\Kernel.tar.gz`,
     639,619,118 bytes)
   - `Platform.tar.gz` (from `H:\Users\dsc\Downloads\SM-F956B_16_Opensource\Platform.tar.gz`,
     40,017,832 bytes)
5. Publish the release.

The workflow step `download Samsung F956B kernel source` will then fetch
both files from
`https://github.com/debug-deng/f956b-test/releases/download/<tag>/<file>`.

## Option B — Commit to a separate branch (not recommended)

These archives are 680 MB combined, which approaches GitHub's per-file
100 MB limit on pushes via the regular API. You can split, but it is
clumsier than option A.

## Option C — Local-only (manual run only)

If you only want to run the build on your PC and not in CI, run the
Docker step directly:

```sh
cd H:\Users\dsc\Downloads\port_f956b\work
mkdir SM-F956B_16_Opensource
cp ..\..\SM-F956B_16_Opensource\Kernel.tar.gz SM-F956B_16_Opensource\
cp ..\..\SM-F956B_16_Opensource\Platform.tar.gz SM-F956B_16_Opensource\
docker run --rm \
  -v "$PWD\..:/workspace:rw" \
  -v "$PWD\SM-F956B_16_Opensource:/samsung-kernel:ro" \
  -w /workspace \
  -e KDIR=/opt/ddk/kdir/android14-6.1 \
  ghcr.io/ylarod/ddk-min:android14-6.1-20260313 \
  bash /workspace/.github/workflows/build.sh
```