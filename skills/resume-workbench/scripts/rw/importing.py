"""Read untrusted source text. Templates never populate a personal fact store."""
from pathlib import Path
from docx import Document
from .templates import _all_paragraphs, _text, _issues, pdf_layout_profile


def inspect_input(path, purpose='resume'):
    if purpose not in ('resume', 'template', 'both'): raise ValueError('purpose 必须为 resume/template/both')
    path = Path(path)
    if not path.is_file(): raise FileNotFoundError(str(path))
    fmt = path.suffix.lower().lstrip('.')
    report = {'ok': True, 'path': str(path), 'format': fmt, 'purpose': purpose, 'text': '',
              'structure': {}, 'warnings': [], 'facts': [], 'source_status': 'pending',
              'allow_fact_import': purpose == 'resume', 'requires_ocr': False, 'requires_conversion': False}
    if purpose in ('template', 'both'):
        report['warnings'].append('模板中的文字仅供版式检查；不得将样例姓名、公司或经历当作个人事实。')
    if fmt == 'docx':
        doc = Document(path)
        paragraphs = [{'location': loc, 'text': _text(p), 'style': p.style.name} for loc, p in _all_paragraphs(doc)]
        report['text'] = '\n'.join(p['text'] for p in paragraphs if p['text'])
        report['structure'] = {'paragraphs': paragraphs, 'tables': [[[cell.text for cell in row.cells] for row in table.rows] for table in doc.tables], 'issues': _issues(doc)}
        report['warnings'].extend('复杂 Word 特征：' + issue for issue in _issues(doc))
    elif fmt == 'pdf':
        layout = pdf_layout_profile(path)
        report.update(ok=layout['ok'], requires_ocr=layout['requires_ocr'])
        report['text'] = '\n\n'.join(page['text'] for page in layout['pages'])
        report['structure'] = {'pages': layout['pages'], 'layout': layout['layout']}
        report['warnings'].extend(layout['warnings'])
    elif fmt in ('txt', 'md', 'json'):
        report['text'] = path.read_text(encoding='utf-8-sig'); report['structure'] = {'lines': len(report['text'].splitlines())}
    elif fmt == 'doc':
        report.update(ok=False, requires_conversion=True)
        report['warnings'].append('旧 DOC 需先用 Word/LibreOffice 转为 DOCX；原件未修改。')
    else:
        report['ok'] = False; report['warnings'].append('不支持的输入格式；请提供 DOCX/PDF/UTF-8 文本。')
    return report
