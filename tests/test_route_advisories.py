import copy
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from routing import review_warnings, route_quality, readability
from quality import operational_quality
from build_drawio import normalize, author
from catalog import manifest
from layout import layout


class RouteAdvisoryTests(unittest.TestCase):
    def inspect(self, routes, groups=(), nodes=None):
        nodes = nodes or [{'id': 's'}, {'id': 't'}]
        a = {'nodes': nodes, 'groups': list(groups),
             'edges': [{'id': e['id'], 'source': 's', 'target': 't'} for e in routes]}
        original = copy.deepcopy((a, routes, groups))
        result = review_warnings(a, routes, groups)
        self.assertEqual((a, routes, groups), original)
        return result

    def frame(self, **values):
        return dict({'id': 'g', 'role': 'containment', 'x': 20, 'y': 20, 'w': 60, 'h': 60}, **values)

    def test_unrelated_frame_transit_is_one_warning_per_edge_and_frame(self):
        route = {'id': 'e', 'points': [[0, 40], [50, 40], [50, 60], [100, 60]]}
        warnings = self.inspect([route], [self.frame()])
        self.assertEqual(len(warnings), 1)
        self.assertEqual(warnings[0]['code'], 'W_EDGE_FRAME_TRANSIT')
        self.assertEqual(warnings[0]['element_ids'], ['e', 'g'])
        self.assertEqual(warnings[0]['details']['segment_indices'], [0, 1, 2])

    def test_frame_boundary_touch_and_outside_are_not_transit(self):
        for points in ([[0,20],[100,20]], [[0,50],[20,50]], [[0,10],[100,10]]):
            with self.subTest(points=points):
                self.assertFalse(self.inspect([{'id':'e','points':points}], [self.frame()]))

    def test_endpoint_frames_and_all_ancestors_are_excluded(self):
        groups = [self.frame(id='outer'), self.frame(id='middle',parent_id='outer'),
                  self.frame(id='child',parent_id='middle'), self.frame(id='target')]
        nodes = [{'id':'s','group_id':'child'}, {'id':'t','group_id':'target'}]
        self.assertFalse(self.inspect([{'id':'e','points':[[0,50],[100,50]]}], groups, nodes))

    def test_sibling_is_unrelated_and_overlay_is_excluded(self):
        groups = [self.frame(id='own'), self.frame(id='sibling'), self.frame(id='overlay',role='overlay')]
        nodes = [{'id':'s','group_id':'own'}, {'id':'t'}]
        warnings = self.inspect([{'id':'e','points':[[0,50],[100,50]]}], groups, nodes)
        self.assertEqual([w['element_ids'] for w in warnings], [['e','sibling']])

    def test_corner_contact_is_deduplicated(self):
        routes = [{'id':'a','points':[[0,0],[50,0],[50,50],[100,50]]},
                  {'id':'b','points':[[0,100],[50,100],[50,50],[0,50]]}]
        self.assertEqual(route_quality(routes)['crossings'], 0)
        warnings = self.inspect(routes)
        self.assertEqual(len(warnings), 1)
        self.assertEqual(warnings[0]['code'], 'W_EDGE_CONTACT')
        self.assertEqual(len(warnings[0]['details']['contacts']), 1)
        self.assertEqual(warnings[0]['details']['contacts'][0]['point_pt'], [50,50])

    def test_endpoint_touching_another_wire_interior_is_reported(self):
        routes = [{'id':'a','points':[[0,50],[100,50]]}, {'id':'b','points':[[50,0],[50,50]]}]
        self.assertEqual(self.inspect(routes)[0]['code'], 'W_EDGE_CONTACT')

    def test_existing_crossing_overlap_and_endpoint_diagnostics_are_not_repeated(self):
        for second in ([[50,0],[50,100]], [[20,50],[80,50]], [[100,50],[100,100]]):
            with self.subTest(second=second):
                routes = [{'id':'a','points':[[0,50],[100,50]]}, {'id':'b','points':second}]
                self.assertFalse(self.inspect(routes))
        _, warnings = readability([{'id':'a','points':[[0,50],[100,50]]},
                                   {'id':'b','points':[[100,50],[100,100]]}])
        self.assertIn('W_PORT_PROXIMITY', {w['code'] for w in warnings})

    def test_near_but_disjoint_lines_are_not_contacts(self):
        self.assertFalse(self.inspect([{'id':'a','points':[[0,50],[100,50]]},
                                       {'id':'b','points':[[50,0],[50,49]]}]))

    def test_two_contacts_on_same_pair_are_preserved_once_each(self):
        routes = [{'id':'a','points':[[0,50],[100,50]]},
                  {'id':'b','points':[[20,50],[20,0],[80,0],[80,50]]}]
        warnings = self.inspect(routes)
        self.assertEqual(len(warnings), 1)
        self.assertEqual([c['point_pt'] for c in warnings[0]['details']['contacts']], [[20,50],[80,50]])

    def test_operational_review_does_not_change_generation_status(self):
        for code in ('W_EDGE_FRAME_TRANSIT', 'W_EDGE_CONTACT'):
            result = {'status':'passed','production_eligible':True,'warnings':[{'code':code}]}
            original = copy.deepcopy(result)
            gate = operational_quality(result, {'canvas':{'width_pt':500,'height_pt':300}},
                                       {'width_px':1920,'height_px':1080,'min_text_px':12})
            self.assertEqual(gate['status'], 'needs-review-or-split')
            self.assertEqual(gate['blocking_warnings'], [code])
            self.assertEqual(result, original)

    def test_independent_transit_is_warned_without_rejecting_or_rerouting(self):
        a = normalize({
            'schema_version':'1.0', 'mode':'draft',
            'nodes':[{'id':i,'asset_id':'aws4.lambda', **({'group_id':'g'} if i == 'inside' else {})}
                     for i in ('s','t','inside')],
            'groups':[{'id':'g','type':'group.private-subnet','role':'containment','label':'Subnet'}],
            'edges':[{'id':'e','source':'s','target':'t'}],
            'layout':{'mode':'manual','positions':[
                {'node_id':'s','x_pt':100,'y_pt':250},
                {'node_id':'t','x_pt':700,'y_pt':250},
                {'node_id':'inside','x_pt':400,'y_pt':300}]}}, manifest())
        original = copy.deepcopy(a)
        with patch('routing.review_warnings', return_value=[]):
            baseline, _ = layout(a, manifest())
        observed, warnings = layout(a, manifest())
        self.assertEqual(a, original)
        self.assertEqual(observed, baseline)
        matches = [w for w in warnings if w['code'] == 'W_EDGE_FRAME_TRANSIT'
                   and w['element_ids'] == ['e','g']]
        self.assertEqual(len(matches), 1)

    def test_layout_and_both_theme_models_are_unchanged_by_advisories(self):
        m = manifest()
        a = normalize({'schema_version':'1.0','nodes':[{'id':i,'asset_id':'aws4.lambda'} for i in ('a','b')],
                       'edges':[{'id':'e','source':'a','target':'b'}],
                       'glossary':[{'asset_id':'aws4.lambda','kind':'note','short_name':'note','full_name':'test'}]}, m)
        baseline, previous = layout(a, m)
        warning = {'code':'W_EDGE_CONTACT','element_ids':['e','test']}
        with patch('routing.review_warnings', return_value=[warning]) as check:
            observed, warnings = layout(a, m)
        self.assertEqual(observed, baseline)
        self.assertEqual(check.call_args.args[1], observed['edges'])
        self.assertEqual(check.call_args.args[2], observed['groups'])
        self.assertEqual(warnings, previous + [warning])
        for theme in ('light', 'dark'):
            self.assertEqual(author(a, baseline, m, theme), author(a, observed, m, theme))


if __name__ == '__main__':
    unittest.main()
