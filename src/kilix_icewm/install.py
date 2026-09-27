"""Ownership records for the per-user state this provider creates.

This is not a package manager. The provider only ever writes below one
storage home -- a built IceWM prefix, the CMake build tree that produced it,
and a regenerated private configuration directory -- and an uninstall has to
answer exactly one question about each path there: *did this install put that
byte there, and is it still the byte we put there?*

A manifest answers that and nothing else, which is the whole design:

* every path an install creates is recorded, with a digest for files and the
  link target for symlinks, so a later removal recognises its own work;
* paths are stored **relative to the directory holding the manifest**, so a
  manifest can only ever describe state inside the storage home it lives in,
  and it carries no absolute home path;
* removal touches recorded paths only. A file the operator edited, replaced
  or created is left alone and reported, never deleted;
* no path component below the storage home may be a symlink at removal time.
  A redirected component means the recorded path is no longer the path we
  wrote, so it is refused rather than followed out of the storage home;
* directories are pruned only when the install created them and only while
  empty, so anything unowned that survives keeps its parents alive too.

The consequence worth stating plainly: an uninstall that reports preserved or
refused paths has not finished, exits non-zero, and keeps its manifest so the
operator can resolve the difference and run it again.
"""
from __future__ import annotations

import argparse
import hashlib
import os
import sys
import tempfile

__all__ = [
    "CONFIG_MANIFEST",
    "INSTALL_MANIFEST",
    "ManifestError",
    "Report",
    "load",
    "missing_directories",
    "record_files",
    "record_tree",
    "remove",
    "scan_directories",
]

# Both manifests sit directly in the storage home, beside the state they own.
INSTALL_MANIFEST = "install-manifest"
CONFIG_MANIFEST = "config-manifest"

HEADER = "kilix-icewm-manifest 1"
_FORBIDDEN = ("\t", "\n", "\r")


class ManifestError(Exception):
    """A manifest could not be written, read, or trusted."""


class Report:
    """What one removal actually did, in the manifest's own terms."""

    def __init__(self, manifest: str):
        self.manifest = manifest
        self.removed: list[str] = []
        self.preserved: list[str] = []
        self.refused: list[str] = []
        self.pruned: list[str] = []
        self.kept: list[str] = []

    @property
    def complete(self) -> bool:
        """True when nothing owned was left behind and nothing was refused."""
        return not self.preserved and not self.refused and not self.kept


def _abs(path: str) -> str:
    return os.path.abspath(os.path.expanduser(path))


def _base_of(manifest: str) -> str:
    return os.path.dirname(_abs(manifest))


def _relative(path: str, base: str) -> str:
    """Return ``path`` relative to ``base``, refusing anything outside it."""
    rel = os.path.relpath(_abs(path), base)
    if rel == os.curdir:
        raise ManifestError(f"refusing to record the storage home itself: {path}")
    if rel == os.pardir or rel.startswith(os.pardir + os.sep) or os.path.isabs(rel):
        raise ManifestError(f"path is outside the storage home: {path}")
    for bad in _FORBIDDEN:
        if bad in rel:
            raise ManifestError(f"path contains an unrecordable character: {path}")
    return rel


def _symlinked_component(base: str, rel: str) -> str | None:
    """Return the first symlinked component of ``base/rel``, excluding the leaf.

    The storage home itself counts: everything recorded is reached through it.
    """
    if os.path.islink(base):
        return base
    current = base
    for part in rel.split(os.sep)[:-1]:
        current = os.path.join(current, part)
        if os.path.islink(current):
            return current
    return None


def digest(path: str) -> str:
    """SHA-256 of a regular file, read in bounded chunks."""
    hasher = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def missing_directories(path: str, base: str) -> list[str]:
    """Ancestors of ``path`` under ``base``, inclusive, that do not exist yet.

    Called *before* the directories are created, so its answer is exactly the
    set this install is about to bring into being and may therefore prune.
    """
    base = _abs(base)
    rel = _relative(path, base)
    created = []
    current = base
    for part in rel.split(os.sep):
        current = os.path.join(current, part)
        if not os.path.isdir(current) or os.path.islink(current):
            created.append(current)
    return created


def scan_directories(roots) -> set:
    """Every directory that exists at or below ``roots`` right now."""
    found = set()
    for root in roots:
        root = _abs(root)
        if not os.path.isdir(root) or os.path.islink(root):
            continue
        found.add(root)
        for parent, names, _files in os.walk(root):
            for name in names:
                child = os.path.join(parent, name)
                if not os.path.islink(child):
                    found.add(child)
    return found


def _write_private(path: str, text: str) -> None:
    """Replace ``path`` with ``text`` through a private same-directory file."""
    directory = os.path.dirname(path) or os.curdir
    fd, tmp = tempfile.mkstemp(
        prefix="." + os.path.basename(path) + ".", suffix=".tmp",
        dir=directory, text=True,
    )
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fd = -1
            fh.write(text)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    except BaseException:
        if fd >= 0:
            os.close(fd)
        try:
            os.unlink(tmp)
        except FileNotFoundError:
            pass
        raise


def load(manifest: str):
    """Return ``(files, links, directories)`` as (relative) manifest records."""
    manifest = _abs(manifest)
    if os.path.islink(manifest):
        raise ManifestError(f"refusing a symlinked manifest: {manifest}")
    try:
        with open(manifest, encoding="utf-8") as fh:
            lines = fh.read().splitlines()
    except FileNotFoundError:
        raise ManifestError(f"no install manifest at {manifest}") from None
    if not lines or lines[0] != HEADER:
        raise ManifestError(f"not a kilix-icewm manifest: {manifest}")
    files: list[tuple[str, str]] = []
    links: list[tuple[str, str]] = []
    directories: list[str] = []
    for number, line in enumerate(lines[1:], 2):
        if not line:
            continue
        fields = line.split("\t")
        if fields[0] == "file" and len(fields) == 3:
            files.append((fields[1], fields[2]))
        elif fields[0] == "link" and len(fields) == 3:
            links.append((fields[1], fields[2]))
        elif fields[0] == "dir" and len(fields) == 2:
            directories.append(fields[1])
        else:
            raise ManifestError(f"malformed manifest line {number}: {manifest}")
    for _value, rel in files + links:
        _check_recorded(rel, manifest)
    for rel in directories:
        _check_recorded(rel, manifest)
    return files, links, directories


def _check_recorded(rel: str, manifest: str) -> None:
    if os.path.isabs(rel) or rel in ("", os.curdir):
        raise ManifestError(f"unsafe manifest path {rel!r} in {manifest}")
    parts = rel.split(os.sep)
    if os.pardir in parts or "" in parts:
        raise ManifestError(f"unsafe manifest path {rel!r} in {manifest}")


def _previous_directories(manifest: str) -> list[str]:
    """Directory records already on file, so a rebuild does not forget them."""
    try:
        _files, _links, directories = load(manifest)
    except ManifestError:
        return []
    return directories


def _emit(manifest: str, files, links, directories) -> int:
    base = _base_of(manifest)
    lines = [HEADER]
    for value, rel in files:
        lines.append(f"file\t{value}\t{rel}")
    for target, rel in links:
        lines.append(f"link\t{target}\t{rel}")
    # Deepest last on disk; removal sorts them deepest-first when pruning.
    for rel in sorted(set(directories), key=lambda rel: (rel.count(os.sep), rel)):
        lines.append(f"dir\t{rel}")
    os.makedirs(base, mode=0o700, exist_ok=True)
    _write_private(manifest, "\n".join(lines) + "\n")
    return len(files) + len(links)


def _classify(path: str, base: str, manifest_rel: str):
    """Return a ``file``/``link`` record for one path, or ``None`` to skip."""
    rel = _relative(path, base)
    if rel == manifest_rel:
        return None
    if os.path.islink(path):
        target = os.readlink(path)
        for bad in _FORBIDDEN:
            if bad in target:
                raise ManifestError(f"unrecordable symlink target at {path}")
        return "link", target, rel
    if os.path.isfile(path):
        return "file", digest(path), rel
    return None


def record_files(manifest: str, paths, directories=()) -> int:
    """Record an explicit set of files, merging earlier directory records."""
    manifest = _abs(manifest)
    base = _base_of(manifest)
    manifest_rel = os.path.basename(manifest)
    files, links = [], []
    for path in paths:
        record = _classify(_abs(path), base, manifest_rel)
        if record is None:
            continue
        kind, value, rel = record
        (links if kind == "link" else files).append((value, rel))
    recorded = [_relative(path, base) for path in directories]
    recorded += _previous_directories(manifest)
    return _emit(manifest, files, links, recorded)


def record_tree(manifest: str, roots, directories=()) -> int:
    """Record everything below ``roots``, merging earlier directory records.

    A rebuild replaces the file records wholesale -- that is the point, the
    digests must describe the bytes now on disk -- while directory records
    accumulate, because the second build creates none of the directories the
    first one did and would otherwise forget it may prune them.
    """
    manifest = _abs(manifest)
    base = _base_of(manifest)
    manifest_rel = os.path.basename(manifest)
    files, links = [], []
    for root in roots:
        root = _abs(root)
        _relative(root, base)
        if not os.path.isdir(root) or os.path.islink(root):
            continue
        for parent, names, filenames in os.walk(root):
            # A symlinked directory is recorded as the link it is and never
            # descended into: what lives behind it belongs to whoever made it.
            linked = [n for n in names if os.path.islink(os.path.join(parent, n))]
            names[:] = [n for n in names if n not in linked]
            for name in sorted(filenames + linked):
                record = _classify(os.path.join(parent, name), base, manifest_rel)
                if record is None:
                    continue
                kind, value, rel = record
                (links if kind == "link" else files).append((value, rel))
    recorded = [_relative(path, base) for path in directories]
    recorded += _previous_directories(manifest)
    return _emit(manifest, files, links, recorded)


def remove(manifest: str) -> Report:
    """Remove exactly what ``manifest`` records, and report everything else."""
    manifest = _abs(manifest)
    base = _base_of(manifest)
    if os.path.islink(base):
        raise ManifestError(f"refusing a symlinked storage home: {base}")
    files, links, directories = load(manifest)
    report = Report(manifest)

    for expected, rel in files:
        path = os.path.join(base, rel)
        blocked = _symlinked_component(base, rel)
        if blocked is not None:
            report.refused.append(rel)
            continue
        if not os.path.lexists(path):
            continue
        if os.path.islink(path) or not os.path.isfile(path):
            report.preserved.append(rel)
            continue
        if digest(path) != expected:
            report.preserved.append(rel)
            continue
        os.unlink(path)
        report.removed.append(rel)

    for target, rel in links:
        path = os.path.join(base, rel)
        if _symlinked_component(base, rel) is not None:
            report.refused.append(rel)
            continue
        if not os.path.lexists(path):
            continue
        if not os.path.islink(path) or os.readlink(path) != target:
            report.preserved.append(rel)
            continue
        os.unlink(path)
        report.removed.append(rel)

    # Deepest first: a parent can only be empty once its children are gone.
    for rel in sorted(directories, key=lambda rel: (-rel.count(os.sep), rel)):
        path = os.path.join(base, rel)
        if _symlinked_component(base, rel) is not None:
            report.refused.append(rel)
            continue
        if os.path.islink(path):
            report.preserved.append(rel)
            continue
        if not os.path.isdir(path):
            continue
        try:
            os.rmdir(path)
        except OSError:
            report.kept.append(rel)
            continue
        report.pruned.append(rel)

    # An incomplete removal keeps its manifest: the operator resolves what was
    # preserved and runs the same command again.
    if report.complete:
        os.unlink(manifest)
    return report


def _snapshot(args) -> int:
    lines = sorted(scan_directories(args.root))
    with open(args.output, "w", encoding="utf-8") as fh:
        fh.write("".join(line + "\n" for line in lines))
    return 0


def _record(args) -> int:
    before = set()
    if args.snapshot:
        with open(args.snapshot, encoding="utf-8") as fh:
            before = {line for line in fh.read().splitlines() if line}
    created = sorted(scan_directories(args.root) - before)
    count = record_tree(args.manifest, args.root, created)
    print(f"kilix-icewm: recorded {count} installed paths in {args.manifest}")
    return 0


def _remove(args) -> int:
    report = remove(args.manifest)
    print(
        f"kilix-icewm: removed {len(report.removed)} files and "
        f"{len(report.pruned)} directories recorded by {args.manifest}"
    )
    for rel in report.preserved:
        print(f"  kept, not ours any more: {rel}", file=sys.stderr)
    for rel in report.refused:
        print(f"  refused, symlinked path component: {rel}", file=sys.stderr)
    for rel in report.kept:
        print(f"  kept, directory not empty: {rel}", file=sys.stderr)
    return 0 if report.complete else 1


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="kilix-icewm-manifest")
    sub = parser.add_subparsers(dest="command", required=True)

    snapshot = sub.add_parser(
        "snapshot", help="list the directories that exist before an install")
    snapshot.add_argument("--root", action="append", required=True)
    snapshot.add_argument("--output", required=True)
    snapshot.set_defaults(handler=_snapshot)

    record = sub.add_parser("record", help="record an install in a manifest")
    record.add_argument("--manifest", required=True)
    record.add_argument("--root", action="append", required=True)
    record.add_argument("--snapshot")
    record.set_defaults(handler=_record)

    delete = sub.add_parser("remove", help="remove exactly what a manifest records")
    delete.add_argument("--manifest", required=True)
    delete.set_defaults(handler=_remove)

    args = parser.parse_args(argv)
    try:
        return args.handler(args)
    except ManifestError as exc:
        print(f"kilix-icewm: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
