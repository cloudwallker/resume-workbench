#!/usr/bin/env python3
"""Local resume file workflow. Run --help for commands; reports are UTF-8 JSON."""
import argparse
import hashlib
import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

from rw import __version__


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def write_json(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def new_directory(parent):
    parent = Path(parent).resolve()
    parent.mkdir(parents=True, exist_ok=True)
    # Windows Python's mkdtemp uses an owner-only ACL. Sandbox and desktop
    # Word may run with different tokens, so inherit the user's workspace ACL.
    for _ in range(100):
        directory = parent / ('resume-' + uuid.uuid4().hex[:16])
        try:
            directory.mkdir()
            return directory
        except FileExistsError:
            continue
    raise OSError('Unable to create a unique output directory.')


def finish_document(args, directory, result, payload=None):
    from rw.exporting import convert_to_pdf
    from rw.quality import check_outputs
    docx = directory / 'resume.docx'
    pdf = directory / 'resume.pdf'
    result['docx'] = str(docx)
    result['pdf'] = None
    if not result.get('document', {}).get('ok'):
        result['status'] = 'failed'
        write_json(directory / 'manifest.json', result)
        return result, 2
    if args.docx_only:
        result['conversion'] = {'ok': False, 'backend': None, 'reason': 'Explicit DOCX-only request.'}
        result['status'] = 'docx_only'
    else:
        conversion = convert_to_pdf(docx, pdf, backend=args.backend)
        result['conversion'] = conversion
        if conversion.get('ok'):
            result['pdf'] = str(pdf)
            result['status'] = 'needs_visual_review'
        else:
            result['status'] = 'partial'
    result['quality'] = check_outputs(docx, pdf if result['pdf'] else None, payload, directory / 'pages')
    if not result['quality'].get('ok'):
        result['status'] = 'quality_failed'
    if payload is not None:
        write_json(directory / 'payload.json', payload)
    result['docx_sha256'] = sha256(docx)
    result['visual_review_required'] = True
    if result['pdf']:
        result['pdf_sha256'] = sha256(pdf)
    result['manifest'] = str(directory / 'manifest.json')
    write_json(directory / 'manifest.json', result)
    if getattr(args, 'workspace', None):
        from rw.workspace import save_version
        result['version'] = save_version(args.workspace, payload or {}, {
            'operation': result['operation'], 'manifest': result['manifest'],
            'docx_sha256': result['docx_sha256'], 'status': result['status']})
        write_json(directory / 'manifest.json', result)
    return result, 0 if result['status'] in ('docx_only', 'needs_visual_review') else 2


def build(args):
    from rw.core import validate_master, materialize_resume
    from rw.rendering import render_docx
    from rw.templates import analyze_template, adapt_docx, pdf_layout_profile
    master = read_json(args.master)
    issues = validate_master(master)
    selected = args.select
    recommendation = None
    if args.jd:
        from rw.targeting import recommend_experiences
        recommendation = recommend_experiences(master, Path(args.jd).read_text(encoding='utf-8-sig'), args.limit)
        # Recommendations are reviewable advice. Selection remains explicit.
    payload = materialize_resume(master, selected_ids=selected, strict=True)
    directory = new_directory(args.outdir)
    result = {'operation': 'build', 'version': __version__, 'created_at': datetime.now(timezone.utc).isoformat(),
              'validation': issues, 'recommendation': recommendation, 'directory': str(directory)}
    layout = None
    if args.template:
        template = Path(args.template).resolve()
        analysis = analyze_template(template)
        result['template'] = analysis
        if template.suffix.lower() == '.pdf':
            if not args.allow_rebuild:
                result.update(status='template_mapping_required', error='PDF is a layout reference. Use --allow-rebuild after reviewing the reconstruction differences.')
                write_json(directory / 'manifest.json', result)
                return result, 2
            layout_report = pdf_layout_profile(template)
            result['layout'] = layout_report
            if layout_report.get('needs_ocr') or layout_report.get('requires_ocr') or layout_report.get('ok') is False:
                result.update(status='needs_ocr', error='PDF has no usable text/layout. Provide a text-layer PDF or a DOCX template.')
                write_json(directory / 'manifest.json', result)
                return result, 2
            result['document'] = render_docx(payload, directory / 'resume.docx', layout_report.get('layout', layout_report))
        elif template.suffix.lower() == '.docx':
            mapping = read_json(args.mapping) if args.mapping else None
            result['document'] = adapt_docx(template, payload, directory / 'resume.docx', mapping)
        else:
            result.update(status='unsupported_template', error='Convert legacy DOC to DOCX with import first. Templates must be DOCX or text-layer PDF.')
            write_json(directory / 'manifest.json', result)
            return result, 2
    else:
        result['document'] = render_docx(payload, directory / 'resume.docx')
    return finish_document(args, directory, result, payload)


def continue_resume(args):
    from rw.continuation import continue_docx
    latest = args.latest or args.latest_path
    if not latest:
        raise ValueError('Continue requires --latest <latest.docx> or a positional Word path.')
    if args.latest and args.latest_path:
        raise ValueError('Specify the latest Word path only once.')
    directory = new_directory(args.outdir)
    changes = read_json(args.replacements) if args.replacements else None
    result = {'operation': 'continue', 'directory': str(directory),
              'document': continue_docx(latest, directory / 'resume.docx', changes)}
    return finish_document(args, directory, result)


def export_existing(args):
    from rw.continuation import continue_docx
    directory = new_directory(args.outdir)
    result = {'operation': 'export', 'directory': str(directory),
              'document': continue_docx(args.docx, directory / 'resume.docx')}
    return finish_document(args, directory, result)


def check(args):
    from rw.quality import check_outputs
    payload = read_json(args.payload) if args.payload else None
    result = check_outputs(args.docx, args.pdf, payload, args.render_dir)
    if args.visual_reviewed:
        if not result.get('ok') or not args.pdf:
            raise ValueError('Visual review receipt requires passing checks and an existing PDF.')
        if not args.receipt:
            raise ValueError('--visual-reviewed requires --receipt to preserve the reviewer record.')
        receipt = {'reviewer': args.visual_reviewed, 'reviewed_at': datetime.now(timezone.utc).isoformat(),
                   'docx_sha256': sha256(args.docx), 'pdf_sha256': sha256(args.pdf),
                   'page_count': result.get('page_count'), 'notes': args.notes,
                   'assertion': 'Reviewer inspected every rendered page.'}
        destination = Path(args.receipt)
        if destination.exists():
            raise ValueError('Receipt exists; use a new path to preserve the audit record.')
        write_json(destination, receipt)
        result['visual_review_receipt'] = str(destination.resolve())
    return result, 0 if result.get('ok') else 2


def parser():
    p = argparse.ArgumentParser(description='Resume Workbench: editable Word and its PDF, with evidence and template checks.')
    p.add_argument('--version', action='version', version=__version__)
    sub = p.add_subparsers(dest='command', required=True)
    sub.add_parser('doctor', help='Report dependency and conversion capabilities.')
    a = sub.add_parser('init', help='Create a local personal workspace.'); a.add_argument('path')
    a = sub.add_parser('validate', help='Validate a master fact file.'); a.add_argument('master')
    a = sub.add_parser('import', help='Inspect DOCX/PDF; convert legacy DOC if possible.')
    a.add_argument('path'); a.add_argument('--purpose', choices=['resume', 'template', 'both'], default='resume'); a.add_argument('--converted-docx')
    a = sub.add_parser('analyze-template'); a.add_argument('path')
    a = sub.add_parser('tailor', help='Explain JD requirements and candidate experience recommendations.')
    a.add_argument('--master', required=True); a.add_argument('--jd', required=True); a.add_argument('--limit', type=int, default=3)
    a = sub.add_parser('github', help='Read public repository evidence without running repository code.')
    a.add_argument('identifier'); a.add_argument('--limit', type=int, default=8)
    a = sub.add_parser('build', help='Build from confirmed facts; recommended IDs require explicit selection.')
    a.add_argument('--master', required=True); a.add_argument('--template'); a.add_argument('--mapping')
    a.add_argument('--allow-rebuild', action='store_true'); a.add_argument('--jd'); a.add_argument('--limit', type=int, default=3)
    a.add_argument('--select', action='append'); a.add_argument('--workspace')
    document_options(a)
    a = sub.add_parser('export', help='Export an unchanged copy of an existing final Word; also useful for internal previews.')
    a.add_argument('--docx', required=True)
    document_options(a)
    a = sub.add_parser('continue', help='Edit a copy of the latest Word file, even without history.')
    a.add_argument('latest_path', nargs='?'); a.add_argument('--latest'); a.add_argument('--replacements'); a.add_argument('--workspace')
    document_options(a)
    a = sub.add_parser('check', help='Check files, render PDF pages, and optionally record completed human/agent review.')
    a.add_argument('--docx', required=True); a.add_argument('--pdf'); a.add_argument('--payload'); a.add_argument('--render-dir')
    a.add_argument('--receipt'); a.add_argument('--visual-reviewed', metavar='REVIEWER'); a.add_argument('--notes', default='')
    return p


def document_options(p):
    p.add_argument('--outdir', required=True)
    p.add_argument('--backend', choices=['auto', 'word', 'libreoffice', 'none'], default='auto')
    p.add_argument('--docx-only', action='store_true', help='Explicitly request only Word; no dual delivery claim.')


def dispatch(args):
    if args.command == 'doctor':
        from rw.exporting import doctor
        return doctor(), 0
    if args.command == 'init':
        from rw.workspace import initialize_workspace
        return initialize_workspace(args.path), 0
    if args.command == 'validate':
        from rw.core import validate_master
        issues = validate_master(read_json(args.master))
        ok = not any(i.get('severity') in ('error', 'blocking') for i in issues)
        return {'ok': ok, 'issues': issues}, 0 if ok else 2
    if args.command == 'import':
        from rw.importing import inspect_input
        if Path(args.path).suffix.lower() == '.doc':
            from rw.exporting import convert_legacy_doc
            if not args.converted_docx:
                raise ValueError('Legacy DOC requires --converted-docx pointing to a new DOCX path.')
            conversion = convert_legacy_doc(args.path, args.converted_docx)
            if not conversion.get('ok'):
                return {'ok': False, 'conversion': conversion}, 2
            inspection = inspect_input(args.converted_docx, args.purpose)
            return {'conversion': conversion, 'inspection': inspection}, 0 if inspection.get('ok') else 2
        inspection = inspect_input(args.path, args.purpose)
        return inspection, 0 if inspection.get('ok') else 2
    if args.command == 'analyze-template':
        from rw.templates import analyze_template
        analysis = analyze_template(args.path)
        return analysis, 0 if analysis.get('ok') else 2
    if args.command == 'tailor':
        from rw.targeting import recommend_experiences
        return recommend_experiences(read_json(args.master), Path(args.jd).read_text(encoding='utf-8-sig'), args.limit), 0
    if args.command == 'github':
        from rw.github import collect_github
        result = collect_github(args.identifier, args.limit)
        return result, 0 if result.get('ok') else 2
    if args.command == 'build':
        return build(args)
    if args.command == 'continue':
        return continue_resume(args)
    if args.command == 'export':
        return export_existing(args)
    return check(args)


def main():
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8')
    args = parser().parse_args()
    try:
        report, status = dispatch(args)
    except (ValueError, OSError, KeyError, TypeError, json.JSONDecodeError) as exc:
        # Only local data errors are printed. Network providers redact their own errors.
        report, status = {'ok': False, 'error': str(exc), 'operation': args.command}, 2
    except Exception as exc:
        # Parser/provider exceptions may carry document text. Return type only.
        report, status = {'ok': False, 'error': 'Input or dependency failure: ' + type(exc).__name__,
                          'operation': args.command, 'recovery': 'Check input format and run doctor; preserve the original file.'}, 2
    print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
    return status


if __name__ == '__main__':
    raise SystemExit(main())
