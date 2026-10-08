"""CLI entry: ``python -m tifxyz_audit`` / ``tifxyz-audit`` / ``vesuvius.tifxyz_audit``."""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

from . import meta_frames
from .checks import audit_paths
from .report import exit_code, format_json, format_text


def _parse_volume_shape(text: str | None) -> tuple[int, int, int] | None:
    if not text:
        return None
    parts = [p.strip() for p in text.split(",")]
    if len(parts) != 3:
        raise argparse.ArgumentTypeError("volume shape must be Z,Y,X")
    return tuple(int(p) for p in parts)  # type: ignore[return-value]


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="tifxyz-audit",
        description=(
            "Audit tifxyz / mesh metadata for missing fields, TIFF consistency, "
            "and same-scale / different-voxel-size frame ambiguity (villa #1522)."
        ),
    )
    p.add_argument(
        "paths",
        nargs="+",
        type=Path,
        help="tifxyz dirs, segment dirs (with mesh/), or parent folders",
    )
    p.add_argument("--json", action="store_true", help="machine-readable JSON report")
    p.add_argument(
        "--strict",
        action="store_true",
        help="nonzero exit if any warning is present (default: only errors)",
    )
    p.add_argument(
        "--skip-tiff",
        action="store_true",
        help="skip x/y/z presence, header shape, and invalid-point checks",
    )
    p.add_argument(
        "--no-sample-invalid",
        action="store_true",
        help="do not sample z.tif for NaN / -1 fractions",
    )
    p.add_argument(
        "--volume-shape",
        type=_parse_volume_shape,
        default=None,
        metavar="Z,Y,X",
        help="optional volume shape to test bbox containment",
    )
    p.add_argument(
        "--fix-meta",
        action="store_true",
        help="write voxel_size_um into meta.json (requires --in-place or --output-dir)",
    )
    p.add_argument(
        "--in-place",
        action="store_true",
        help="with --fix-meta, modify meta.json in place (explicit; never default)",
    )
    p.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="with --fix-meta, copy each tifxyz dir here then write meta in the copy",
    )
    p.add_argument(
        "--overwrite-voxel-size",
        action="store_true",
        help="with --fix-meta, overwrite an existing voxel_size_um value",
    )
    return p


def _apply_fix_meta(
    dirs: list[Path],
    *,
    in_place: bool,
    output_dir: Path | None,
    overwrite: bool,
) -> list[str]:
    notes: list[str] = []
    if not in_place and output_dir is None:
        raise SystemExit(
            "--fix-meta requires --in-place or --output-dir (refusing silent writes)"
        )
    if in_place and output_dir is not None:
        raise SystemExit("use only one of --in-place or --output-dir")

    targets: list[Path] = []
    if output_dir is not None:
        output_dir.mkdir(parents=True, exist_ok=True)
        for d in dirs:
            dest = output_dir / d.name
            if dest.exists():
                raise SystemExit(f"refusing to overwrite existing copy: {dest}")
            shutil.copytree(d, dest)
            targets.append(dest)
            notes.append(f"copied {d} -> {dest}")
    else:
        targets = list(dirs)

    for d in targets:
        value = meta_frames.annotate_meta_voxel_size_um(d, overwrite=overwrite)
        notes.append(f"annotate {d}: voxel_size_um={value!r}")
    return notes


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    dirs, findings = audit_paths(
        args.paths,
        volume_shape=args.volume_shape,
        sample_invalid=not args.no_sample_invalid,
        skip_tiff=args.skip_tiff,
    )

    fix_notes: list[str] = []
    if args.fix_meta:
        if not dirs:
            print("no tifxyz dirs to annotate", file=sys.stderr)
            return 2
        fix_notes = _apply_fix_meta(
            dirs,
            in_place=args.in_place,
            output_dir=args.output_dir,
            overwrite=args.overwrite_voxel_size,
        )
        # Re-audit targets after fix
        re_inputs = [args.output_dir] if args.output_dir else dirs
        dirs, findings = audit_paths(
            re_inputs,
            volume_shape=args.volume_shape,
            sample_invalid=not args.no_sample_invalid,
            skip_tiff=args.skip_tiff,
        )

    if args.json:
        sys.stdout.write(format_json(findings, dirs))
        if fix_notes:
            # keep JSON clean; notes on stderr
            for n in fix_notes:
                print(n, file=sys.stderr)
    else:
        for n in fix_notes:
            print(n)
        sys.stdout.write(format_text(findings, dirs))

    return exit_code(findings, strict=args.strict)


if __name__ == "__main__":
    raise SystemExit(main())
