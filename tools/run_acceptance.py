"""Run real file scenarios. All inputs are fictional; never fake visual review."""
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / 'skills/resume-workbench/scripts/resume.py'
EXAMPLES = ROOT / 'skills/resume-workbench/assets/examples'
FIXTURES = ROOT / 'tests/fixtures'


def main():
    folder = ROOT / 'output/acceptance' / datetime.now().strftime('%Y%m%d-%H%M%S-%f')
    folder.mkdir(parents=True)
    index = {'folder': str(folder), 'cases': [], 'visual_review': 'pending'}
    def run(name, arguments, expected=0):
        case = folder / name; case.mkdir()
        process = subprocess.run([sys.executable, '-X', 'utf8', str(CLI), *map(str, arguments)], capture_output=True, text=True, encoding='utf-8')
        (case / 'stdout.json').write_text(process.stdout, encoding='utf-8')
        if process.stderr: (case / 'stderr.txt').write_text(process.stderr, encoding='utf-8')
        report = json.loads(process.stdout)
        entry = {'name': name, 'exit_code': process.returncode, 'expected_exit_code': expected,
                 'report': str(case / 'stdout.json'), 'status': report.get('status', report.get('ok'))}
        if report.get('manifest'): entry['manifest'] = report['manifest']
        index['cases'].append(entry)
        (folder / 'index.json').write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding='utf-8')
        print(json.dumps(entry, ensure_ascii=False), flush=True)
        if process.returncode != expected:
            raise RuntimeError(f'{name} failed: inspect {entry["report"]}')
        return report
    def build(name, master, *extra):
        return run(name, ['build', '--master', EXAMPLES / master, '--outdir', folder / name / 'exports', '--backend', 'word', *extra])
    run('doctor', ['doctor'])
    operations = build('operations-general', 'operations-zh.json', '--workspace', folder / 'operations-workspace')
    build('technical-student', 'technical-zh.json')
    build('experienced-english', 'experienced-en.json')
    run('jd-advice', ['tailor', '--master', EXAMPLES / 'operations-zh.json', '--jd', EXAMPLES / 'jd-operations.txt'])
    build('jd-selected', 'operations-zh.json', '--select', 'work-1', '--select', 'education-1', '--jd', EXAMPLES / 'jd-operations.txt')
    build('paragraph-template', 'operations-zh.json', '--template', FIXTURES / 'paragraph-template.docx')
    build('table-template', 'operations-zh.json', '--template', FIXTURES / 'table-template.docx')
    build('pdf-reconstruction', 'operations-zh.json', '--template', operations['pdf'], '--allow-rebuild')
    run('continue-no-history', ['continue', '--latest', FIXTURES / 'manually-edited.docx', '--replacements', FIXTURES / 'changes.json',
                                '--outdir', folder / 'continue-no-history/exports', '--backend', 'word'])
    changes = folder / 'history-changes.json'
    changes.write_text(json.dumps([{'old': '整理活动报名资料并交付周报，供团队复盘使用。', 'new': '整理活动资料和周报，供团队复盘使用。'}], ensure_ascii=False), encoding='utf-8')
    run('continue-with-history', ['continue', '--latest', operations['docx'], '--replacements', changes,
                                  '--workspace', folder / 'operations-workspace', '--outdir', folder / 'continue-with-history/exports', '--backend', 'word'])
    run('converter-missing', ['build', '--master', EXAMPLES / 'operations-zh.json', '--outdir', folder / 'converter-missing/exports', '--backend', 'none'], 2)
    run('ocr-missing', ['build', '--master', EXAMPLES / 'operations-zh.json', '--outdir', folder / 'ocr-missing/exports',
                       '--template', FIXTURES / 'no-text-template.pdf', '--allow-rebuild'], 2)
    run('public-github', ['github', 'octocat/Hello-World'])
    print('Acceptance index: ' + str(folder / 'index.json'), flush=True)


if __name__ == '__main__':
    main()
