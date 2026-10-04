"""Convert the final Word source using Word or LibreOffice, preserving originals."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile


WORD_SCRIPT = r'''param(
    [Parameter(Mandatory=$true)][string]$InputPath,
    [Parameter(Mandatory=$true)][string]$OutputPath,
    [ValidateSet('pdf','docx')][string]$Format = 'pdf'
)
$ErrorActionPreference = 'Stop'
$word = $null
$document = $null
try {
    $word = New-Object -ComObject Word.Application
    $word.Visible = $false
    $word.DisplayAlerts = 0
    $word.AutomationSecurity = 3
    $document = $word.Documents.Open($InputPath, $false, $true, $false)
    if ($Format -eq 'pdf') {
        $document.ExportAsFixedFormat($OutputPath, 17)
    } else {
        $document.SaveAs2($OutputPath, 16)
    }
} finally {
    try {
        if ($null -ne $document) {
            # Windows PowerShell 5 binds the SaveChanges VARIANT by reference.
            $documentSaveChanges = [object]0
            try { $document.Close([ref]$documentSaveChanges) } finally {
                [void][System.Runtime.InteropServices.Marshal]::FinalReleaseComObject($document)
            }
        }
    } finally {
        if ($null -ne $word) {
            $applicationSaveChanges = [object]0
            try { $word.Quit([ref]$applicationSaveChanges) } finally {
                [void][System.Runtime.InteropServices.Marshal]::FinalReleaseComObject($word)
            }
        }
    }
}
'''


def _hash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _libreoffice():
    return shutil.which('libreoffice') or shutil.which('soffice')


def _word_registered():
    if os.name != 'nt':
        return False
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, r'Word.Application\CLSID'):
            return True
    except OSError:
        return False


def doctor():
    word, libreoffice = _word_registered(), _libreoffice()
    dependencies = {name: importlib.util.find_spec(name) is not None
                    for name in ('docx', 'pdfplumber', 'pypdf', 'pypdfium2', 'PIL')}
    return {'ok': all(dependencies.values()), 'dependencies': dependencies,
            'backends': {'word': {'available': word, 'note': '已注册不代表当前权限能创建 COM；转换时验证'},
                         'libreoffice': {'available': bool(libreoffice), 'path': libreoffice}},
            'pdf_available': word or bool(libreoffice), 'ocr_available': bool(shutil.which('tesseract'))}


def _word(source, target, kind, temp):
    script = Path(temp) / 'word-export.ps1'
    script.write_text(WORD_SCRIPT, encoding='utf-8-sig')
    executable = shutil.which('powershell.exe') or 'powershell.exe'
    subprocess.run([executable, '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass',
                    '-File', str(script), '-InputPath', str(source), '-OutputPath', str(target),
                    '-Format', kind], check=True, capture_output=True, timeout=180,
                   creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))


def _lo(source, target, kind, temp):
    executable = _libreoffice()
    if not executable:
        raise OSError('LibreOffice 转换程序不可用')
    converted = Path(temp) / 'converted'
    converted.mkdir()
    config = (Path(temp) / 'lo-profile').resolve().as_uri()
    subprocess.run([executable, '-env:UserInstallation=' + config, '--headless', '--norestore',
                    '--convert-to', kind, '--outdir', str(converted), str(source)],
                   check=True, capture_output=True, timeout=180,
                   creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    produced = converted / (source.stem + '.' + kind)
    if not produced.is_file():
        raise OSError('转换器未生成所需文件')
    shutil.copyfile(produced, target)


def _convert(source_path, target_path, kind, backend):
    source, target = Path(source_path).resolve(), Path(target_path).resolve()
    base = {'ok': False, 'source': str(source), 'path': str(target), 'backend': backend,
            'recovery': '保留原 Word；请在允许 Word COM 的环境重试或使用可用 LibreOffice 后端'}
    if not source.is_file():
        return {**base, 'error': '输入文件不存在'}
    if target.exists():
        return {**base, 'error': '输出文件已存在；请使用新文件名'}
    if source == target:
        return {**base, 'error': '输入与输出不能相同'}
    selected = backend
    if backend == 'auto':
        selected = 'word' if _word_registered() else 'libreoffice' if _libreoffice() else None
    if selected not in ('word', 'libreoffice'):
        return {**base, 'error': '没有可用或支持的转换后端'}
    base['backend'] = selected
    source_hash = _hash(source)
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='resume-export-') as temp:
            staging = Path(temp) / ('result.' + kind)
            (_word if selected == 'word' else _lo)(source, staging, kind, temp)
            if not staging.is_file() or not staging.stat().st_size:
                raise OSError('转换器未生成有效文件')
            if _hash(source) != source_hash:
                raise OSError('转换期间源文件变化，请从最终 Word 重新导出')
            if kind == 'pdf':
                with staging.open('rb') as stream:
                    if stream.read(5) != b'%PDF-':
                        raise ValueError('转换器输出不是 PDF')
                from pypdf import PdfReader
                if not PdfReader(staging).pages:
                    raise OSError('PDF 没有页面')
            else:
                from docx import Document
                Document(staging)
            with target.open('xb') as stream, staging.open('rb') as reader:
                shutil.copyfileobj(reader, stream)
        result = {**base, 'ok': True, 'source_sha256': source_hash,
                  kind + '_path': str(target), 'output_sha256': _hash(target)}
        result.pop('recovery', None)
        if kind == 'pdf':
            result['pdf_sha256'] = result['output_sha256']
            target.with_suffix(target.suffix + '.source.json').write_text(
                json.dumps({k: result[k] for k in ('source', 'source_sha256', 'pdf_sha256', 'backend')},
                           ensure_ascii=False, indent=2), encoding='utf-8')
        return result
    except Exception as error:
        # Do not echo process stderr: Office diagnostics can contain private input text.
        return {**base, 'error': '转换失败：' + type(error).__name__,
                'source_sha256': source_hash, 'partial_output': str(target) if target.exists() else None}


def convert_to_pdf(docx_path, pdf_path, backend='auto'):
    if Path(docx_path).suffix.lower() != '.docx' or Path(pdf_path).suffix.lower() != '.pdf':
        return {'ok': False, 'error': '需要 .docx 输入与 .pdf 输出', 'recovery': '检查文件扩展名并重试'}
    return _convert(docx_path, pdf_path, 'pdf', backend)


def convert_legacy_doc(path, output_path):
    if Path(path).suffix.lower() != '.doc' or Path(output_path).suffix.lower() != '.docx':
        return {'ok': False, 'error': '需要 .doc 输入与 .docx 输出', 'recovery': '保留原件并检查文件扩展名'}
    return _convert(path, output_path, 'docx', 'auto')
