import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]


class ReleaseTests(unittest.TestCase):
    def test_package_has_only_skill_resources_and_is_standalone(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = subprocess.run([sys.executable, '-X', 'utf8', str(ROOT / 'tools/build_release.py'), '--outdir', tmp],
                                    capture_output=True, text=True, encoding='utf-8')
            self.assertEqual(0, result.returncode, result.stdout + result.stderr)
            report = json.loads(result.stdout)
            with ZipFile(report['zip']) as archive:
                names = archive.namelist()
                self.assertIn('resume-workbench/SKILL.md', names)
                self.assertIn('resume-workbench/assets/default-zh.docx', names)
                self.assertNotIn('resume-workbench/output/', names)
                self.assertFalse(any('__pycache__' in n or n.endswith('.pyc') or '.env' in n for n in names))
                archive.extractall(Path(tmp) / 'unpacked')
            command = Path(tmp) / 'unpacked/resume-workbench/scripts/resume.py'
            smoke = subprocess.run([sys.executable, '-X', 'utf8', str(command), 'doctor'], capture_output=True, text=True, encoding='utf-8')
            self.assertEqual(0, smoke.returncode, smoke.stdout + smoke.stderr)
            self.assertIsInstance(json.loads(smoke.stdout), dict)


if __name__ == '__main__':
    unittest.main()
