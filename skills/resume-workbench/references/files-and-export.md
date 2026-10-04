# 环境 导出与检查

Python 3.10+。依赖：python-docx、pdfplumber、pypdf、pypdfium2、Pillow。优先 Codex 提供的依赖运行时。独立环境可在任务目录创建 venv，再安装本包 `requirements.txt`；不用修改系统 Python。

```text
python -m venv "<任务目录/.venv>"
<venv-python> -m pip install -r "$SKILL_DIR/requirements.txt"
<venv-python> "$SKILL_DIR/scripts/resume.py" --help
```

`doctor` 报告 Python 库、Windows Word、LibreOffice、OCR 情况。检测到 Word 文件不代表 COM 已可用。Word 必须在当前已登录桌面会话可启动；沙箱登录会话报 80070520 时，在授权的当前桌面会话执行相同脚本。不要结束用户已打开的 Word，不需打开可见窗口。

默认 build/continue 选 auto 后端，Word 或 LibreOffice 实际转换。macOS/Linux 使用可用 LibreOffice。没有后端时返回 partial，Word 留存；不要另造 PDF 伪称来自 Word。`--docx-only` 是用户明确只要 Word 的选择。OCR 缺失报告 needs_ocr，普通文字层 PDF 不需要 OCR。

每次输出目录含 Word、成功时的 PDF、JSON manifest、payload（构建时）、来源哈希记录和渲染页。若质量失败或导出失败，查看报告的 issues/recovery，修复后生成新版本，原件留存。

```text
python "$SKILL_DIR/scripts/resume.py" check --docx "<resume.docx>" --pdf "<resume.pdf>" --payload "<payload.json>" --render-dir "<页图目录>"
```

自动检查姓名/正文/数字/链接是否缺失、未替换占位符、PDF 可提取性、页数限制与来源哈希。自动检查不能识别全部自然语言事实或评价排版审美。必须用图像查看工具查看每一页，检查缺字、截断、文本重叠、标题孤行、空白页、错误字体，以及 PDF 重建差异。

只交付 Word 时，仍需检查布局。可用现有最终 Word 生成内部 PDF 预览，Word 副本与原件字节一致，预览无需作为额外交付发给用户：

```text
python "$SKILL_DIR/scripts/resume.py" export --docx "<最终.docx>" --outdir "<内部预览目录>"
```

复杂编辑由文档工具完成后，也可用 export 从该最终文件导出 PDF，再运行 check。转换或预览工具不可用时，报告视觉尚未核验，不以正文检查替代。

实际完成逐页查看后才运行：

```text
python "$SKILL_DIR/scripts/resume.py" check --docx "<resume.docx>" --pdf "<resume.pdf>" --payload "<payload.json>" --receipt "<新审阅记录.json>" --visual-reviewed "Codex" --notes "已查看全部页面；记录具体差异"
```

这条命令只记录审阅者声明，不自动执行视觉审阅。凭据绑定当前 Word/PDF 哈希；后续修改须重新导出和检查。最终把文件和限制真实交付，不输出“已经通过”来代替缺失文件。
