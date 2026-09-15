from __future__ import annotations

import argparse
import hashlib
from pathlib import Path


FORBIDDEN_NAMES = {
    '.env',
    'all_for_cabal_web.db',
    'all_for_cabal_web_dev.db',
    '.cabal_chrome_profile',
    'config.json',
}
FORBIDDEN_SUFFIXES = {
    '.db',
    '.sqlite',
    '.sqlite3',
    '.xlsx',
    '.xlsm',
    '.log',
}
FORBIDDEN_COMPONENTS = {
    '.git',
    '.worktrees',
    'dist',
    'build',
    '__pycache__',
    '.pytest_cache',
}

SHIPPED_TEMPLATES = {
    'web/static/templates/bundle-template.xlsx',
    '_internal/web/static/templates/bundle-template.xlsx',
}


def _forbidden_reason(relative: Path) -> str | None:
    lowered_parts = [part.casefold() for part in relative.parts]
    if any(part in FORBIDDEN_COMPONENTS for part in lowered_parts):
        return 'forbidden directory'
    if any(part in FORBIDDEN_NAMES for part in lowered_parts):
        return 'private runtime name'
    # Only the reviewed, bundled template is public; uploaded workbooks remain forbidden.
    if relative.as_posix().casefold() in SHIPPED_TEMPLATES:
        return None
    if relative.suffix.casefold() in FORBIDDEN_SUFFIXES:
        return 'private runtime suffix'
    return None


def verify_tree(root: str | Path) -> None:
    package = Path(root)
    if not package.exists():
        raise ValueError(f'release path does not exist: {package}')

    if package.is_file():
        reason = _forbidden_reason(Path(package.name))
        if reason:
            raise ValueError(f'{reason}: {package.name}')
        return

    # Check files first so an error names the actual leaked artifact rather
    # than only its containing directory. Empty forbidden directories are
    # checked in the second pass.
    entries = list(package.rglob('*'))
    for path in (entry for entry in entries if not entry.is_dir()):
        relative = path.relative_to(package)
        reason = _forbidden_reason(relative)
        if reason:
            raise ValueError(f'{reason}: {relative}')
    for path in (entry for entry in entries if entry.is_dir()):
        relative = path.relative_to(package)
        reason = _forbidden_reason(relative)
        if reason:
            raise ValueError(f'{reason}: {relative}')


def write_checksum(file_path: str | Path) -> Path:
    source = Path(file_path)
    if not source.is_file():
        raise ValueError(f'checksum source is not a file: {source}')
    digest = hashlib.sha256()
    with source.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    destination = source.with_name(source.name + '.sha256')
    destination.write_text(
        f'{digest.hexdigest()} *{source.name}\n',
        encoding='ascii',
    )
    return destination


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description='Verify an All for Cabal Web release tree.')
    parser.add_argument('path')
    parser.add_argument(
        '--checksum',
        metavar='FILE',
        help='also write a streaming SHA-256 sidecar for FILE',
    )
    args = parser.parse_args(argv)
    verify_tree(args.path)
    if args.checksum:
        write_checksum(args.checksum)
        verify_tree(args.path)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
