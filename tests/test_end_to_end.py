import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from docx import Document
from rw.core import materialize_resume

ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / 'skills/resume-workbench/scripts/resume.py'
EXAMPLES = ROOT / 'skills/resume-workbench/assets/examples'


class EndToEndTests(unittest.TestCase):
    def call(self, *args):
        result = subprocess.run([sys.executable, '-X', 'utf8', str(CLI), *map(str, args)], capture_output=True, text=True, encoding='utf-8')
        return result, json.loads(result.stdout)

    def test_initialize_validate_tailor_and_immutable_fact_selection(self):
        with tempfile.TemporaryDirectory() as tmp:
            result, report = self.call('init', tmp)
            self.assertEqual(0, result.returncode)
            self.assertTrue(Path(report['master_path']).exists())
            example = EXAMPLES / 'operations-zh.json'; original = example.read_bytes()
            result, report = self.call('validate', example)
            self.assertEqual(0, result.returncode, report)
            result, report = self.call('tailor', '--master', example, '--jd', EXAMPLES / 'jd-operations.txt')
            self.assertEqual(0, result.returncode, report)
            self.assertEqual('keyword_heuristic', report['method'])
            self.assertTrue(report['gaps'])
            self.assertEqual(original, example.read_bytes())
            result, report = self.call('build', '--master', example, '--select', 'work-1', '--workspace', tmp,
                                       '--outdir', Path(tmp) / 'exports', '--docx-only')
            self.assertEqual(0, result.returncode, report)
            self.assertTrue(Path(report['version']['path']).is_dir())
            text = '\n'.join(p.text for p in Document(report['docx']).paragraphs)
            self.assertIn('工作经历', text)
            self.assertNotIn('教育经历', text)

    def test_no_text_pdf_is_rejected_before_document_generation(self):
        with tempfile.TemporaryDirectory() as tmp:
            result, report = self.call('build', '--master', EXAMPLES / 'operations-zh.json', '--outdir', tmp,
                                       '--template', ROOT / 'tests/fixtures/no-text-template.pdf', '--allow-rebuild', '--docx-only')
            self.assertEqual(2, result.returncode, report)
            self.assertEqual('needs_ocr', report['status'])
            self.assertEqual([], list(Path(tmp).rglob('*.docx')))

    def test_template_and_latest_file_are_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            template = ROOT / 'tests/fixtures/paragraph-template.docx'; original = template.read_bytes()
            result, report = self.call('build', '--master', EXAMPLES / 'operations-zh.json', '--template', template,
                                       '--outdir', tmp, '--docx-only')
            self.assertEqual(0, result.returncode, report)
            self.assertEqual(original, template.read_bytes())
            self.assertNotIn('样例', report['quality']['docx_text'])
            latest = report['docx']; before = Path(latest).read_bytes()
            changes = Path(tmp) / 'changes.json'
            changes.write_text(json.dumps([{'old': '整理活动报名资料并交付周报，供团队复盘使用。',
                                          'new': '整理活动资料与周报，供团队复盘使用。'}], ensure_ascii=False), encoding='utf-8')
            result, updated = self.call('continue', '--latest', latest, '--replacements', changes, '--outdir', tmp, '--docx-only')
            self.assertEqual(0, result.returncode, updated)
            self.assertEqual(before, Path(latest).read_bytes())
            self.assertIn('整理活动资料与周报', updated['quality']['docx_text'])

    def test_qualification_and_estimated_metric_never_materialize(self):
        master = json.loads((EXAMPLES / 'operations-zh.json').read_text(encoding='utf-8'))
        bad = copy.deepcopy(master)
        bad['experiences'][0]['bullets'][0]['metrics'] = [{'value': 50, 'unit': '%', 'scope': '估计效率', 'basis': 'estimated'}]
        with self.assertRaises(ValueError): materialize_resume(bad)
        self.assertNotIn('整理活动报名资料', json.dumps(materialize_resume(bad, strict=False), ensure_ascii=False))


if __name__ == '__main__':
    unittest.main()
