"""Package reviewed skill resources only; never traverse user workspaces."""
import argparse
import hashlib
import json
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / 'skills' / 'resume-workbench'
RESOURCE_FILES = [
    'SKILL.md', 'LICENSE', 'agents/openai.yaml', 'requirements.txt',
    'scripts/resume.py', 'scripts/rw/__init__.py',
    'scripts/rw/core.py', 'scripts/rw/workspace.py', 'scripts/rw/targeting.py',
    'scripts/rw/github.py', 'scripts/rw/importing.py', 'scripts/rw/templates.py',
    'scripts/rw/continuation.py', 'scripts/rw/rendering.py', 'scripts/rw/exporting.py', 'scripts/rw/quality.py',
    'references/data-model.md', 'references/content-and-targeting.md', 'references/templates.md',
    'references/files-and-export.md', 'references/continuation.md',
    'assets/default-zh.docx', 'assets/default-en.docx',
    'assets/examples/operations-zh.json', 'assets/examples/technical-zh.json',
    'assets/examples/experienced-en.json', 'assets/examples/jd-operations.txt',
]


def build(outdir):
    outdir = Path(outdir).resolve()
    outdir.mkdir(parents=True, exist_ok=True)
    missing = [name for name in RESOURCE_FILES if not (SKILL / name).is_file()]
    if missing:
        raise ValueError('Missing release resources: ' + ', '.join(missing))
    from sys import path
    path.insert(0, str(SKILL / 'scripts'))
    from rw import __version__
    destination = outdir / f'resume-workbench-{__version__}.zip'
    if destination.exists():
        raise ValueError('Release exists; use a new output directory to retain previous package.')
    hashes = {}
    with ZipFile(destination, 'x', compression=ZIP_DEFLATED) as archive:
        for name in RESOURCE_FILES:
            content = (SKILL / name).read_bytes()
            hashes[name] = hashlib.sha256(content).hexdigest()
            archive.writestr('resume-workbench/' + name, content)
        archive.writestr('resume-workbench/RELEASE-MANIFEST.json', json.dumps({'version': __version__, 'sha256': hashes}, indent=2))
    report = {'version': __version__, 'zip': str(destination), 'sha256': hashlib.sha256(destination.read_bytes()).hexdigest(),
              'file_count': len(RESOURCE_FILES) + 1}
    destination.with_suffix('.zip.sha256').write_text(report['sha256'] + '  ' + destination.name + '\n', encoding='utf-8')
    return report


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--outdir', required=True)
    args = p.parse_args()
    print(json.dumps(build(args.outdir), ensure_ascii=False, indent=2))
