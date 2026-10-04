"""Text/provenance checks and PDF rasterization; visual judgement remains explicit."""
import hashlib
import json
from pathlib import Path
import re
from urllib.parse import urlparse
from zipfile import ZipFile

from docx import Document


def _hash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _normalized(text):
    return re.sub(r'\s+', '', str(text)).replace('–', '-').replace('—', '-')


def _visible_paragraphs(root):
    """Read displayed text, excluding field instructions and XML metadata."""
    word = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
    paragraphs = []
    for paragraph in root.iter(word + 'p'):
        pieces = []

        def collect(element):
            # Textbox paragraphs are checked separately, not joined to their
            # enclosing body paragraph in an invented reading order.
            if element.tag == word + 'p' and element is not paragraph:
                return
            if element.tag == word + 't':
                pieces.append(element.text or '')
            elif element.tag == word + 'tab':
                pieces.append('\t')
            elif element.tag in (word + 'br', word + 'cr'):
                pieces.append('\n')
            else:
                for child in element:
                    collect(child)

        collect(paragraph)
        text = ''.join(pieces)
        if text.strip():
            paragraphs.append(text)
    return paragraphs


def _expected(payload):
    texts, links = [], []
    profile = payload.get('profile', {})
    texts.extend(str(profile[k]) for k in ('name', 'headline', 'email', 'phone', 'location', 'summary') if profile.get(k))
    for link in profile.get('links', []):
        if link.get('url'):
            links.append(link['url'])
    for group in payload.get('sections', []):
        if group.get('title'):
            texts.append(group['title'])
        for entry in group.get('entries', []):
            texts.extend(str(entry[k]) for k in ('title', 'organization', 'role', 'start', 'end', 'summary') if entry.get(k))
            texts.extend(entry.get('bullets', []))
            if entry.get('url'):
                links.append(entry['url'])
    return texts, links


def check_outputs(docx_path, pdf_path=None, payload=None, render_dir=None):
    docx = Path(docx_path).resolve()
    report = {'ok': False, 'docx_path': str(docx), 'pdf_path': str(Path(pdf_path).resolve()) if pdf_path else None,
              'issues': [], 'warnings': [], 'dual_delivery': False, 'visual_review_required': True,
              'visual_review_status': 'pending', 'rendered_pages': [], 'page_count': None}
    def issue(code, message, severity='error', **data):
        report['issues'].append({'code': code, 'message': message, 'severity': severity, **data})
    if not docx.is_file():
        issue('docx_missing', 'Word 文件不存在'); return report
    try:
        document = Document(docx)
        # Displayed text includes tables, hyperlink labels, headers, and footers.
        with ZipFile(docx) as archive:
            from xml.etree import ElementTree
            parts = [n for n in archive.namelist() if re.fullmatch(r'word/(document|header\d+|footer\d+)\.xml', n)]
            roots = {name: ElementTree.fromstring(archive.read(name)) for name in parts}
            paragraphs = [text for root in roots.values() for text in _visible_paragraphs(root)]
            text = '\n'.join(paragraphs)
            body = roots['word/document.xml']
            word = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
            if any(body.find('.//' + word + tag) is not None for tag in ('ins', 'del')):
                issue('tracked_changes', 'Word 中仍有修订；请确认最终文本')
            if 'word/comments.xml' in archive.namelist():
                issue('comments', 'Word 中仍有批注；请核对是否可交付')
        story_parts = {('/' + name) for name in parts}
        links = [relation.target_ref for part in document.part.package.parts
                 if str(part.partname) in story_parts
                 for relation in part.rels.values()
                 if relation.is_external and 'hyperlink' in relation.reltype]
        report['source_sha256'] = _hash(docx)
        report['docx_text'] = text
        report['docx_links'] = links
        for placeholder in re.findall(r'\{\{[^{}]+\}\}|\$\{[^{}]+\}|<<[^<>]+>>|\[(?:待填写|填写|姓名|邮箱|电话|TODO)[^\]]*\]', text, re.I):
            issue('placeholder', 'Word 中有未替换的占位符', value=placeholder)
        for url in links:
            parsed = urlparse(url)
            if parsed.scheme not in ('https', 'http', 'mailto') or (parsed.scheme != 'mailto' and not parsed.netloc):
                issue('invalid_link', 'Word 链接格式无效', value=url)
        expected, expected_links = _expected(payload or {})
        for item in expected:
            if _normalized(item) not in _normalized(text):
                issue('missing_content', 'Word 缺少预期内容', value=item)
        expected_numbers = set(re.findall(r'\d+(?:[.,]\d+)*%?', ' '.join(expected)))
        actual_numbers = set(re.findall(r'\d+(?:[.,]\d+)*%?', text))
        for number in sorted(expected_numbers - actual_numbers):
            issue('missing_number', 'Word 缺少预期数字', value=number)
        for link in expected_links:
            if link not in links:
                issue('missing_link', 'Word 缺少预期可点击链接', value=link)
    except Exception as error:
        issue('docx_unreadable', 'Word 文件无法读取：' + type(error).__name__); return report
    if pdf_path:
        pdf = Path(pdf_path).resolve()
        if not pdf.is_file():
            issue('pdf_missing', 'PDF 文件不存在')
        else:
            try:
                from pypdf import PdfReader
                reader = PdfReader(pdf)
                page_text = [page.extract_text() or '' for page in reader.pages]
                pdf_text = '\n'.join(page_text)
                report['page_count'] = len(reader.pages)
                report['pdf_sha256'] = _hash(pdf)
                report['pdf_text'] = pdf_text
                for number, item in enumerate(page_text, 1):
                    if not item.strip():
                        issue('pdf_no_text', 'PDF 页面无可提取文字；不能确认内容完整', page=number)
                if '\ufffd' in pdf_text:
                    issue('pdf_encoding', 'PDF 包含无法解码的字符')
                # PDF page headers, footers and automatic list markers can
                # interrupt the XML part order. Check each displayed paragraph
                # when no fact payload is available, without dropping content.
                for item in expected or paragraphs:
                    if _normalized(item) not in _normalized(pdf_text):
                        issue('pdf_missing_content', 'PDF 缺少 Word/资料中的内容', value=item)
                pdf_numbers = set(re.findall(r'\d+(?:[.,]\d+)*%?', pdf_text))
                for number in sorted(expected_numbers - pdf_numbers):
                    issue('pdf_missing_number', 'PDF 缺少预期数字', value=number)
                pdf_links = []
                for page in reader.pages:
                    for ref in page.get('/Annots', []):
                        annotation = ref.get_object()
                        action = annotation.get('/A')
                        if action:
                            action = action.get_object()
                            if action.get('/URI'):
                                pdf_links.append(str(action['/URI']))
                report['pdf_links'] = pdf_links
                for link in expected_links or links:
                    if link not in pdf_links:
                        issue('pdf_missing_link', 'PDF 缺少 Word 中的链接', value=link)
                limit = (payload or {}).get('target', {}).get('page_limit')
                if limit and len(reader.pages) > int(limit):
                    issue('page_limit', '页数超出偏好；请精简或允许更多页面，不会自动缩字号', actual=len(reader.pages), preferred=int(limit))
                sidecar = pdf.with_suffix(pdf.suffix + '.source.json')
                if sidecar.exists():
                    binding = json.loads(sidecar.read_text(encoding='utf-8'))
                    report['provenance'] = binding
                    if binding.get('source_sha256') != report['source_sha256'] or binding.get('pdf_sha256') != report['pdf_sha256']:
                        issue('stale_pdf', 'PDF 与当前 Word/导出记录不一致，请重新导出')
                else:
                    issue('unbound_pdf', '没有同源导出记录，无法确认 PDF 来自当前最终 Word')
                if render_dir:
                    import pypdfium2
                    folder = Path(render_dir).resolve(); folder.mkdir(parents=True, exist_ok=True)
                    with pypdfium2.PdfDocument(pdf) as rendered:
                        for index in range(len(rendered)):
                            page = rendered[index]
                            bitmap = page.render(scale=1.5)
                            image = bitmap.to_pil()
                            destination = folder / f'page-{index + 1:03d}.png'
                            if destination.exists():
                                raise FileExistsError('页面图片已存在，请使用新的 render_dir')
                            image.save(destination)
                            report['rendered_pages'].append({'page': index + 1, 'path': str(destination),
                                                             'width': image.width, 'height': image.height})
                            image.close(); bitmap.close(); page.close()
            except Exception as error:
                issue('pdf_unreadable', 'PDF 读取或页面渲染失败：' + type(error).__name__)
    report['ok'] = not any(x['severity'] == 'error' for x in report['issues'])
    report['dual_delivery'] = bool(pdf_path and report['ok'])
    report['warnings'].append('自动检查不能判断裁切、重叠或视觉布局；需查看渲染页后记录审阅')
    return report
