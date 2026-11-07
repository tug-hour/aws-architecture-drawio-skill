import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from batch import apply_operations
from drawing import generate
from input_common import Failure
from test_drawing import document


class BatchTests(unittest.TestCase):
    def test_operations_and_atomic_failure(self):
        source = document()
        before = copy.deepcopy(source)
        ops = [{'op': 'copy', 'roots': ['a'], 'prefix': 'new-', 'offset': [5, 0]},
               {'op': 'set', 'id': 'ab', 'fields': {'waypoints': [[3, 4]], 'source_port': [1, .25],
                                                    'overrides': {'strokeWidth': 2}}},
               {'op': 'move', 'roots': ['b'], 'offset': [0, 10]},
               {'op': 'add', 'id': 'custom', 'at': [0, 0], 'shape': 'mxgraph.example.unknown', 'color': '#123456'}]
        result, report = apply_operations(source, ops)
        self.assertEqual(source, before)
        self.assertEqual(report[0]['ids']['a'], 'new-a')
        self.assertIn('ab', report[2]['affected_edges'])
        self.assertEqual(result['elements']['ab']['waypoints'], [[3, 4]])
        self.assertIn('custom.glyph', result['elements'])
        with self.assertRaises(Failure):
            apply_operations(source, ops + [{'op': 'set', 'id': 'missing', 'fields': {'value': 'x'}}])
        self.assertEqual(source, before)

    def test_put_and_remove_validate_final_references(self):
        source = document()
        changed, results = apply_operations(source, [
            {'op': 'remove', 'id': 'ab'},
            {'op': 'put', 'id': 'wire2', 'element': {'source': 'a', 'target': 'b', 'waypoints': []}},
        ])
        self.assertNotIn('ab', changed['elements'])
        self.assertEqual(results[1]['affected_edges'], ['wire2'])
        with self.assertRaises(Failure):
            apply_operations(source, [{'op': 'remove', 'id': 'a'}])
        self.assertIn('a', source['elements'])

    def test_set_reports_edges_owned_by_moved_frame(self):
        source = document()
        source['elements']['frame'] = {'bounds': [0, 0, 100, 100]}
        source['elements']['ab']['parent'] = 'frame'
        _, report = apply_operations(source, [
            {'op': 'set', 'id': 'frame', 'fields': {'bounds': [20, 0, 100, 100]}}
        ])
        self.assertIn('ab', report[0]['affected_edges'])

    def test_replacing_endpoint_reports_existing_wire(self):
        source = document()
        replacement = copy.deepcopy(source['elements']['a'])
        replacement['bounds'][0] += 50
        _, results = apply_operations(source, [
            {'op': 'remove', 'id': 'a'},
            {'op': 'put', 'id': 'a', 'element': replacement},
        ])
        self.assertIn('ab', results[0]['affected_edges'])
        self.assertIn('ab', results[1]['affected_edges'])

    def test_generate_saves_transformed_source_and_results_without_overwrite(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / 'in.json'
            source.write_text(json.dumps(document()))
            operations = root / 'ops.json'
            operations.write_text(json.dumps({'operations': [{'op': 'set', 'id': 'a', 'fields': {'value': 'changed'}}]}))
            output = root / 'out'
            report, _ = generate(source, output, operations)
            self.assertEqual(json.loads((output / 'architecture.json').read_text())['elements']['a']['value'], 'changed')
            self.assertEqual(report['operations'][0]['ids'], {'a': 'a'})
            self.assertEqual(json.loads((output / 'report.json').read_text())['operations'], report['operations'])
            with self.assertRaises(Failure):
                generate(source, output, operations)


if __name__ == '__main__':
    unittest.main()
