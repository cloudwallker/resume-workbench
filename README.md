# Resume Workbench

### A Codex skill for editable resumes built from real experience

**Turn your experience, existing resume, and optional public GitHub projects into an editable Word resume and a PDF exported from that Word. Adapt the content to a job description, use a DOCX/PDF layout reference, or continue from your latest manually edited Word file.**

English | [中文](README_ZH.md)

[Quick Start](#quick-start) · [Features](#features) · [Usage](#usage) · [Documentation](#documentation)

<img src="docs/images/resume-example.png" alt="A one-page Chinese operations resume generated from fictional example data" width="550">

*A fictional Chinese operations resume, rendered from the generated Word file through its PDF export. This is an actual example output.*

## Features

- **Confirmed experience first.** Keep facts, sources, job-specific choices, and templates separate. Template samples are never treated as your experience, and repository ownership does not establish your contribution.
- **Flexible inputs.** Start with your description, an existing resume, or optional public GitHub evidence. Chinese and English examples cover a student, an operations applicant, and an experienced professional.
- **Job-specific versions.** Explain relevant experience and gaps from a job description. Select the experience to include explicitly; a job description is optional.
- **Editable Word plus its PDF.** Use the default layout, ordinary DOCX paragraphs/simple tables, or reconstruct a text-layer PDF reference as Word. Report unsupported layout elements and reconstruction differences.
- **Continue from your latest Word.** Edit a copy without requiring version history, preserve the original, and export a new PDF from the edited Word.

The workflow supports different industries and career stages; it does not require a technical project or a GitHub account.

## Quick Start

### 1. Prepare the environment

Python 3.10+ is required. PDF export needs Windows Microsoft Word in a working desktop session or an available LibreOffice installation. The Windows Word path has been exercised with real files; LibreOffice and other operating systems have not received the same end-to-end validation.

```powershell
git clone https://github.com/cloudwallker/resume-workbench.git
cd resume-workbench
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe skills/resume-workbench/scripts/resume.py doctor
```

On macOS/Linux, use `.venv/bin/python` for the environment commands. Codex desktop may also provide a bundled document runtime; the skill checks for that runtime before preparing a separate environment.

### 2. Install the Codex skill

Copy the entire `skills/resume-workbench` directory into your personal Codex skills directory, for example `~/.codex/skills/resume-workbench`. Preserve an existing installation before replacing it. Start a new Codex conversation after installation and invoke:

```text
$resume-workbench Create a Word and PDF resume from my experience and target role.
```

Personal facts, imported originals, and generated files belong in a separate working directory, never inside the skill package or public examples.

### 3. Try the fictional example

```powershell
.\.venv\Scripts\python.exe skills/resume-workbench/scripts/resume.py build --master skills/resume-workbench/assets/examples/operations-zh.json --outdir output --workspace workspaces/demo
```

The command creates a new version directory containing Word, PDF when conversion succeeds, and verification reports. Inspect every rendered PDF page before treating the files as reviewed. If you explicitly want Word only, add `--docx-only`; without a converter, the default dual-format request returns `partial` and retains the Word file.

## Usage

The examples below use `python` from the prepared environment. See `--help` for every command and its arguments.

```text
python skills/resume-workbench/scripts/resume.py --help
python skills/resume-workbench/scripts/resume.py validate master.json
python skills/resume-workbench/scripts/resume.py tailor --master master.json --jd JD.txt
python skills/resume-workbench/scripts/resume.py github octocat/Hello-World
python skills/resume-workbench/scripts/resume.py analyze-template template.docx
```

`tailor` supplies explainable recommendations; it does not modify facts or select experience automatically. Use repeated `--select <id>` arguments when building a selected version. GitHub retrieval reads public API/README material without running repository code; its findings remain pending until personal contributions are confirmed. No universal ATS score or hiring outcome is promised.

### Templates

```text
python skills/resume-workbench/scripts/resume.py build --master master.json --template template.docx --mapping mapping.json --outdir output
python skills/resume-workbench/scripts/resume.py build --master master.json --template reference.pdf --allow-rebuild --outdir output
```

Ordinary DOCX paragraphs and simple tables support placeholders, recognized headings, and explicit mappings. A text-layer PDF supplies layout measurements for an editable Word reconstruction; it is not a lossless PDF-to-Word conversion. Scanned PDFs need an OCR-processed or editable source: this project reports `needs_ocr` rather than providing an integrated OCR workflow. Floating text boxes, nested/merged tables, and other complex layouts need inspection and adaptation. Legacy `.doc` files can be converted to a new DOCX when a converter is available.

### Continue and check

```text
python skills/resume-workbench/scripts/resume.py continue --latest latest.docx --replacements changes.json --outdir output
python skills/resume-workbench/scripts/resume.py export --docx final.docx --outdir preview
python skills/resume-workbench/scripts/resume.py check --docx resume.docx --pdf resume.pdf --payload payload.json --render-dir pages
```

Use the latest Word as the source for continued editing, including manual changes. `export` copies that Word unchanged and converts it to PDF; it is also useful for an internal layout preview when only Word is requested.

Automatic checks cover text, numbers, links, placeholders, source hashes, and PDF readability/page count. A successful PDF export returns `needs_visual_review`, which still requires viewing every page. Other states include `docx_only`, `partial`, and `quality_failed`; exit code `2` signals an error or a missing requirement. Review records bind to the current file hashes and become stale after a change.

## Documentation

- [Skill instructions](skills/resume-workbench/SKILL.md)
- [Data model](skills/resume-workbench/references/data-model.md)
- [Experience writing and job tailoring](skills/resume-workbench/references/content-and-targeting.md)
- [Template mapping and reconstruction](skills/resume-workbench/references/templates.md)
- [Export and file verification](skills/resume-workbench/references/files-and-export.md)
- [Continuing from Word](skills/resume-workbench/references/continuation.md)
- [Verification and reproducible checks](docs/verification.md)

The detailed skill references are currently in Chinese. All bundled applicant examples are fictional.

## Development and local packaging

```text
python tools/run_tests.py
python tools/build_release.py --outdir dist
python tools/install_skill.py dist/resume-workbench-0.1.0.zip --skills-dir "<personal Codex skills directory>"
```

Build the ZIP locally before using the ZIP installer. The installer checks archive paths and manifest hashes; `--backup-existing` preserves an existing skill during replacement. Packaging uses an explicit resource list and excludes personal workspaces, outputs, caches, and environment files. See [verification](docs/verification.md) for the unit suite and real Word/PDF scenarios.

## Contributor and license

Project contributor: [cloudwallker](https://github.com/cloudwallker).

License terms have not been specified; this repository currently contains no license file.
