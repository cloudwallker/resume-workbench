"""Install a checksum-verified skill ZIP. Existing installations require backup."""
import argparse
import hashlib
import json
import shutil
import tempfile
from datetime import datetime
from pathlib import Path
from zipfile import ZipFile

if __package__:
    from .build_release import RESOURCE_FILES
else:
    from build_release import RESOURCE_FILES


def install(archive_path, skills_dir, backup=False):
    archive_path, skills_dir = Path(archive_path).resolve(), Path(skills_dir).resolve()
    destination = skills_dir / 'resume-workbench'
    backup_path = None
    with tempfile.TemporaryDirectory(prefix='resume-install-') as tmp:
        tmp = Path(tmp)
        with ZipFile(archive_path) as archive:
            for item in archive.infolist():
                target = (tmp / item.filename).resolve()
                if not target.is_relative_to(tmp) or not item.filename.startswith('resume-workbench/'):
                    raise ValueError('Unsafe archive path.')
            archive.extractall(tmp)
        source = tmp / 'resume-workbench'
        try:
            manifest = json.loads((source / 'RELEASE-MANIFEST.json').read_text(encoding='utf-8'))
        except (OSError, UnicodeError, ValueError) as error:
            raise ValueError('Invalid or missing release manifest.') from error
        if not isinstance(manifest, dict):
            raise ValueError('Release manifest must be an object.')
        version = manifest.get('version')
        if not isinstance(version, str) or not version.strip():
            raise ValueError('Release manifest requires a non-empty version string.')
        if not isinstance(manifest.get('sha256'), dict):
            raise ValueError('Release manifest requires a resource checksum object.')
        if set(manifest['sha256']) != set(RESOURCE_FILES):
            raise ValueError('Release manifest differs from the required resource whitelist.')
        expected = set(manifest['sha256']) | {'RELEASE-MANIFEST.json'}
        actual = {p.relative_to(source).as_posix() for p in source.rglob('*') if p.is_file()}
        if actual != expected:
            raise ValueError('Archive file list differs from release manifest.')
        for name, checksum in manifest['sha256'].items():
            file = (source / name).resolve()
            if not file.is_relative_to(source) or hashlib.sha256(file.read_bytes()).hexdigest() != checksum:
                raise ValueError('Resource checksum mismatch: ' + name)
        if destination.exists() and not backup:
            raise ValueError('Installation exists. Inspect it first, then use --backup-existing if authorized.')
        skills_dir.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='.resume-workbench-install-', dir=skills_dir) as staging_dir:
            staging = Path(staging_dir) / 'resume-workbench'
            shutil.copytree(source, staging)
            if destination.exists():
                if not backup:
                    raise ValueError('Installation exists. Inspect it first, then use --backup-existing if authorized.')
                backup_path = skills_dir / ('resume-workbench.backup-' + datetime.now().strftime('%Y%m%d-%H%M%S-%f'))
                destination.rename(backup_path)
            try:
                staging.rename(destination)
            except Exception:
                if backup_path is not None:
                    try:
                        backup_path.rename(destination)
                    except Exception as error:
                        raise OSError('Installation switch and rollback failed; previous installation retained at '
                                      + str(backup_path)) from error
                raise
    return {'ok': True, 'installed': str(destination), 'backup': str(backup_path) if backup_path else None,
            'version': version, 'resource_count': len(manifest['sha256'])}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('zip')
    parser.add_argument('--skills-dir', required=True)
    parser.add_argument('--backup-existing', action='store_true')
    args = parser.parse_args()
    print(json.dumps(install(args.zip, args.skills_dir, args.backup_existing), ensure_ascii=False, indent=2))
