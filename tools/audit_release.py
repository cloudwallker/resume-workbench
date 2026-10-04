"""Check release allowlist, hashes, example identities and Word metadata."""
import argparse
import hashlib
import io
import json
import re
from pathlib import Path
from zipfile import ZipFile

from docx import Document
from build_release import RESOURCE_FILES


def audit(path):
    issues = []
    with ZipFile(path) as archive:
        names = set(archive.namelist())
        expected = {'resume-workbench/' + n for n in RESOURCE_FILES} | {'resume-workbench/RELEASE-MANIFEST.json'}
        if names != expected: issues.append({'code': 'file_list_mismatch'})
        manifest = json.loads(archive.read('resume-workbench/RELEASE-MANIFEST.json'))
        for name in RESOURCE_FILES:
            content = archive.read('resume-workbench/' + name)
            if hashlib.sha256(content).hexdigest() != manifest['sha256'].get(name):
                issues.append({'code': 'hash_mismatch', 'file': name})
            if name.endswith('.docx'):
                doc = Document(io.BytesIO(content))
                if doc.core_properties.author or doc.core_properties.last_modified_by:
                    issues.append({'code': 'author_metadata', 'file': name})
                continue
            text = content.decode('utf-8')
            secret_patterns = [r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----', r'\bAKIA[0-9A-Z]{16}\b',
                               r'\bgh[pousr]_[A-Za-z0-9]{30,}\b', r'\bgithub_pat_[A-Za-z0-9_]{30,}\b',
                               r'\bsk-[A-Za-z0-9_-]{30,}\b']
            if any(re.search(pattern, text) for pattern in secret_patterns):
                issues.append({'code': 'secret_pattern', 'file': name})
            if re.search(r'[A-Z]:[/\\]Users[/\\][^<"\s]+', text, re.I):
                issues.append({'code': 'personal_absolute_path', 'file': name})
            if name.startswith('assets/examples/') and name.endswith('.json'):
                data = json.loads(text)
                if data['profile'].get('email') != 'candidate@example.com':
                    issues.append({'code': 'unexpected_example_identity', 'file': name})
                if not any('虚构' in source.get('note', '') for source in data['sources']):
                    issues.append({'code': 'unmarked_fictional_example', 'file': name})
    return {'ok': not issues, 'zip': str(Path(path).resolve()), 'file_count': len(names), 'issues': issues,
            'checks': ['explicit resource allowlist', 'all content hashes', 'known secret patterns',
                       'personal absolute paths', 'fictional example identities', 'DOCX author metadata'],
            'scope': 'Automated checks plus manual resource review; no user workspace is packaged.'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('zip'); args = parser.parse_args()
    result = audit(args.zip)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result['ok'] else 2)
