import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))

import install_skill
from build_release import RESOURCE_FILES


class InstallerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='resume-installer-test-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.skills = self.root / 'skills'
        self.destination = self.skills / 'resume-workbench'
        self.resources = {name: ('fixture: ' + name).encode('utf-8') for name in RESOURCE_FILES}

    def package(self, resources=None, manifest=None):
        resources = self.resources if resources is None else resources
        if manifest is None:
            manifest = {'version': '0.1.0', 'sha256': {
                name: hashlib.sha256(content).hexdigest() for name, content in resources.items()}}
        archive = self.root / 'release.zip'
        with ZipFile(archive, 'w') as output:
            for name, content in resources.items():
                output.writestr('resume-workbench/' + name, content)
            output.writestr('resume-workbench/RELEASE-MANIFEST.json', json.dumps(manifest))
        return archive

    def existing_install(self):
        self.destination.mkdir(parents=True)
        (self.destination / 'SKILL.md').write_text('existing skill', encoding='utf-8')

    def assert_existing_preserved(self):
        self.assertTrue((self.destination / 'SKILL.md').is_file(), 'Existing skill was removed.')
        self.assertEqual('existing skill', (self.destination / 'SKILL.md').read_text(encoding='utf-8'))

    def assert_rejected_before_change(self, archive):
        with self.assertRaises(Exception) as caught:
            install_skill.install(archive, self.skills, backup=True)
        self.assertIsInstance(caught.exception, ValueError)
        self.assert_existing_preserved()
        self.assertEqual([], list(self.skills.glob('resume-workbench.backup-*')))

    def test_rejects_malformed_manifest_before_changing_existing_install(self):
        self.existing_install()
        for manifest in ([], {}, {'version': '0.1.0'},
                         {'version': '0.1.0', 'sha256': []}):
            with self.subTest(manifest=manifest):
                self.assert_rejected_before_change(self.package(manifest=manifest))

    def test_rejects_missing_or_invalid_version_before_changing_existing_install(self):
        self.existing_install()
        hashes = {name: hashlib.sha256(content).hexdigest() for name, content in self.resources.items()}
        for version in (None, '', '   ', 1):
            manifest = {'sha256': hashes}
            if version is not None:
                manifest['version'] = version
            with self.subTest(version=version):
                self.assert_rejected_before_change(self.package(manifest=manifest))

    def test_rejects_empty_skill_before_changing_existing_install(self):
        self.existing_install()
        self.assert_rejected_before_change(self.package(resources={}))

    def test_rejects_missing_required_resource_before_changing_existing_install(self):
        self.existing_install()
        resources = dict(self.resources)
        del resources['SKILL.md']
        self.assert_rejected_before_change(self.package(resources=resources))

    def test_rejects_manifested_file_outside_release_whitelist(self):
        self.existing_install()
        resources = dict(self.resources, **{'personal.json': b'fixture'})
        self.assert_rejected_before_change(self.package(resources=resources))

    def test_copy_failure_preserves_existing_install_and_removes_staging(self):
        self.existing_install()
        archive = self.package()

        def partial_copy(source, destination):
            destination = Path(destination)
            destination.mkdir()
            (destination / 'partial.txt').write_text('incomplete', encoding='utf-8')
            raise OSError('simulated disk full')

        with patch.object(install_skill.shutil, 'copytree', side_effect=partial_copy):
            with self.assertRaises(OSError):
                install_skill.install(archive, self.skills, backup=True)
        self.assert_existing_preserved()
        self.assertEqual([], list(self.skills.glob('resume-workbench.backup-*')))
        self.assertEqual([], list(self.skills.glob('.resume-workbench-install-*')))

    def test_failed_switch_restores_existing_install_and_removes_staging(self):
        self.existing_install()
        archive = self.package()
        rename = Path.rename

        def fail_switch(source, target):
            if source.name == 'resume-workbench' and Path(target) == self.destination:
                raise OSError('simulated installation switch failure')
            return rename(source, target)

        with patch.object(Path, 'rename', fail_switch):
            with self.assertRaises(OSError):
                install_skill.install(archive, self.skills, backup=True)
        self.assert_existing_preserved()
        self.assertEqual([], list(self.skills.glob('resume-workbench.backup-*')))
        self.assertEqual([], list(self.skills.glob('.resume-workbench-install-*')))

    def test_failed_rollback_retains_old_install_in_reported_backup(self):
        self.existing_install()
        archive = self.package()
        rename = Path.rename

        def fail_switch_and_restore(source, target):
            if Path(target) == self.destination:
                raise OSError('simulated switch and restore failure')
            return rename(source, target)

        with patch.object(Path, 'rename', fail_switch_and_restore):
            with self.assertRaises(OSError) as caught:
                install_skill.install(archive, self.skills, backup=True)
        backups = list(self.skills.glob('resume-workbench.backup-*'))
        self.assertEqual(1, len(backups))
        self.assertEqual('existing skill', (backups[0] / 'SKILL.md').read_text(encoding='utf-8'))
        self.assertIn(str(backups[0]), str(caught.exception))
        self.assertFalse(self.destination.exists())
        self.assertEqual([], list(self.skills.glob('.resume-workbench-install-*')))

    def test_existing_install_requires_explicit_backup(self):
        self.existing_install()
        with self.assertRaises(ValueError):
            install_skill.install(self.package(), self.skills)
        self.assert_existing_preserved()
        self.assertEqual([], list(self.skills.glob('resume-workbench.backup-*')))

    def test_successful_update_preserves_old_install_in_backup(self):
        self.existing_install()
        result = install_skill.install(self.package(), self.skills, backup=True)
        self.assertTrue(result['ok'])
        self.assertEqual('0.1.0', result['version'])
        self.assertEqual(b'fixture: SKILL.md', (self.destination / 'SKILL.md').read_bytes())
        self.assertEqual('existing skill', (Path(result['backup']) / 'SKILL.md').read_text(encoding='utf-8'))
        self.assertEqual([], list(self.skills.glob('.resume-workbench-install-*')))


if __name__ == '__main__':
    unittest.main()
