"""Explicit local diagnostic exports only; never overwrite an existing file.

A three-file export is not a filesystem transaction. On an I/O failure, retain
any already written parts and report the failure instead of deleting evidence.
"""
from pathlib import Path


def output_paths(selected: str | Path) -> tuple[Path, Path, Path]:
    path = Path(selected)
    # Remove only the chosen PNG suffix; preserve meaningful dots in the name.
    base = path.with_suffix('') if path.suffix.casefold() == '.png' else path
    return tuple(Path(str(base) + suffix) for suffix in ('.raw.png', '.preview.png', '.json'))


def write_diagnostic(selected: str | Path, raw: bytes, preview: bytes, metadata: bytes):
    paths = output_paths(selected)
    if any(p.exists() or p.is_symlink() for p in paths):
        raise FileExistsError('A diagnostic with this base name exists; choose a new name')
    for path, payload in zip(paths, (raw, preview, metadata)):
        if not isinstance(payload, bytes):
            raise TypeError('Diagnostic payloads must be bytes')
    # Exclusive creation also refuses an intervening conflicting writer.
    for path, payload in zip(paths, (raw, preview, metadata)):
        with path.open('xb') as stream:
            stream.write(payload)
    return paths
