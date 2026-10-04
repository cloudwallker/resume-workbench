# 模板预检与映射

`analyze-template` 先列出正文段落、表格、页眉页脚、占位符和复杂结构。模板样例不能成为个人事实。保存模板副本；`adapt_docx` 仅向新路径写入。旧 `.doc` 需先转换为新的 DOCX。

## DOCX

支持跨 run 的 `{{profile.name}}` 等 profile 字段（也支持 `{{name}}`）；profile 标量字段为 name/headline/email/phone/location/summary。`{{profile.contact}}` 合并 email、phone、location 和链接；`{{profile.links}}` 为标签及 URL。`{{target.<标量字段>}}` 可输出目标字段。`{{sections}}` 放入全部栏目并带栏目标题；`{{section:work}}` 或 `{{sections.work}}` 等放入指定栏目内容，不重复标题。资料和经历 URL 创建真实可点击关系；未输出的链接会阻断并提示需要槽位。

普通模板的“姓名：样例姓名”“联系方式：样例邮箱”等标签可识别字段。工作经历、教育经历等标题可识别栏目，栏目下面的样例正文替换为真实已确认内容。简单表格的字段或栏目槽可以适配。未识别非空文字默认阻断输出，需要明确映射、删除或确认保留，以防样例姓名、公司、邮箱混入成品。

映射为 UTF-8 JSON，索引零起，以 analyze-template 的报告为准：

```json
{
  "paragraphs": {"0": "profile.name", "3": "section:work"},
  "tables": {"0:0:1": "profile.email"},
  "locations": {"header:0:0": "profile.contact"},
  "remove_paragraphs": [1],
  "remove_cells": ["0:1:1"],
  "preserve_paragraphs": [2],
  "preserve_cells": ["0:0:0"]
}
```

tables 的 key 是 `表格:行:列`；`sections` 表示所有栏目，`profile.contact` 合并联系方式。preserve 明确授权保留静态文字，例如固定栏目标题，不应保留样例个人数据。映射或占位替换后还需回读完整文本、表格、页眉页脚及链接，核对样例无残留。复杂布局如浮动文本框、分栏、合并/嵌套表格、修订会报告需人工适配或重建；不会静默换成默认版式。

locations 使用报告里的完整位置字符串，如 `body:p`、`header:s:p`、`footer:s:p`，s 为节，p 为段落；首页/偶数页使用 `header:first:s:p`、`footer:even:s:p` 等。`remove_locations` / `preserve_locations` 数组可明确删除/保留位置。普通栏目内容沿用首样例段落格式并以真实换行分行，不承诺复制所有原样例的多级段落样式。

## PDF

有文字层 PDF 通过字形和页面边界测量纸张、正文边界、正文/标题字号、字体与配色，再用这些特征重建可编辑 Word。PDF 不是可直接替换字段的模板；多栏、字体替代、图片/图标和复杂对齐等差异必须记录并审阅。首版不保证像素级复刻。

短简历没有填满右侧或下方时，文字留白不能直接当作物理页边距。分析保留原文字边界及 measured_content_gaps_cm；只对无图片/矢量/多栏的简单版式，明显过大的右/下留白可回退到对称左/上边距，并在 adjustments 和 warnings 记录推断。字号不因此缩小。字体名仅在与已安装字体去空格名称一致时还原标准名称，其他未知字体仍报告替代风险。

```text
python "$SKILL_DIR/scripts/resume.py" build --master master.json --template reference.pdf --allow-rebuild --outdir output
```

`--allow-rebuild` 表示采用测得版式进行可编辑重建；用户明确请求这个任务已给出授权，无需额外重复确认。无文字层/扫描页返回 requires_ocr 和页面号。缺 OCR 时请提供可编辑来源，或按用户偏好使用默认版式，不输出空白复刻。所有新 PDF 仍由最终 Word 导出。
