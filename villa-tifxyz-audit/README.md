# villa patch: `vesuvius.tifxyz_audit`

Adds a `vesuvius.tifxyz_audit` console script on top of the #1522 `meta_frames`
patch. Author: Scroll Ash Lab \<scrollash.lab@gmail.com\>.

## Apply order (villa `main` @ `0e14cf48`)

```bash
git am villa-1522/0001-*.patch
git am villa-tifxyz-audit/0001-*.patch
```

Standalone package (no villa install): see `tools/tifxyz-audit/`. Keep its
vendored `meta_frames.py` in sync with #1522 (`SCALE_RTOL=1e-6`).

## Tests included in this patch

`vesuvius/tests/tifxyz/test_tifxyz_audit.py` (2 tests). Together with
`test_meta_frames.py` on the 8-patch stack @ `0e14cf48`: **14 passed**
(2026-10-05 HST). This patch no longer modifies `meta_frames.py` — tolerant
scale matching lives entirely in #1522.
