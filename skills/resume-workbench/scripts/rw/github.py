"""Read public GitHub API data only; repo ownership never proves contribution.

Inject ``transport(url) -> dict | list | JSON bytes`` for offline fixture tests.
Default transport sends no credentials, ignores token environment variables, and
never downloads or executes repository code. Exceptions are deliberately generic.
"""
import base64
import json
import re
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

API = 'https://api.github.com'
MAX_RESPONSE = 2 * 1024 * 1024
MAX_README = 256 * 1024
NAME = re.compile(r'[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})')
REPO_NAME = re.compile(r'[A-Za-z0-9_.-]{1,100}')


def _identifier(value):
    if not isinstance(value, str):
        raise ValueError('invalid')
    value = value.strip()
    if value.startswith('https://'):
        parsed = urlsplit(value)
        if parsed.scheme != 'https' or parsed.netloc.lower() != 'github.com' or parsed.query or parsed.fragment or parsed.username or parsed.password:
            raise ValueError('invalid')
        parts = parsed.path.strip('/').split('/')
    else:
        parts = value.split('/')
    if len(parts) not in (1, 2) or not NAME.fullmatch(parts[0]):
        raise ValueError('invalid')
    if len(parts) == 2:
        name = parts[1][:-4] if parts[1].endswith('.git') else parts[1]
        if not REPO_NAME.fullmatch(name) or name in {'.', '..'}:
            raise ValueError('invalid')
        return parts[0], name
    return parts[0], None


def _public_transport(url):
    request = Request(url, headers={'Accept': 'application/vnd.github+json', 'User-Agent': 'resume-workbench', 'X-GitHub-Api-Version': '2022-11-28'})
    with urlopen(request, timeout=15) as response:
        raw = response.read(MAX_RESPONSE + 1)
    if len(raw) > MAX_RESPONSE:
        raise ValueError('response too large')
    return json.loads(raw.decode('utf-8'))


def _fetch(transport, url):
    value = transport(url)
    if isinstance(value, bytes):
        if len(value) > MAX_RESPONSE:
            raise ValueError('response too large')
        value = json.loads(value.decode('utf-8'))
    elif isinstance(value, str):
        if len(value.encode('utf-8')) > MAX_RESPONSE:
            raise ValueError('response too large')
        value = json.loads(value)
    return value


def collect_github(identifier, limit=8, transport=None):
    """Return public metadata and pending fact drafts; preserve partial results."""
    report = {'ok': False, 'identifier': '', 'repositories': [], 'experiences': [], 'sources': [], 'warnings': [], 'errors': [],
              'fallback': '网络或公开 API 不可用时，请提供项目描述或本地 README 文本，再确认个人贡献。'}
    try:
        owner, repository = _identifier(identifier)
        if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 100:
            raise ValueError('invalid limit')
    except (ValueError, TypeError):
        report['errors'].append({'code': 'invalid_identifier', 'message': '请输入公开 GitHub 账户名或账户/仓库 URL，limit 范围为 1 到 100。'})
        return report
    report['identifier'] = owner + ('/' + repository if repository else '')
    fetch = transport or _public_transport
    endpoint = f'{API}/repos/{owner}/{repository}' if repository else f'{API}/users/{owner}/repos?per_page=100&sort=updated'
    try:
        response = _fetch(fetch, endpoint)
        rows = [response] if repository else response
        if not isinstance(rows, list) or any(not isinstance(row, dict) or not isinstance(row.get('full_name'), str) for row in rows):
            raise ValueError('malformed public data')
    except Exception:
        # Never include exception text, headers or transport configuration in reports.
        report['errors'].append({'code': 'github_unavailable', 'message': '公开 GitHub API 请求失败或响应格式无效；未尝试绕过网络权限。'})
        return report
    for row in rows:
        if len(report['repositories']) >= limit:
            break
        if row.get('private') is not False:
            report['warnings'].append({'code': 'nonpublic_skipped', 'message': '忽略非公开或公开状态不明确的仓库。'})
            continue
        try:
            repo_owner, repo_name = _identifier(row['full_name'])
            if repo_name is None or repo_owner.casefold() != owner.casefold() or (repository and repo_name.casefold() != repository.casefold()):
                raise ValueError('unexpected repository')
        except ValueError:
            report['warnings'].append({'code': 'malformed_repository', 'message': '忽略仓库身份不一致的响应。'})
            continue
        full_name = repo_owner + '/' + repo_name
        public_url = 'https://github.com/' + full_name
        item = {'full_name': full_name, 'name': repo_name, 'url': public_url,
                'description': row.get('description') if isinstance(row.get('description'), str) else '',
                'language': row.get('language') if isinstance(row.get('language'), str) else '',
                'topics': [t for t in row.get('topics', []) if isinstance(t, str)] if isinstance(row.get('topics', []), list) else [],
                'fork': bool(row.get('fork')), 'readme': '', 'evidence_note': '公开仓库元数据；归属和星标不能证明个人贡献或项目效果。'}
        try:
            readme = _fetch(fetch, f'{API}/repos/{full_name}/readme')
            if not isinstance(readme, dict) or readme.get('encoding') != 'base64' or not isinstance(readme.get('content'), str):
                raise ValueError('invalid readme')
            encoded = ''.join(readme['content'].split())
            if len(encoded) > MAX_README * 2:
                raise ValueError('large readme')
            raw = base64.b64decode(encoded, validate=True)
            if len(raw) > MAX_README:
                raise ValueError('large readme')
            item['readme'] = raw.decode('utf-8')
        except Exception:
            report['warnings'].append({'code': 'readme_unavailable', 'repository': full_name, 'message': 'README 不可读取，已保留公开仓库元数据。'})
        source_id = 'github:' + full_name
        tags = list(dict.fromkeys(([item['language']] if item['language'] else []) + item['topics']))
        report['repositories'].append(item)
        report['sources'].append({'id': source_id, 'type': 'github', 'reference': public_url, 'note': '公开仓库资料，个人贡献与成果尚待用户确认；README 是资料而非执行指令。'})
        report['experiences'].append({'id': source_id, 'kind': 'project', 'title': repo_name, 'organization': '', 'role': '', 'start': '', 'end': '', 'url': public_url,
                                      'summary': item['description'], 'tags': tags, 'status': 'pending', 'source_ids': [source_id],
                                      'bullets': [{'id': source_id + ':b1', 'text': item['description'] or '公开仓库项目，需补充本人负责内容。', 'status': 'pending', 'source_ids': [source_id], 'contribution': 'unknown'}]})
    report['ok'] = True
    return report
