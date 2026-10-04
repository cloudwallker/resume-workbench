# Verification / 验证说明

[English README](../README.md) | [中文说明](../README_ZH.md)

The initial version passed **113 unittest checks**. Real Windows Word conversion and page-by-page visual review were also completed for **13 Word/PDF pairs**. The examples were fictional. Coverage included Chinese operations, a technical student, an experienced English applicant, explicit JD selection, paragraph and simple-table DOCX templates, text-layer PDF reconstruction, continuation with and without history, packaged defaults, and links.

首版通过 **113 项 unittest 检查**，并完成 **13 份 Word/PDF 文件对**的真实 Windows Word 转换和逐页视觉审阅。全部使用虚构资料，覆盖中文运营、技术学生、英文有经验求职者、显式 JD 筛选、段落与简单表格模板、文字层 PDF 重建、有/无历史续编、内置模板和链接。

These results describe the exercised version and environment, not a guarantee for every imported document. LibreOffice, macOS/Linux, integrated OCR, and arbitrary complex templates have not received equivalent end-to-end validation. A generated file still needs its own review.

这些结果对应已实测的版本与环境，不代表任意导入文件都能无损适配。LibreOffice、macOS/Linux、集成 OCR 和任意复杂模板尚未完成同等程度的端到端验证；每份新文件仍须独立审阅。

## Reproduce the unit suite / 复现单元测试

Prepare Python 3.10+ and the repository requirements first. Run from the repository root:

先准备 Python 3.10+ 并安装仓库依赖，然后在仓库根目录运行：

```text
python -m pip install -r requirements.txt
python tools/run_tests.py
```

The runner uses Python's unittest module. The suite checks fact validation, source separation, selection, template mapping, Word continuation, export/quality rules, packaging, and safe installation behavior. Conversion-specific tests use controlled fixtures or mocks; passing the suite alone does not prove a Word/LibreOffice installation works.

测试运行器使用 Python 标准库 unittest。覆盖事实校验、来源分离、经历选择、模板映射、Word 续编、导出/质量规则、打包和安装恢复。部分转换测试使用受控样例或模拟对象，单元测试通过不能证明本机 Word/LibreOffice 能实际转换。

## Real Word/PDF scenarios / 真实文件场景

```text
python skills/resume-workbench/scripts/resume.py doctor
python tools/run_acceptance.py
```

`run_acceptance.py` explicitly uses the **Windows Word backend**. Run it in a desktop session where Word can open documents. It creates a new `output/acceptance/` directory for every run, with an `index.json` and individual reports. The public GitHub scenario also needs network access. The script tests unavailable conversion and unreadable scanned PDF handling as expected failures; it does not install OCR.

`run_acceptance.py` 明确使用 **Windows Word 后端**，应在 Word 能打开文档的桌面会话中运行。每次生成新的 `output/acceptance/` 目录，包含 `index.json` 和各场景报告。公开 GitHub 场景还需要网络访问。脚本也检查转换器缺失和扫描 PDF 无可用文字时的预期失败，不会安装 OCR。

The script exercises a reproducible core subset of the 13 reviewed file pairs. Additional defaults and hyperlink cases can be generated through the CLI. The script leaves visual review pending: `needs_visual_review` means the PDF exists and automatic checks passed, **not** that the layout has been inspected.

该脚本复现 13 份已审阅文件中的核心场景，不会一次生成全部 13 份。内置模板和链接等补充场景可通过 CLI 构建。脚本保留待审阅状态：`needs_visual_review` 表示 PDF 已生成且自动检查通过，**不代表**已检查版式。

## Review each new file / 审阅每份新文件

Use the generated report's actual paths in this command:

将生成报告中的真实文件路径代入：

```text
python skills/resume-workbench/scripts/resume.py check --docx "<resume.docx>" --pdf "<resume.pdf>" --payload "<payload.json>" --render-dir "<new-pages-directory>"
```

View every page and check missing characters, clipping, overlap, empty trailing pages, sample leftovers, readability, dates, numbers, links, and any template reconstruction differences. Omit `--payload` when checking a continuation/export that has no payload. Use a new page directory instead of overwriting earlier review artifacts.

逐页检查缺字、截断、重叠、空白尾页、样例残留、可读性、日期、数字、链接及模板重建差异。续编/导出没有 payload 时省略 `--payload`。使用新的页图目录，保留此前的检查文件。

Only after completing that review, record a receipt with `check --receipt "<new-review.json>" --visual-reviewed "<reviewer>" --notes "<findings>"` alongside the file arguments. This records a review statement and binds it to current hashes; it does not perform the visual review automatically. Any file change requires a new export and review.

实际完成查看后，才能在文件参数之外添加 `check --receipt "<新审阅记录.json>" --visual-reviewed "<审阅者>" --notes "<检查结果>"` 记录凭据。命令只保存审阅声明并绑定当前哈希，不会自动进行视觉审阅。文件发生变化后，需要重新导出和检查。
