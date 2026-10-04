"""Separate personal workspace data from immutable, atomically published versions."""
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import uuid


def _write_json(path, value, exclusive=True):
    text = json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n'
    with Path(path).open('x' if exclusive else 'w', encoding='utf-8') as stream:
        stream.write(text)
        stream.flush()
        import os
        os.fsync(stream.fileno())


def initialize_workspace(path):
    root = Path(path).resolve()
    root.mkdir(parents=True, exist_ok=True)
    for name in ('inputs', 'versions', 'exports'):
        (root / name).mkdir(exist_ok=True)
    master = root / 'master.json'
    try:
        _write_json(master, {'schema_version': '1.0', 'profile': {}, 'target': {'language': 'zh', 'seniority': 'experienced', 'paper': 'A4'}, 'experiences': [], 'sources': []})
    except FileExistsError:
        pass
    return {'path': str(root), 'master_path': str(master), 'versions_path': str(root / 'versions')}


def save_version(path, payload, metadata=None):
    """Publish complete directories by same-filesystem rename; never reuse an ID."""
    # Serialize before filesystem changes, so failures leave no half-created version.
    json.dumps(payload, ensure_ascii=False, allow_nan=False)
    json.dumps(metadata or {}, ensure_ascii=False, allow_nan=False)
    if metadata is not None and not isinstance(metadata, dict):
        raise ValueError('metadata 必须为对象。')
    root = Path(path).resolve()
    root.mkdir(parents=True, exist_ok=True)
    versions = root / 'versions'
    versions.mkdir(exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ')
    identifier = stamp + '-' + uuid.uuid4().hex
    temporary = versions / ('.tmp-' + uuid.uuid4().hex)
    final = versions / identifier
    temporary.mkdir()
    details = dict(metadata or {})
    details.update(version_id=identifier, created_at=datetime.now(timezone.utc).isoformat())
    try:
        _write_json(temporary / 'payload.json', payload)
        _write_json(temporary / 'metadata.json', details)
        if final.exists():
            raise FileExistsError('新版本目录已存在。')
        temporary.rename(final)
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)
    return {'version_id': identifier, 'path': str(final), 'payload': json.loads((final / 'payload.json').read_text(encoding='utf-8')), 'metadata': details}


def load_latest(path):
    """Read the latest complete version; ignore unfinished temporary directories."""
    versions = Path(path).resolve() / 'versions'
    if not versions.exists():
        return None
    candidates = sorted((p for p in versions.iterdir() if p.is_dir() and not p.name.startswith('.')), key=lambda p: p.name, reverse=True)
    for candidate in candidates:
        if not (candidate / 'payload.json').is_file() or not (candidate / 'metadata.json').is_file():
            continue
        try:
            payload = json.loads((candidate / 'payload.json').read_text(encoding='utf-8'))
            metadata = json.loads((candidate / 'metadata.json').read_text(encoding='utf-8'))
        except (ValueError, OSError):
            continue
        return {'version_id': candidate.name, 'path': str(candidate), 'payload': payload, 'metadata': metadata}
    return None
