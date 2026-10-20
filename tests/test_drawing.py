"""Explicit JSON drawings keep unrelated geometry and routes unchanged."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from drawing import author_document, generate
from schema import Failure


def document():
    return {
        'format': 'drawio/1',
        'styles': {
            'group': {'group': None, 'recursiveResize': 0},
            'service': {'shape': 'mxgraph.aws4.not_in_catalog', 'fillColor': '#ED7100'},
            'wire': {'endArrow': 'open', 'endSize': 6, 'strokeWidth': 1.6667},
        },
        'elements': {
            'region': {'bounds': [100, 100, 600, 300], 'style': 'group'},
            'a': {'parent': 'region', 'bounds': [20, 40, 80, 80], 'style': 'service'},
            'label': {'parent': 'a', 'bounds': [-30, 84, 140, 21],
                      'value': '日本語 & <label>', 'overrides': {'text': None}},
            'b': {'parent': 'region', 'bounds': [400, 40, 80, 80], 'style': 'service'},
            'ab': {'parent': 'region', 'source': 'a', 'target': 'b', 'style': 'wire',
                   'source_port': [1, .5], 'target_port': [0, .5],
                   'waypoints': [[200, 80]]},
        },
    }


class DrawingTests(unittest.TestCase):
    def test_native_shapes_nested_geometry_labels_and_explicit_routes(self):
        source = document()
        before = copy.deepcopy(source)
        root = ET.fromstring(author_document(source))
        self.assertEqual(source, before)
        self.assertEqual(root.find('.//mxGraphModel').get('adaptiveColors'), 'none')
        cells = {c.get('id'): c for c in root.iter('mxCell')}
        self.assertEqual(cells['label'].get('value'), '日本語 & <label>')
        self.assertEqual(cells['label'].get('parent'), 'a')
        self.assertEqual(cells['a'].find('mxGeometry').get('x'), '20')
        self.assertIn('shape=mxgraph.aws4.not_in_catalog;', cells['a'].get('style'))
        self.assertIn('exitY=0.5;', cells['ab'].get('style'))
        self.assertEqual(cells['ab'].find('.//mxPoint').attrib, {'x': '200', 'y': '80'})
        self.assertEqual(cells['ab'].get('target'), 'b')

    def test_local_add_move_and_reroute_preserve_other_cells_and_source(self):
        source = document()
        before = author_document(source)
        changed = copy.deepcopy(source)
        changed['elements']['a']['bounds'][1] += 20
        changed['elements']['ab']['waypoints'] = [[200, 100], [200, 80]]
        changed['elements']['c'] = {'bounds': [20, 450, 80, 80], 'style': 'service'}
        after = author_document(changed)
        cells = lambda xml: {c.get('id'): ET.tostring(c) for c in ET.fromstring(xml).iter('mxCell')}
        old, new = cells(before), cells(after)
        self.assertEqual({k for k in old if old[k] != new[k]}, {'a', 'ab'})
        self.assertEqual(set(new) - set(old), {'c'})
        self.assertEqual(before, author_document(source))

    def test_bad_references_cycles_nonfinite_and_conflicting_ports_are_not_silent(self):
        cases = []
        a = document(); a['elements']['ab']['target'] = 'missing'; cases.append(a)
        a = document(); a['elements']['region']['parent'] = 'a'; cases.append(a)
        a = document(); a['elements']['a']['bounds'][0] = float('inf'); cases.append(a)
        a = document(); a['elements']['ab']['overrides'] = {'exitX': .2}; cases.append(a)
        a = document(); a['elements']['a']['style'] = 'missing'; cases.append(a)
        for source in cases:
            with self.subTest(source=source), self.assertRaises(Failure):
                author_document(source)

    def test_cli_needs_no_drawio_browser_and_preserves_existing_output(self):
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder); source = folder / 'source.json'; output = folder / 'out'
            data = json.dumps(document()).encode()
            source.write_bytes(data)
            command = [sys.executable, '-B', str(ROOT / 'scripts/build_drawio.py'),
                       '--input', str(source), '--output', str(output)]
            result = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            self.assertEqual(json.loads(result.stdout)['status'], 'authored')
            self.assertEqual(source.read_bytes(), data)
            saved = {p.name: p.read_bytes() for p in output.iterdir()}
            self.assertEqual(saved['architecture.json'], data)
            self.assertTrue(ET.fromstring(saved['diagram.drawio']).findall('.//mxCell'))
            result = subprocess.run(command, capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(saved, {p.name: p.read_bytes() for p in output.iterdir()})

    def test_invalid_xml_text_or_attribute_is_not_reported_as_authored(self):
        for change in ('text', 'attribute'):
            source = document()
            if change == 'text':
                source['elements']['label']['value'] = 'a\0b'
            else:
                source['page'] = {'model': {'bad attribute': 'x'}}
            with self.subTest(change=change), self.assertRaises(Failure):
                author_document(source)

    def test_source_copy_and_xml_use_one_snapshot_even_if_input_changes(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / 'source.json'; output = Path(folder) / 'out'
            original = json.dumps(document()).encode()
            source.write_bytes(original)
            changed = document(); changed['elements']['label']['value'] = 'Changed externally'
            read_bytes = Path.read_bytes
            def read_then_change(path):
                data = read_bytes(path)
                if path == source:
                    source.write_text(json.dumps(changed))
                return data
            with patch.object(Path, 'read_bytes', read_then_change):
                generate(source, output)
            self.assertEqual((output / 'architecture.json').read_bytes(), original)
            cells = ET.parse(output / 'diagram.drawio')
            self.assertEqual(cells.find(".//mxCell[@id='label']").get('value'), '日本語 & <label>')


if __name__ == '__main__':
    unittest.main()
