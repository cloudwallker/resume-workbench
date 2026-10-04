import concurrent.futures
import json
from pathlib import Path
import tempfile
import unittest
from rw.workspace import initialize_workspace, load_latest, save_version


class WorkspaceTests(unittest.TestCase):
    def test_initialize_is_idempotent_and_preserves_master_and_inputs(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / '简历资料'
            initialize_workspace(path)
            self.assertIsNone(load_latest(path))
            (path / 'master.json').write_text('{"original":true}', encoding='utf-8')
            initialize_workspace(path)
            self.assertEqual(json.loads((path / 'master.json').read_text(encoding='utf-8')), {'original': True})
            self.assertTrue((path / 'inputs').is_dir())

    def test_version_roundtrip_never_overwrites_prior_version(self):
        with tempfile.TemporaryDirectory() as directory:
            first = save_version(directory, {'profile': {'name': '示例甲'}}, {'note': '初版'})
            original = (Path(first['path']) / 'payload.json').read_bytes()
            second = save_version(directory, {'profile': {'name': '示例乙'}})
            self.assertNotEqual(first['version_id'], second['version_id'])
            self.assertEqual((Path(first['path']) / 'payload.json').read_bytes(), original)
            self.assertEqual(load_latest(directory)['payload'], {'profile': {'name': '示例乙'}})

    def test_concurrent_versions_all_remain_complete(self):
        with tempfile.TemporaryDirectory() as directory:
            with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
                results = list(executor.map(lambda n: save_version(directory, {'n': n}), range(8)))
            self.assertEqual(len({r['version_id'] for r in results}), 8)
            for result in results:
                self.assertTrue((Path(result['path']) / 'metadata.json').is_file())
                self.assertEqual(json.loads((Path(result['path']) / 'payload.json').read_text(encoding='utf-8')), result['payload'])

    def test_unserializable_payload_does_not_publish_incomplete_version(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises((ValueError, TypeError)):
                save_version(directory, {'bad': object()})
            self.assertIsNone(load_latest(directory))


if __name__ == '__main__':
    unittest.main()
