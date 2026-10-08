# villa #1300 — README `pip install` on Python 3.14 → vesuvius 0.1.10

**Issue:** https://github.com/ScrollPrize/villa/issues/1300 (verified open 2026-10-04)  
**Base:** villa `main` @ `5a4388f` (apply **after** `villa-1520`)  
**Author:** Scroll Ash Lab \<scrollash.lab@gmail.com\>  
**License:** MIT

## Problem

`main` `requires-python = ">=3.14,<3.15"`, but PyPI latest `vesuvius` **0.2.4** declares `requires_python` `<3.14,>=3.10`. On Python 3.14, `pip install vesuvius` therefore installs the older unrestricted release **0.1.10** (`requires_python >=3.8`) with no warning in the README.

Verified PyPI metadata (2026-10-04):

| version | requires_python |
|---------|-----------------|
| 0.1.10  | `>=3.8` |
| 0.2.0–0.2.2 | `<3.13,>=3.9` |
| 0.2.3 | `<3.13,>=3.10` |
| 0.2.4 | `<3.14,>=3.10` |

## Fix

Add an Installation callout naming the mismatch and a git install path:
`pip install "vesuvius @ git+https://github.com/ScrollPrize/villa.git#subdirectory=vesuvius"`.

Extends `tests/test_readme_entrypoints.py` with one assertion (created by #1520).

## Tests

**4 passed** for `tests/test_readme_entrypoints.py` after #1520+#1300.

## Limits

Docs/test only — does not publish a new PyPI build. End-to-end `pip install` on a real CPython 3.14 interpreter was **not** re-run on this box (no 3.14 toolchain here); the resolve claim rests on published `requires_python` metadata above.

## Verification (2026-10-04 PT) — GATE PASS

Real pip dry-run resolves (throwaway venvs; CPython via `uv python install 3.14`, 107 MiB under `/tmp/uv-py`):

| Interpreter | Resolved `vesuvius` | `requires_python` (from report) | Log |
|-------------|---------------------|----------------------------------|-----|
| CPython **3.14.8** | **0.1.10** | `>=3.8` | `pip-dry-run-py314.log` + `pip-dry-run-py314-report.json` |
| CPython **3.13.5** | **0.2.4** | `<3.14,>=3.10` | `pip-dry-run-py313.log` + `pip-dry-run-py313-report.json` |

README claim holds exactly. Throwaway venvs and uv cache removed after recording.

