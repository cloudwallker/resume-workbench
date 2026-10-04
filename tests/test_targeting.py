import copy
import unittest
from rw.targeting import analyze_jd, recommend_experiences


class TargetingTests(unittest.TestCase):
    def test_requirements_keep_qualification_and_language_context(self):
        report = analyze_jd('岗位要求：\n1. 本科及以上学历\n2. 熟悉 Python 和 SQL\n3. 三年以上数据分析经验')
        self.assertEqual(len(report['requirements']), 3)
        self.assertTrue(any('本科' in r['text'] and r['kind'] == 'qualification' for r in report['requirements']))
        self.assertEqual(report['method'], 'keyword_heuristic')

    def test_no_matching_requirements_still_report_gaps(self):
        master = {'experiences': [{'id': 'x', 'kind': 'work', 'title': '运营', 'status': 'confirmed', 'bullets': []}]}
        report = recommend_experiences(master, '要求：Python 开发经验\n必须持有注册会计师证书')
        self.assertEqual(len(report['gaps']), 2)
        self.assertNotIn('ats_score', report)

    def test_keyword_evidence_does_not_prove_qualification_and_facts_stay_intact(self):
        master = {'experiences': [{'id': 'p', 'kind': 'project', 'title': 'Python 工具', 'tags': ['Python'],
                  'status': 'confirmed', 'start': '2024-01', 'bullets': [{'text': '团队协作开发 Python 工具', 'status': 'confirmed', 'contribution': 'team'}]},
                  {'id': 'c', 'kind': 'certificate', 'title': '注册会计师', 'status': 'pending', 'bullets': []}]}
        before = copy.deepcopy(master)
        report = recommend_experiences(master, 'Python 开发\n必须持有注册会计师证书', limit=1)
        self.assertEqual(report['candidates'][0]['id'], 'p')
        self.assertTrue(report['candidates'][0]['reasons'])
        self.assertTrue(any('注册会计师' in g['requirement'] for g in report['gaps']))
        self.assertEqual(master, before)
        self.assertNotIn('qualified', report)

    def test_without_jd_returns_general_recommendations(self):
        report = recommend_experiences({'experiences': [{'id': 'v', 'kind': 'volunteer', 'title': '社区服务', 'status': 'confirmed', 'bullets': []}]}, '')
        self.assertEqual(report['candidates'][0]['id'], 'v')
        self.assertEqual(report['gaps'], [])

    def test_english_keyword_boundary_does_not_claim_java_from_javascript(self):
        master = {'experiences': [{'id': 'web', 'title': 'JavaScript frontend', 'kind': 'project', 'status': 'confirmed', 'bullets': []}]}
        report = recommend_experiences(master, 'Java backend development')
        self.assertEqual(report['candidates'][0]['matched_requirement_ids'], [])
        self.assertTrue(report['candidates'][0]['reasons'])
        self.assertEqual(len(report['gaps']), 1)


if __name__ == '__main__':
    unittest.main()
