"""Validate user-confirmed facts and materialize conservative resume payloads."""
from copy import deepcopy
import re
from urllib.parse import urlsplit

KINDS = ('education', 'work', 'project', 'research', 'teaching', 'volunteer', 'award', 'certificate', 'publication', 'other')
STATUSES = {'confirmed', 'pending', 'conflict', 'missing'}
CONTRIBUTIONS = {'individual', 'team', 'assisted', 'unknown'}
CONTRIBUTION_KINDS = {'work', 'project', 'research', 'teaching', 'volunteer'}
TITLES = {
    'zh': dict(zip(KINDS, ('教育经历', '工作经历', '项目经历', '研究经历', '教学经历', '志愿经历', '荣誉奖项', '资格证书', '发表成果', '其他经历'))),
    'en': dict(zip(KINDS, ('Education', 'Work Experience', 'Projects', 'Research', 'Teaching', 'Volunteering', 'Awards', 'Certifications', 'Publications', 'Other Experience'))),
}


def _issue(issues, code, path, message):
    issues.append({'code': code, 'path': path, 'message': message, 'severity': 'error'})


def _date(value):
    if not value or str(value).lower() in {'present', 'current', '至今', 'now'}:
        return None
    match = re.fullmatch(r'(\d{4})(?:[-/.](\d{1,2}))?(?:[-/.](\d{1,2}))?', str(value))
    if not match:
        return False
    year, month, day = (int(match[1]), int(match[2] or 1), int(match[3] or 1))
    import datetime
    try:
        datetime.date(year, month, day)
        return year, month, day
    except ValueError:
        return False


def _safe_link_url(value):
    """Accept external document links without credentials or control characters."""
    if not isinstance(value, str) or not value or '\\' in value:
        return False
    if any(character.isspace() or ord(character) < 32 or ord(character) == 127 for character in value):
        return False
    if re.search(r'%(?:0[0-9a-f]|1[0-9a-f]|7f)', value, re.I):
        return False
    try:
        parsed = urlsplit(value)
        if parsed.scheme in {'http', 'https'}:
            if not parsed.hostname or parsed.username is not None or parsed.password is not None:
                return False
            if re.search(r'[<>"\'%]', parsed.hostname):
                return False
            # Accessing port validates malformed and out-of-range port values.
            return parsed.port is None or 0 < parsed.port <= 65535
        if parsed.scheme == 'mailto':
            return not parsed.netloc and not parsed.fragment and bool(re.fullmatch(r'[^@\s/\\:;,?]+@[^@\s/\\:;,?]+', parsed.path))
    except ValueError:
        return False
    return False


def validate_master(master):
    """Return actionable blocking issues without modifying the supplied dict."""
    issues = []
    if not isinstance(master, dict):
        return [{'code': 'master_type', 'path': '$', 'message': '主资料必须为对象。', 'severity': 'error'}]
    if master.get('schema_version') != '1.0':
        _issue(issues, 'schema_version', 'schema_version', '需要 schema_version=1.0。')
    profile = master.get('profile')
    if not isinstance(profile, dict):
        _issue(issues, 'profile_type', 'profile', 'profile 必须为对象。')
        profile = {}
    for field in ('name', 'headline', 'email', 'phone', 'location', 'summary'):
        if field in profile and not isinstance(profile[field], str):
            _issue(issues, 'profile_field_type', 'profile.' + field, '个人资料文字字段必须为字符串。')
    if not isinstance(profile.get('name'), str) or not profile.get('name', '').strip():
        _issue(issues, 'name_required', 'profile.name', '最终简历需要姓名。')
    if not any(isinstance(profile.get(key), str) and profile[key].strip() for key in ('email', 'phone')):
        _issue(issues, 'contact_required', 'profile', '最终简历需要邮箱或电话。')
    links = profile.get('links', [])
    if not isinstance(links, list):
        _issue(issues, 'profile_links_type', 'profile.links', 'links 必须为数组，可为空数组。')
    else:
        for index, link in enumerate(links):
            path = f'profile.links[{index}]'
            if not isinstance(link, dict):
                _issue(issues, 'profile_link_type', path, '链接必须为包含 url 的对象。')
                continue
            # The renderer displays the URL when label is omitted or empty.
            if 'label' in link and not isinstance(link['label'], str):
                _issue(issues, 'profile_link_label_type', path + '.label', '提供的链接名称必须为字符串；省略或留空会显示 URL。')
            if not _safe_link_url(link.get('url')):
                _issue(issues, 'profile_link_url', path + '.url', '链接需为非空安全 http、https 或 mailto 地址，不能含凭据或控制字符。')
    target = master.get('target')
    if not isinstance(target, dict):
        _issue(issues, 'target_type', 'target', 'target 必须为对象。')
        target = {}
    for field, allowed in (('language', {'zh', 'en'}), ('seniority', {'student', 'experienced', 'academic'}), ('paper', {'A4', 'Letter'})):
        if not isinstance(target.get(field), str) or target.get(field) not in allowed:
            _issue(issues, 'target_value', 'target.' + field, '该目标字段取值无效。')
    if 'page_limit' in target and (not isinstance(target['page_limit'], int) or isinstance(target['page_limit'], bool) or target['page_limit'] <= 0):
        _issue(issues, 'page_limit_invalid', 'target.page_limit', '提供的 page_limit 必须为正整数。')
    sources = master.get('sources', [])
    if not isinstance(sources, list):
        _issue(issues, 'sources_type', 'sources', 'sources 必须为数组。')
        sources = []
    source_ids = set()
    for index, source in enumerate(sources):
        path = f'sources[{index}]'
        if not isinstance(source, dict):
            _issue(issues, 'source_type', path, '来源必须为对象。')
            continue
        identifier = source.get('id')
        if not isinstance(identifier, str) or not identifier or identifier in source_ids:
            _issue(issues, 'source_id', path + '.id', '来源 ID 必须为唯一非空字符串。')
        else:
            source_ids.add(identifier)
        if not isinstance(source.get('type'), str) or source.get('type') not in {'user', 'document', 'github'} or not source.get('reference'):
            _issue(issues, 'source_invalid', path, '来源需包含 type 和 reference。用户陈述不等于独立核证。')
    experiences = master.get('experiences', [])
    if not isinstance(experiences, list):
        _issue(issues, 'experiences_type', 'experiences', 'experiences 必须为数组。')
        experiences = []
    ids = set()

    def check_status(item, path):
        status = item.get('status', 'pending')
        if not isinstance(status, str) or status not in STATUSES:
            _issue(issues, 'status_invalid', path + '.status', '状态取值无效。')
        elif status != 'confirmed':
            _issue(issues, 'fact_' + status, path + '.status', '该事实尚不能用于最终投递内容，请核对确认。')
        refs = item.get('source_ids', [])
        if not isinstance(refs, list) or any(not isinstance(s, str) or s not in source_ids for s in refs):
            _issue(issues, 'source_unknown', path + '.source_ids', '引用了不存在的来源 ID。')

    for index, experience in enumerate(experiences):
        path = f'experiences[{index}]'
        if not isinstance(experience, dict):
            _issue(issues, 'experience_type', path, '经历必须为对象。')
            continue
        identifier = experience.get('id')
        if not isinstance(identifier, str) or not identifier or identifier in ids:
            _issue(issues, 'experience_id', path + '.id', '经历 ID 必须为唯一非空字符串。')
        else:
            ids.add(identifier)
        kind = experience.get('kind')
        if kind not in KINDS:
            _issue(issues, 'kind_invalid', path + '.kind', '经历栏目取值无效。')
        if not isinstance(experience.get('title'), str) or not experience.get('title', '').strip():
            _issue(issues, 'title_required', path + '.title', '经历需要标题。')
        check_status(experience, path)
        start, end = _date(experience.get('start')), _date(experience.get('end'))
        if start is False or end is False:
            _issue(issues, 'date_invalid', path, '日期需使用有效年、年月或年月日，也可用至今。')
        elif start and end and start > end:
            _issue(issues, 'date_order', path, '开始日期不能晚于结束日期。')
        bullets = experience.get('bullets', [])
        if not isinstance(bullets, list):
            _issue(issues, 'bullets_type', path + '.bullets', 'bullets 必须为对象数组。')
            continue
        bullet_ids = set()
        for number, bullet in enumerate(bullets):
            bp = f'{path}.bullets[{number}]'
            if not isinstance(bullet, dict):
                _issue(issues, 'bullet_type', bp, 'bullet 必须为对象。')
                continue
            bid = bullet.get('id')
            if not isinstance(bid, str) or not bid or bid in bullet_ids:
                _issue(issues, 'bullet_id', bp + '.id', 'bullet ID 必须为经历内唯一非空字符串。')
            else:
                bullet_ids.add(bid)
            check_status(bullet, bp)
            if not isinstance(bullet.get('text'), str) or not bullet.get('text', '').strip():
                _issue(issues, 'bullet_text', bp + '.text', 'bullet 需要非空文本。')
            contribution = bullet.get('contribution', 'unknown')
            if not isinstance(contribution, str) or contribution not in CONTRIBUTIONS:
                _issue(issues, 'contribution_invalid', bp + '.contribution', '贡献归属取值无效。')
            elif isinstance(kind, str) and kind in CONTRIBUTION_KINDS and contribution == 'unknown':
                _issue(issues, 'contribution_unknown', bp + '.contribution', '请确认个人、团队或协助贡献，不自动升级个人归属。')
            metrics = bullet.get('metrics', [])
            if not isinstance(metrics, list):
                _issue(issues, 'metrics_type', bp + '.metrics', 'metrics 必须为数组。')
                continue
            for number, metric in enumerate(metrics):
                mp = f'{bp}.metrics[{number}]'
                if not isinstance(metric, dict):
                    _issue(issues, 'metric_type', mp, '指标必须为对象。')
                    continue
                if not isinstance(metric.get('basis'), str) or metric.get('basis') not in {'measured', 'user_confirmed'}:
                    _issue(issues, 'metric_unconfirmed', mp + '.basis', '估算或未知指标需确认后才能投递。')
                if any(field not in metric or metric[field] is None or metric[field] == '' for field in ('value', 'unit', 'scope')):
                    _issue(issues, 'metric_incomplete', mp, '指标需包含 value、unit 和 scope，保留口径。')
    return issues


def materialize_resume(master, selected_ids=None, strict=True):
    """Render confirmed facts only; strict mode rejects all selected blocking issues."""
    candidate = deepcopy(master)
    if not isinstance(candidate, dict):
        raise ValueError('主资料必须为对象。')
    if selected_ids is not None:
        if not isinstance(selected_ids, (list, tuple, set)):
            raise ValueError('selected_ids 必须为 ID 列表。')
        if any(not isinstance(identifier, str) for identifier in selected_ids):
            raise ValueError('selected_ids 的 ID 必须为字符串。')
        experiences = candidate.get('experiences', [])
        if not isinstance(experiences, list):
            raise ValueError('experiences 必须为数组。')
        known = {e.get('id') for e in experiences if isinstance(e, dict) and isinstance(e.get('id'), str)}
        if set(selected_ids) - known:
            raise ValueError('选中了不存在的经历 ID。')
        candidate['experiences'] = [e for e in experiences if isinstance(e, dict) and e.get('id') in selected_ids]
    issues = validate_master(candidate)
    if strict and issues:
        raise ValueError('最终构建被阻断：' + '; '.join(i['path'] + ': ' + i['message'] for i in issues))
    profile, target = candidate.get('profile'), candidate.get('target')
    profile = profile if isinstance(profile, dict) else {}
    target = target if isinstance(target, dict) else {}
    groups = {}
    experiences = candidate.get('experiences', [])
    for index, experience in enumerate(experiences if isinstance(experiences, list) else []):
        path = f'experiences[{index}]'
        if not isinstance(experience, dict) or experience.get('status', 'pending') != 'confirmed':
            continue
        if any(i['path'].startswith(path) and '.bullets' not in i['path'] for i in issues):
            continue
        entry = {key: deepcopy(experience.get(key, '')) for key in ('id', 'title', 'organization', 'role', 'start', 'end', 'url', 'summary')}
        entry['bullets'] = []
        bullets = experience.get('bullets', [])
        for number, bullet in enumerate(bullets if isinstance(bullets, list) else []):
            bp = f'{path}.bullets[{number}]'
            if isinstance(bullet, dict) and not any(i['path'] == bp or i['path'].startswith(bp + '.') for i in issues):
                entry['bullets'].append(bullet['text'])
        groups.setdefault(experience['kind'], []).append(entry)
    language = target.get('language', 'zh')
    titles = TITLES.get(language, TITLES['zh']) if isinstance(language, str) else TITLES['zh']
    default_order = ('education', 'project', 'work') if target.get('seniority') == 'student' else ('work', 'project', 'education')
    if target.get('seniority') == 'academic':
        default_order = ('education', 'research', 'publication', 'teaching')
    explicit = candidate.get('section_order', [])
    order = []
    for kind in (explicit if isinstance(explicit, list) else []) + list(default_order) + list(KINDS):
        if kind in groups and kind not in order:
            order.append(kind)
    return {'profile': deepcopy(profile), 'target': deepcopy(target), 'sections': [{'id': kind, 'title': titles[kind], 'entries': groups[kind]} for kind in order]}
