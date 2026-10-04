"""Transparent keyword hints, never an ATS score or a qualification decision."""
from copy import deepcopy
import re

NOTICE = '关键词启发式辅助；文本相似不证明满足任职资格，需由用户核对实际经历和资格。'
QUALIFICATION = re.compile(r'学历|本科|硕士|博士|学位|证书|资格|持有|执照|\d+\s*年|[一二三四五六七八九十]+年|degree|bachelor|master|phd|certif|licen[sc]e|\d+\s*years?', re.I)
KNOWN_TERMS = ('数据分析', '内容运营', '用户运营', '社区运营', '项目管理', '客户服务', '财务', '会计', '注册会计师', '营销', '销售', '沟通', '团队', '本科', '硕士', '博士', '研究', '教学', 'Python', 'SQL', 'Java', 'Excel', 'Power BI', 'Tableau', 'JavaScript', 'React', 'Linux')


def _contains(text, keyword):
    if re.fullmatch(r'[a-z0-9+#.\- ]+', keyword):
        return bool(re.search(r'(?<![a-z0-9_])' + re.escape(keyword) + r'(?![a-z0-9_])', text))
    return keyword in text


def _keywords(text):
    lowered = text.casefold()
    keywords = [term.casefold() for term in KNOWN_TERMS if _contains(lowered, term.casefold())]
    keywords += re.findall(r'[a-z][a-z0-9+#.\-]{1,}', lowered)
    if not keywords:
        for phrase in re.findall(r'[\u4e00-\u9fff]{2,}', text):
            phrase = re.sub(r'^(岗位要求|任职要求|要求|必须|熟悉|具备|负责|具有|能够|擅长|经验|技能)+', '', phrase)
            if len(phrase) >= 2:
                keywords.append(phrase)
    return list(dict.fromkeys(term for term in keywords if term not in {'and', 'the', 'with', 'for', 'you', 'must', 'required'}))


def analyze_jd(text):
    if not isinstance(text, str):
        raise ValueError('JD 必须为文本。')
    requirements = []
    for raw in re.split(r'[\r\n;；]+', text):
        line = re.sub(r'^\s*(?:[-*•]|\d+[.)、]|[一二三四五六七八九十]+[、.])\s*', '', raw).strip()
        line = re.sub(r'^(?:岗位要求|任职要求|要求|Requirements|Qualifications)\s*[:：]\s*', '', line, flags=re.I)
        if not line or re.fullmatch(r'(?:岗位要求|任职要求|要求|Requirements|Qualifications)\s*[:：]?', line, re.I):
            continue
        requirements.append({'id': f'r{len(requirements) + 1}', 'text': line, 'kind': 'qualification' if QUALIFICATION.search(line) else 'skill_or_responsibility', 'keywords': _keywords(line)})
    return {'requirements': requirements, 'method': 'keyword_heuristic', 'notice': NOTICE}


def recommend_experiences(master, jd_text, limit=3):
    if not isinstance(master, dict) or not isinstance(master.get('experiences', []), list):
        raise ValueError('主资料经历必须为数组。')
    if not isinstance(limit, int) or isinstance(limit, bool) or limit < 0:
        raise ValueError('limit 必须为非负整数。')
    analysis = analyze_jd(jd_text)
    requirements = analysis['requirements']
    candidates = []
    evidence = {requirement['id']: [] for requirement in requirements}
    for index, experience in enumerate(master.get('experiences', [])):
        if not isinstance(experience, dict) or experience.get('status', 'pending') != 'confirmed':
            continue
        text_parts = [str(experience.get(key, '')) for key in ('title', 'organization', 'role', 'summary')]
        tags = experience.get('tags', [])
        if isinstance(tags, list):
            text_parts += [tag for tag in tags if isinstance(tag, str)]
        bullets = experience.get('bullets', [])
        for bullet in bullets if isinstance(bullets, list) else []:
            if not isinstance(bullet, dict) or bullet.get('status', 'pending') != 'confirmed':
                continue
            if experience.get('kind') in {'work', 'project', 'research', 'teaching', 'volunteer'} and bullet.get('contribution', 'unknown') == 'unknown':
                continue
            metrics = bullet.get('metrics', [])
            if not isinstance(metrics, list) or any(not isinstance(m, dict) or m.get('basis') not in {'measured', 'user_confirmed'} for m in metrics):
                continue
            text_parts.append(str(bullet.get('text', '')))
        haystack = ' '.join(text_parts).casefold()
        reasons = []
        matched = []
        for requirement in requirements:
            terms = [term for term in requirement['keywords'] if _contains(haystack, term)]
            if terms:
                evidence[requirement['id']].append(experience.get('id'))
                matched.append(requirement['id'])
                reasons.append({'requirement_id': requirement['id'], 'matched_keywords': terms, 'explanation': '已确认经历含相关关键词，需复核实际职责和资格。'})
        if not requirements:
            reasons.append({'explanation': '未提供 JD，按已确认经历的原始顺序提供通用版候选。'})
        elif not reasons:
            reasons.append({'explanation': '未找到 JD 关键词关联；仅作为已确认经历备选，不表示岗位匹配。'})
        candidates.append({'id': experience.get('id'), 'title': experience.get('title', ''), 'reasons': reasons, 'matched_requirement_ids': matched, '_order': index})
    candidates.sort(key=lambda candidate: (-len(candidate['matched_requirement_ids']), candidate['_order']))
    for candidate in candidates:
        candidate.pop('_order')
    gaps = []
    for requirement in requirements:
        matching = evidence[requirement['id']]
        if not matching or requirement['kind'] == 'qualification':
            gaps.append({'requirement_id': requirement['id'], 'requirement': requirement['text'], 'reason': '资格、年限或学历需人工核对；关键词不构成满足证明。' if requirement['kind'] == 'qualification' else '已确认经历中未找到相关关键词证据。', 'related_experience_ids': matching})
    return {'requirements': deepcopy(requirements), 'candidates': candidates[:limit], 'selected_ids': [c['id'] for c in candidates[:limit]], 'gaps': gaps, 'method': analysis['method'], 'notice': NOTICE}
