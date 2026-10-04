import base64
import json
import unittest
from rw.github import collect_github


REPO = {'id': 101, 'name': 'example', 'full_name': 'fiction/example', 'html_url': 'https://github.com/fiction/example',
        'description': '公开示例工具', 'language': 'Python', 'topics': ['automation'], 'fork': False, 'private': False,
        'stargazers_count': 2, 'default_branch': 'main', 'owner': {'login': 'fiction'}, 'updated_at': '2026-01-01T00:00:00Z'}


def fixture_transport(url):
    if url == 'https://api.github.com/users/fiction/repos?per_page=100&sort=updated':
        return [REPO]
    if url == 'https://api.github.com/repos/fiction/example':
        return REPO
    if url == 'https://api.github.com/repos/fiction/example/readme':
        return {'encoding': 'base64', 'content': base64.b64encode('# Example\n运行脚本可执行'.encode()).decode(), 'html_url': 'https://github.com/fiction/example/blob/main/README.md'}
    raise AssertionError('unexpected public endpoint')


class GithubTests(unittest.TestCase):
    def test_account_parses_public_data_and_ownership_never_confirms_contribution(self):
        report = collect_github('fiction', transport=fixture_transport)
        self.assertTrue(report['ok'])
        self.assertEqual(report['repositories'][0]['readme'], '# Example\n运行脚本可执行')
        self.assertEqual(report['experiences'][0]['status'], 'pending')
        self.assertEqual(report['experiences'][0]['bullets'][0]['contribution'], 'unknown')
        self.assertEqual(report['experiences'][0]['bullets'][0]['status'], 'pending')
        self.assertIn('Python', report['experiences'][0]['tags'])

    def test_repository_url_reads_single_repository(self):
        report = collect_github('https://github.com/fiction/example', transport=fixture_transport)
        self.assertEqual(len(report['repositories']), 1)
        self.assertEqual(report['repositories'][0]['full_name'], 'fiction/example')

    def test_transport_failure_is_sanitized_and_retains_fallback(self):
        def broken(url):
            raise OSError('Authorization: Bearer super-secret-token')
        report = collect_github('fiction', transport=broken)
        self.assertFalse(report['ok'])
        self.assertTrue(report['errors'])
        self.assertNotIn('super-secret-token', json.dumps(report))
        self.assertTrue(report['fallback'])

    def test_readme_failure_preserves_repository_and_invalid_input_makes_no_request(self):
        def missing_readme(url):
            if url.endswith('/readme'):
                raise OSError('unavailable')
            return fixture_transport(url)
        report = collect_github('fiction', transport=missing_readme)
        self.assertTrue(report['ok'])
        self.assertTrue(report['warnings'])
        self.assertEqual(len(report['repositories']), 1)
        for identifier in ('https://evil.example/fiction/example', 'fiction/../secret', 'https://github.com/fiction/example?token=secret'):
            report = collect_github(identifier, transport=lambda url: self.fail('invalid input fetched'))
            self.assertFalse(report['ok'])
            self.assertNotIn('secret', json.dumps(report))

    def test_private_or_malformed_fixture_cannot_be_turned_into_public_evidence(self):
        report = collect_github('fiction', transport=lambda url: [{**REPO, 'private': True}])
        self.assertEqual(report['repositories'], [])
        self.assertEqual(report['experiences'], [])
        report = collect_github('fiction', transport=lambda url: {'malformed': 'response'})
        self.assertFalse(report['ok'])


if __name__ == '__main__':
    unittest.main()
