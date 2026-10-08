#!/usr/bin/env bash
# Re-run every test/stacking check for the villa-downscale patch. Writes logs to out/.
# Needs: villa clone at ./villa, worktrees ./dev (patched commit) and ./main-check (main), env /workspace/envs/zarr3.
set -u
HERE=$(cd "$(dirname "$0")/.." && pwd); OUT=$HERE/out; PY=/workspace/envs/zarr3/bin/python
STACK=/workspace/vesuvius-lab/handoff/scroll-ash-lab-villa-fixes
PATCH=$(ls $HERE/patch/0001-*.patch)
MAIN=e0bbb8b40a2db58b1d71864f286eb85717e59e64
SUITE="tests/tifxyz src/vesuvius/tifxyz/test_reader_bbox.py src/vesuvius/tifxyz/test_labels.py tests/tifxyz_label_transfer tests/test_surface_preflight.py tests/test_imports.py"
ENVV=$($PY -c 'import sys,numpy,tifffile,cv2,zarr,pytest;print("Python",sys.version.split()[0],"numpy",numpy.__version__,"tifffile",tifffile.__version__,"cv2",cv2.__version__,"zarr",zarr.__version__,"pytest",pytest.__version__)')
NOTE="## note: the 2 test_imports CLI-help failures are environment-only (ModuleNotFoundError: nnunetv2 / pytorch_optimizer not installed in this env) and identical with and without the patch"
hdr() { echo "## $1; run $(date '+%Y-%m-%d %H:%M:%S HST')"; echo "## env /workspace/envs/zarr3: $ENVV; vesuvius not installed, PYTHONPATH=src"; echo "## patch: $(basename $PATCH) sha256 $(sha256sum $PATCH | cut -c1-64)"; }
summ() { rg "^(FAILED|SKIPPED)|passed|failed" || true; }

# 1. new tests on unpatched main (test file copied in, then removed)
cd $HERE/main-check/vesuvius
cp $HERE/dev/vesuvius/tests/tifxyz/test_open_data_downscale.py tests/tifxyz/
{ hdr "UNPATCHED main $(git rev-parse --short=12 HEAD) + only the new test file"; echo '$ pytest -q -rf tests/tifxyz/test_open_data_downscale.py'
  PYTHONPATH=src $PY -m pytest -q -p no:cacheprovider -rf tests/tifxyz/test_open_data_downscale.py 2>&1 | rg "^(FAILED|E  )|passed|failed"; } > $OUT/pytest-new-tests-on-main.log
rm tests/tifxyz/test_open_data_downscale.py
# 2. full suite on main
{ hdr "UNPATCHED main $(git rev-parse --short=12 HEAD), $(git status --porcelain | wc -l) uncommitted files"; echo "## \$ pytest -q -rfs $SUITE"; echo "$NOTE"
  PYTHONPATH=src $PY -m pytest -q -p no:cacheprovider -rfs $SUITE 2>&1 | summ; } > $OUT/pytest-main-baseline.log
# 3. new tests + full suite on patched
cd $HERE/dev/vesuvius
{ hdr "PATCHED $(git log --oneline -1 | cut -c1-12) on main, $(git status --porcelain | wc -l) uncommitted files"; echo '$ pytest -v tests/tifxyz/test_open_data_downscale.py'
  PYTHONPATH=src $PY -m pytest -v -p no:cacheprovider tests/tifxyz/test_open_data_downscale.py 2>&1 | rg "PASSED|FAILED|ERROR|passed|failed"; } > $OUT/pytest-new-tests-patched.log
{ hdr "PATCHED $(git log --oneline -1 | cut -c1-12) on main"; echo "## \$ pytest -q -rfs $SUITE"; echo "$NOTE"
  PYTHONPATH=src $PY -m pytest -q -p no:cacheprovider -rfs $SUITE 2>&1 | summ; } > $OUT/pytest-patched-full.log
# 4. stacking: bare main; 9-patch stack (README order, villa-1855 excluded) on 0e14cf48 and on main
cd $HERE/villa
{ hdr "stacking, plain 'git am' (no --3way), git $(git --version | cut -d' ' -f3)"
  for base in $MAIN 0e14cf48 ; do for mode in bare stack; do
    [ $base = 0e14cf48 ] && [ $mode = bare ] && continue
    w=/tmp/vds-$mode-${base:0:8}; git worktree remove --force $w 2>/dev/null; git worktree add -q --detach $w $base
    echo "### $mode on $(git -C $w rev-parse --short=12 HEAD)"
    if [ $mode = stack ]; then for d in 1970 1481 1522 tifxyz-audit 1520 1586 1300 1507 1648; do
      if git -C $w am -q $(ls $STACK/villa-$d/*.patch) >/dev/null 2>&1; then echo "OK   villa-$d"; else echo "FAIL villa-$d"; git -C $w am --abort; fi; done; fi
    if git -C $w am -q "$PATCH" 2>&1; then echo "OK   villa-downscale -> $(git -C $w log --oneline -1 | cut -c1-12)"; else echo "FAIL villa-downscale"; fi
    if [ $mode = stack ]; then echo "#### suite on stacked tree: $SUITE"; (cd $w/vesuvius && PYTHONPATH=src $PY -m pytest -q -p no:cacheprovider -rf $SUITE 2>&1 | rg "^FAILED|passed|failed"); fi
  done; done
  echo "$NOTE"; } > $OUT/stacking-2026-10-07.log 2>&1
