---
name: resume-workbench
description: "制作、定制或续编求职简历，默认交付可编辑 Word 和 PDF。适用于用户描述经历、导入旧简历或 PDF/Word 模板、从公开 GitHub 项目挑选素材，以及依据岗位 JD 调整不同职业阶段和行业的简历。"
---

# Resume Workbench

帮助用户把真实经历写成适合目标岗位的简历。你负责追问、归纳和表达，配套脚本负责资料校验、模板处理与文件导出。默认交付可编辑 `.docx` 和从该 Word 导出的 `.pdf`，并保留可续编的资料。使用用户语言沟通；内容语言和投递地区依据用户需求。

## 开始任务

1. 优先阅读用户已经给出的经历、文件、JD 与要求；不要重新索取已有信息。
2. 确认目标岗位/方向、内容语言、职业阶段、文件用途。无 JD 可按方向生成通用版；不强制用户提供 GitHub。
3. 最多一次问一个当前最关键的缺口，在不依赖回答的部分继续整理。用户要快速初稿时，用已知事实制作并列出尚缺资料。
4. 如果用户已有最新 Word，要求“改一下”“继续编辑”，直接走续编流程；不要用历史 JSON 重排覆盖手工修改。
5. 在用户指定目录建立资料工作区；未指定时在当前工作区使用独立目录。个人资料、模板原件和输出放在工作区，禁止写进 skill 目录或公开示例。

先运行能力检查。本文中 `$SKILL_DIR` 指本 SKILL.md 所在目录，替换为实际绝对路径；使用工具参数传递路径，不把用户文本拼接进 shell 命令。

```text
python "$SKILL_DIR/scripts/resume.py" doctor
python "$SKILL_DIR/scripts/resume.py" init "<工作区>"
```

Codex 桌面如提供 `load_workspace_dependencies`，先发现其 Python 和文档依赖；否则使用用户环境的 Python 3.10+。缺少依赖时按 [文件工作流](references/files-and-export.md) 在任务目录准备环境。doctor 只检测安装情况；真实转换才证明 Word/LibreOffice 可用。

## 整理事实与文案

阅读 [数据格式](references/data-model.md) 和 [经历写作](references/content-and-targeting.md)。创建 UTF-8 `master.json`：个人信息、目标、来源与经历分开记录，经历和 bullet 使用稳定 id。只保留用户需要的联系方式。

- 个人叙述可标为用户确认；旧简历内容先待核对，模板样例永远只是样例。来源说明不能写成独立核证。
- 区分项目总体功能与个人职责，团队成果写清团队及个人参与。公开仓库、README、提交数或仓库归属不证明候选人的具体贡献。
- 已确认、待确认、冲突和缺失分别记录。不要编造学历、证书、任职日期、技术熟练度、管理人数或量化结果。
- 数字需记录统计范围和依据；estimated/unknown 指标不得进入投递稿。没有数字也可准确写清动作、对象和交付结果。
- 来源间有冲突时指出具体差异并追问；不要自行选较亮眼的版本。模板不能替用户补齐空白。
- 将素材归纳为明确职责与结果。避免“精通”“大幅提升”等没有依据的表述；不过度追问无关个人信息。

```text
python "$SKILL_DIR/scripts/resume.py" import "<旧简历.docx>" --purpose resume
python "$SKILL_DIR/scripts/resume.py" validate "<master.json>"
```

确认内容可以是持续对话中的用户陈述，不要求为了格式重复整份批准。脚本严格构建会阻断选中经历中未确认的事实；把待核对素材保留在经历库，选择已确认 id 生成投递稿。

## 项目和岗位筛选

GitHub 是可选资料来源，仅读公开 API/README，不运行仓库代码。导入结果全部是待确认素材，告诉用户值得写的项目与依据，再问具体贡献。账号没有可用仓库、限流或断网时改用用户描述，保留已整理内容。

```text
python "$SKILL_DIR/scripts/resume.py" github "<GitHub账号或仓库URL>" --limit 8
python "$SKILL_DIR/scripts/resume.py" tailor --master "<master.json>" --jd "<JD.txt>" --limit 3
```

把 JD 拆成职责、必要条件、优先条件和未知项，给出素材选择理由与缺口。脚本提供可解释的关键词辅助，不能把它当成招聘系统评分、资格证明或最终语义判断。根据上下文决定保留哪些经历，明确 `--select`，不偷偷修改事实、日期、归属或统计口径。无 JD 按目标方向组织栏目。学生可教育/项目优先，有经验者工作/成果优先，学术岗位可研究/教学/发表优先；按实际材料调整，不将技术项目作为所有行业的必填项。

## 导入模板

先阅读 [模板规则](references/templates.md)，检查输入用途：旧简历、版式模板或两者兼有。即使两者兼有，内容核对和布局提取仍分开。

```text
python "$SKILL_DIR/scripts/resume.py" import "<模板>" --purpose template
python "$SKILL_DIR/scripts/resume.py" analyze-template "<模板>"
```

- DOCX：优先占位符，其次普通标题段落和简单表格。跨 run 占位符也应完整替换。歧义或样例残留时建立显式映射，检查所有标题、表格、页眉页脚，原件保留。
- PDF：将有文字层 PDF 用作纸张、边距、字号、字体与配色参考，重建可编辑 Word。先向用户说明重建差异，若用户已明确要求沿用 PDF 制作 Word，该请求已授权重建。`--allow-rebuild` 是脚本的显式选择，不是额外批准流程。
- 扫描件：报告需要 OCR。没有 OCR 时请用户给可编辑/文字层来源或用默认版式继续，不能生成空白文件冒充复刻。
- 浮动文本框、嵌套/合并表格等复杂布局：报告实际无法映射的位置。可以在副本人工适配，或根据用户偏好改用重建；未经说明不静默换模板。
- `.doc`：转换为新的 DOCX 再检查；转换不可用时保留原件并解释恢复办法。

## 构建与交付

```text
python "$SKILL_DIR/scripts/resume.py" build --master "<master.json>" --outdir "<输出目录>" --workspace "<工作区>"
python "$SKILL_DIR/scripts/resume.py" build --master "<master.json>" --select "<经历id>" --template "<模板.docx>" --outdir "<输出目录>"
python "$SKILL_DIR/scripts/resume.py" build --master "<master.json>" --template "<参考.pdf>" --allow-rebuild --outdir "<输出目录>"
```

每次输出独立版本目录，不覆盖原件。默认生成 Word，再由 Windows Word 或 LibreOffice 转为 PDF；不能另用 PDF 排版器生成一份看似一致的替代物。需要单独 Word 时明确 `--docx-only`。

用户只要 Word 时，可用 `export --docx "<最终.docx>" --outdir "<内部预览目录>"` 生成内部 PDF 页图用于检查，保持原 Word 不变；不必把预览作为额外交付发给用户。

运行 [文件工作流](references/files-and-export.md) 的检查并查看所有 PDF 页面。自动检查通过不代表视觉审阅通过。核对无截断、缺字、重叠、空白尾页、样例残留、过小正文；检查日期、数字、姓名、链接、页数与用户意图。内容过长先精简重复文字或调整分页，不为塞进一页把正文挤到难以阅读。完成逐页查看后才记录审阅凭据。

交付链接指向真实 Word/PDF；简短说明内容来源、模板重建差异和未解决项。转换失败时保留 Word、资料和报告，明确 PDF 未完成以及可用恢复办法，不写“双格式交付完成”。`needs_visual_review` 表示等待你实际查看；只有完成查看才能对用户称交付已核验。

## 续编

阅读 [续编规则](references/continuation.md)。以用户指定的最新 Word 为基础，即使没有经历库和版本记录也能继续；保留原件，修改副本。明确替换文案写入 JSON，不改其他内容和样式。回读差异，再从这次最终 Word 导出新的 PDF。旧 PDF 的来源哈希不匹配时视为过期。

```text
python "$SKILL_DIR/scripts/resume.py" continue --latest "<最新.docx>" --replacements "<修改.json>" --outdir "<输出目录>"
```

不适合精确文字替换的复杂编辑，直接用 python-docx/文档工具编辑副本，并遵循相同导出、回读和逐页检查流程。事实发生变化时将差异作为待确认项更新资料，不从格式变化推断新个人事实。

## 参考与示例

- [数据格式](references/data-model.md)：字段、状态、指标与栏目。
- [经历写作与岗位定制](references/content-and-targeting.md)：追问、JD、行业及资历适配。
- [模板规则](references/templates.md)：映射格式、支持范围与重建说明。
- [文件工作流](references/files-and-export.md)：依赖、能力缺失、导出和验收。
- [续编规则](references/continuation.md)：无历史修改、差异与版本。
- `assets/examples/`：虚构的中文运营、技术学生与英文有经验资料，用来验证流程，不能复制成用户履历。
