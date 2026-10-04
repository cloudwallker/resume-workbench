import copy
import unittest

from rw.core import materialize_resume, validate_master


def master_fixture():
    return {'schema_version': '1.0', 'profile': {'name': '虚构求职者', 'email': 'person@example.com'},
            'target': {'role': '运营', 'language': 'zh', 'market': 'CN', 'seniority': 'experienced', 'paper': 'A4'},
            'sources': [{'id': 's1', 'type': 'user', 'reference': '用户陈述'}],
            'experiences': [{'id': 'w1', 'kind': 'work', 'title': '内容运营', 'organization': '虚构企业',
                             'role': '运营专员', 'start': '2023-01', 'end': '2024-12', 'status': 'confirmed',
                             'source_ids': ['s1'], 'bullets': [{'id': 'b1', 'text': '协助团队完成内容策划',
                             'status': 'confirmed', 'source_ids': ['s1'], 'contribution': 'assisted'}]}]}


class CoreTests(unittest.TestCase):
    def test_confirmed_assisted_text_dates_and_sources_are_preserved(self):
        master = master_fixture()
        before = copy.deepcopy(master)
        payload = materialize_resume(master)
        entry = payload['sections'][0]['entries'][0]
        self.assertEqual(entry['bullets'], ['协助团队完成内容策划'])
        self.assertEqual((entry['start'], entry['end']), ('2023-01', '2024-12'))
        self.assertEqual(master, before)
        self.assertEqual(validate_master(master), [])

    def test_default_pending_and_conflict_cannot_enter_final(self):
        for status in (None, 'pending', 'conflict', 'missing'):
            with self.subTest(status=status):
                master = master_fixture()
                bullet = master['experiences'][0]['bullets'][0]
                bullet.pop('status') if status is None else bullet.update(status=status)
                with self.assertRaises(ValueError):
                    materialize_resume(master)
                self.assertEqual(materialize_resume(master, strict=False)['sections'][0]['entries'][0]['bullets'], [])

    def test_estimated_and_unknown_metrics_are_blocked(self):
        for basis in ('estimated', 'unknown'):
            master = master_fixture()
            master['experiences'][0]['bullets'][0]['metrics'] = [{'value': 20, 'unit': '%', 'scope': '团队内容阅读量', 'basis': basis}]
            self.assertIn('metric_unconfirmed', [i['code'] for i in validate_master(master)])
            with self.assertRaises(ValueError):
                materialize_resume(master)

    def test_unknown_contribution_requires_confirmation_but_education_does_not(self):
        master = master_fixture()
        master['experiences'][0]['bullets'][0]['contribution'] = 'unknown'
        with self.assertRaises(ValueError):
            materialize_resume(master)
        master['experiences'][0]['kind'] = 'education'
        master['experiences'][0]['bullets'][0].pop('contribution')
        self.assertEqual(materialize_resume(master)['sections'][0]['id'], 'education')

    def test_selected_facts_do_not_block_on_unselected_pending_qualification(self):
        master = master_fixture()
        master['experiences'].append({'id': 'cert', 'kind': 'certificate', 'title': '待确认资格', 'status': 'pending', 'bullets': []})
        with self.assertRaises(ValueError):
            materialize_resume(master)
        self.assertEqual(len(materialize_resume(master, ['w1'])['sections']), 1)

    def test_contact_date_source_and_schema_errors_have_paths(self):
        master = master_fixture()
        master['schema_version'] = '0'
        master['profile'].pop('email')
        master['experiences'][0]['start'] = '2025-02'
        master['experiences'][0]['source_ids'] = ['unknown']
        issues = validate_master(master)
        self.assertTrue(all(i['path'] and i['severity'] == 'error' for i in issues))
        self.assertTrue({'schema_version', 'contact_required', 'date_order', 'source_unknown'} <= {i['code'] for i in issues})

    def test_english_multiple_industry_sections_and_order(self):
        master = master_fixture()
        master['target']['language'] = 'en'
        master['experiences'].append({'id': 'e1', 'kind': 'education', 'title': 'Bachelor', 'status': 'confirmed', 'bullets': []})
        master['section_order'] = ['education', 'work']
        payload = materialize_resume(master)
        self.assertEqual([s['id'] for s in payload['sections']], ['education', 'work'])
        self.assertEqual(payload['sections'][0]['title'], 'Education')

    def test_malformed_collections_report_instead_of_crashing(self):
        for field in ('experiences', 'sources', 'profile', 'target'):
            master = master_fixture()
            master[field] = None
            self.assertTrue(validate_master(master))

    def test_malformed_status_and_enum_fields_report_instead_of_crashing(self):
        for location, field in (('experience', 'status'), ('experience', 'kind'), ('bullet', 'contribution'), ('bullet', 'status'), ('target', 'language'), ('source', 'type')):
            with self.subTest(location=location, field=field):
                master = master_fixture()
                objects = {'experience': master['experiences'][0], 'bullet': master['experiences'][0]['bullets'][0], 'target': master['target'], 'source': master['sources'][0]}
                objects[location][field] = []
                self.assertTrue(validate_master(master))
                self.assertIsInstance(materialize_resume(master, strict=False), dict)

    def test_malformed_selection_is_value_error(self):
        with self.assertRaises(ValueError):
            materialize_resume(master_fixture(), [{}])

    def test_malformed_links_block_before_materialization_with_exact_paths(self):
        cases = [(None, 'profile.links'), ('https://example.invalid', 'profile.links'),
                 ([None], 'profile.links[0]'), ([{}], 'profile.links[0].url'),
                 ([{'label': None, 'url': 'https://example.invalid'}], 'profile.links[0].label'),
                 ([{'label': '主页', 'url': 12}], 'profile.links[0].url')]
        for value, expected_path in cases:
            with self.subTest(value=value):
                master = master_fixture()
                master['profile']['links'] = value
                self.assertIn(expected_path, [issue['path'] for issue in validate_master(master)])
                with self.assertRaises(ValueError):
                    materialize_resume(master)

    def test_safe_links_and_optional_label_fallback_are_preserved(self):
        master = master_fixture()
        self.assertEqual(validate_master(master), [])
        for links in ([], [{'url': 'https://example.invalid/portfolio'}],
                      [{'label': '', 'url': 'http://example.invalid'}],
                      [{'label': '邮件', 'url': 'mailto:fiction@example.invalid'}]):
            master['profile']['links'] = links
            self.assertEqual(validate_master(master), [])
            self.assertEqual(materialize_resume(master)['profile']['links'], links)

    def test_unsafe_or_invalid_link_urls_are_rejected(self):
        for url in ('', 'javascript:alert(1)', 'file:///C:/secret.txt', '//example.invalid',
                    'https://', 'https://user:password@example.invalid', 'https://example.invalid:bad',
                    'https://example.invalid/line\nbreak', 'https://example.invalid/%0d%0aheader',
                    'https://example.invalid\\misleading', 'mailto:', 'mailto:not-an-address'):
            with self.subTest(url=url):
                master = master_fixture()
                master['profile']['links'] = [{'label': '链接', 'url': url}]
                self.assertIn('profile.links[0].url', [i['path'] for i in validate_master(master)])
                with self.assertRaises(ValueError):
                    materialize_resume(master)

    def test_profile_scalar_fields_must_be_strings_when_present(self):
        for field in ('name', 'headline', 'email', 'phone', 'location', 'summary'):
            for value in (None, [], {}, 12, True):
                with self.subTest(field=field, value=value):
                    master = master_fixture()
                    master['profile'][field] = value
                    self.assertIn('profile.' + field, [i['path'] for i in validate_master(master)])
                    with self.assertRaises(ValueError):
                        materialize_resume(master)

    def test_page_limit_is_optional_positive_integer_and_rejects_bool(self):
        for value in (0, -1, '1', 1.5, True, None, []):
            with self.subTest(value=value):
                master = master_fixture()
                master['target']['page_limit'] = value
                self.assertIn('target.page_limit', [i['path'] for i in validate_master(master)])
                with self.assertRaises(ValueError):
                    materialize_resume(master)
        master = master_fixture()
        master['target']['page_limit'] = 2
        self.assertEqual(validate_master(master), [])
        self.assertEqual(materialize_resume(master)['target']['page_limit'], 2)


if __name__ == '__main__':
    unittest.main()
