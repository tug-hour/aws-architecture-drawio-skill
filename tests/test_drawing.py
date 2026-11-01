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


class PartTests(unittest.TestCase):
    def test_create_catalog_and_uncatalogued_shapes_is_expanded_and_nonmutating(self):
        from parts import add_part
        source = {'format': 'drawio/1', 'elements': {}}
        made, info = add_part(source, 'kms', asset='aws4.key_management_service', name='AWS Key Management Service', at=(100, 100), role='暗号化')
        self.assertEqual(source['elements'], {})
        self.assertEqual(made['elements']['kms']['bounds'], [100, 100, 80, 80])
        self.assertEqual(made['elements']['kms.name']['value'], 'AWS Key Management Service')
        self.assertEqual(made['elements']['kms.glyph']['overrides']['fillColor'], '#FFFFFF')
        made, _ = add_part(made, 'custom', shape='mxgraph.aws4.future_service', color='#ED7100',
                           name='Example service', at=(400, 100), theme='dark')
        xml = author_document(made)
        self.assertIn('mxgraph.aws4.future_service', xml)
        self.assertEqual(made['elements']['custom.name']['overrides']['fontColor'], '#FFFFFF')
        self.assertNotIn('template', made)
        for asset in ['group.region', 'group.availability-zone', 'group.aws-cloud']:
            frame, _ = add_part(source, 'frame', asset=asset, at=(0, 0))
            self.assertEqual(frame['elements']['frame']['overrides']['fillColor'], 'none')
            self.assertIn('mxGraphModel', author_document(frame))
        resource, _ = add_part(source, 'stream', asset='aws4.dynamodb_stream', at=(0, 0))
        self.assertEqual(resource['elements']['stream']['bounds'][2:], [48, 48])
        frame, _ = add_part(source, 'asg', asset='group.auto-scaling', at=(0, 0))
        self.assertEqual(frame['elements']['asg']['overrides']['container'], 0)
        self.assertEqual(frame['elements']['asg.glyph']['bounds'], [280, 0, 40, 40])
        self.assertEqual(frame['elements']['asg.name']['bounds'][1], 44)
        cloud, _ = add_part(source, 'cloud', asset='group.aws-cloud', at=(0, 0), theme='dark')
        self.assertEqual(cloud['elements']['cloud.header-base']['overrides']['fillColor'], '#FFFFFF')
        self.assertEqual(cloud['elements']['cloud.glyph']['overrides']['fillColor'], '#232F3E')

    def test_copy_remaps_subtrees_internal_edges_and_conflicting_styles(self):
        from parts import copy_part
        source = document()
        source['elements']['external'] = {'bounds': [900, 100, 80, 80], 'style': 'service'}
        source['elements']['boundary'] = {'source': 'b', 'target': 'external', 'style': 'wire'}
        before = copy.deepcopy(source)
        target = {'format': 'drawio/1', 'styles': {'service': {'shape': 'rect'}}, 'elements': {}}
        made, info = copy_part(source, 'region', target=target, prefix='copy.', offset=(10, 20))
        self.assertEqual(source, before)
        self.assertNotIn('copy.boundary', made['elements'])
        self.assertEqual(info['affected_edges'], ['boundary'])
        self.assertEqual(made['elements']['copy.ab']['source'], 'copy.a')
        self.assertEqual(made['elements']['copy.label']['parent'], 'copy.a')
        self.assertEqual(made['elements']['copy.region']['bounds'][:2], [110, 120])
        self.assertEqual(made['elements']['copy.ab']['waypoints'], [[200, 80]])
        self.assertEqual(made['elements']['copy.a']['style'], 'copy.service')
        self.assertEqual(made['styles']['service'], {'shape': 'rect'})
        self.assertTrue(author_document(made))
        with self.assertRaises(Failure):
            copy_part(made, 'copy.region', prefix='')

    def test_copy_parent_coordinates_and_edge_outside_subtree(self):
        from parts import copy_part
        source = document()
        source['elements']['ab']['parent'] = '1'
        source['elements']['ab']['waypoints'] = [[300, 180]]
        source['elements']['dest'] = {'bounds': [800, 500, 600, 300], 'style': 'group'}
        made, _ = copy_part(source, ['a', 'b'], prefix='c.', parent='dest', offset=(10, 20))
        self.assertEqual(made['elements']['c.a']['bounds'][:2], [30, 60])
        self.assertEqual(made['elements']['c.b']['bounds'][:2], [410, 60])
        self.assertEqual(made['elements']['c.ab']['waypoints'], [[210, 100]])
        self.assertEqual(made['elements']['c.ab']['parent'], 'dest')
        self.assertTrue(author_document(made))
        source['elements']['c'] = {'parent': 'dest', 'bounds': [20, 40, 80, 80], 'style': 'service'}
        reversed_order, _ = copy_part(source, ['c', 'a'], prefix='r.', parent='1', offset=(10, 20))
        self.assertEqual(reversed_order['elements']['r.c']['bounds'][:2], [30, 60])
        self.assertEqual(reversed_order['elements']['r.a']['bounds'][:2], [-670, -340])

    def test_move_subtree_keeps_relative_routes_and_fixed_boundary_waypoints(self):
        from parts import move_part
        source = document()
        source['elements']['external'] = {'bounds': [900, 100, 80, 80], 'style': 'service'}
        source['elements']['boundary'] = {'parent': 'region', 'source': 'b', 'target': 'external',
                                         'style': 'wire', 'waypoints': [[550, 80]]}
        made, info = move_part(source, 'region', offset=(50, 60))
        self.assertEqual(made['elements']['a'], source['elements']['a'])
        self.assertEqual(made['elements']['ab'], source['elements']['ab'])
        self.assertEqual(made['elements']['external'], source['elements']['external'])
        self.assertEqual(made['elements']['boundary']['parent'], '1')
        self.assertEqual(made['elements']['boundary']['waypoints'], [[650, 180]])
        self.assertEqual(info['affected_edges'], ['boundary'])
        with self.assertRaises(Failure):
            move_part(source, 'region', parent='a')

    def test_move_multiple_roots_preserves_valid_edge_parent(self):
        from parts import move_part
        source = document()
        source['elements']['ab']['parent'] = '1'
        source['elements']['ab']['waypoints'] = [[300, 180]]
        source['elements']['dest'] = {'bounds': [800, 500, 600, 300], 'style': 'group'}
        made, info = move_part(source, ['a', 'b'], parent='dest', offset=(100, 100))
        self.assertEqual(made['elements']['a']['bounds'][:2], [-580, -260])
        self.assertEqual(made['elements']['ab']['parent'], '1')
        self.assertEqual(made['elements']['ab']['waypoints'], [[400, 280]])
        self.assertEqual(made['elements']['label'], source['elements']['label'])
        self.assertEqual(info['affected_edges'], [])
        self.assertTrue(author_document(made))
        translated, _ = move_part(source, ['a', 'b'], offset=(10, 20))
        self.assertEqual(translated['elements']['ab']['parent'], '1')
        self.assertEqual(translated['elements']['ab']['waypoints'], [[310, 200]])

    def test_normal_cli_imports_no_legacy_and_old_api_remains_available(self):
        command = [sys.executable, '-B', '-c',
                   "import sys;sys.path.insert(0,sys.argv[1]);import build_drawio;"
                   "assert 'schema' not in sys.modules;assert 'layout' not in sys.modules;"
                   "from build_drawio import normalize;from schema import Failure;"
                   "from input_common import Failure as Common;assert Failure is Common", str(ROOT/'scripts')]
        result = subprocess.run(command, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == '__main__':
    unittest.main()
