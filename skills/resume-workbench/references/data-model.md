# 资料格式

`master.json` 使用 UTF-8，schema_version 为 `1.0`。每个来源、经历、bullet 有唯一稳定 id。实际完整虚构示例见 assets/examples。最终排版 payload 由脚本生成，不手工把待核对资料转为排版内容。

顶层：

| 字段 | 内容 |
| --- | --- |
| profile | name、headline、email、phone、location、summary、links（label/url） |
| target | role、language（zh/en）、market、seniority（student/experienced/academic）、paper（A4/Letter）、可选 page_limit |
| sources | id、type（user/document/github）、reference、可选 note |
| experiences | 下述经历数组 |
| section_order | 可选的 kind 数组，用于指定栏目顺序 |

最终至少需姓名和一种联系方式。资料不足时可先保存 JSON 草稿，不伪造联系方式或资格。

经历字段：id、kind、title、organization、role、start、end、url、summary、tags、status、source_ids、bullets。

- kind：education/work/project/research/teaching/volunteer/award/certificate/publication/other。
- status：confirmed/pending/conflict/missing；未提供状态视为 pending。
- 日期如 `2023-06` 至 `2025-08`，仍在职按用户语言使用“至今”或 Present，不自行补月份。
- source_ids 对应来源 id。用户确认可来自本次叙述；document/github 导入先 pending。
- bullet：id、text、status、source_ids、contribution（individual/team/assisted/unknown），可选 metrics。
- 资格类如学历、证书不要求贡献字段；工作/项目中的贡献需区分个人、团队与协助。
- metric：value、unit、scope、basis（measured/user_confirmed/estimated/unknown），可选 period、baseline、conditions。估算或未知不能写入最终投递内容。

```json
{
  "id": "work-1",
  "kind": "work",
  "title": "活动运营",
  "organization": "示例机构（虚构）",
  "role": "运营专员",
  "start": "2023-06",
  "end": "2025-08",
  "status": "confirmed",
  "source_ids": ["user-1"],
  "tags": ["运营", "活动"],
  "bullets": [{
    "id": "work-1-b1",
    "text": "整理活动报名资料并交付周报，供团队复盘使用。",
    "status": "confirmed",
    "source_ids": ["user-1"],
    "contribution": "individual"
  }]
}
```

confirmed 表示用户已确认供简历使用，不表示第三方验证。无依据的数字即使写在普通 text 中也不可靠；脚本不能识别所有自然语言谎言，你必须检查和追问。脚本的严格构建会阻断选中经历中的待核对项；用多次 `--select` 指定已确认素材，未选中素材仍留在主库。
