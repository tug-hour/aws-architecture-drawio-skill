"""Release acceptance contracts and routing/label regressions."""
import json
import sys
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from build_drawio import normalize,author
from catalog import manifest
from layout import layout
from routing import search,route_quality
from schema import Failure
from integrity import compare_model

class ReleaseTests(unittest.TestCase):
    def test_connection_label_is_visible_and_bound_to_input(self):
        m=manifest();a=json.loads((ROOT/'examples/japanese-auto.json').read_text());a['edges'][0]['label']='HTTPS';a=normalize(a,m);lay,_=layout(a,m)
        self.assertEqual(lay['connection_labels'][0]['text'],'HTTPS');xml=author(a,lay,m,'light');self.assertIn('connection.label.write',xml)
        with self.assertRaises(Failure):compare_model(xml.replace('value="HTTPS"','value="SQL"'),xml,'light')
    def test_invalid_connection_labels_are_rejected(self):
        for label in ('','two\nlines','x'*81,None):
            a=json.loads((ROOT/'examples/japanese-auto.json').read_text());a['edges'][0]['label']=label
            with self.assertRaises(Failure):normalize(a,manifest())
    def test_explicit_ports_are_validated(self):
        a=json.loads((ROOT/'examples/japanese-auto.json').read_text());a['edges'][0]['source_side']='diagonal'
        with self.assertRaises(Failure) as ctx:normalize(a,manifest())
        self.assertEqual(ctx.exception.issue['code'],'E_EDGE_PORT')
    def test_spatial_port_order_reduces_fanout_crossings(self):
        a={'schema_version':'1.0','nodes':[{'id':'s','asset_id':'aws4.lambda'},{'id':'t','asset_id':'aws4.s3'},{'id':'b','asset_id':'aws4.dynamodb'}],'edges':[{'id':'a-bottom','source':'s','target':'b'},{'id':'z-top','source':'s','target':'t'}],'layout':{'mode':'manual','positions':[{'node_id':'s','x_pt':100,'y_pt':200},{'node_id':'t','x_pt':400,'y_pt':100},{'node_id':'b','x_pt':400,'y_pt':400}]}}
        lay,_=layout(normalize(a,manifest()),manifest());edges={e['id']:e for e in lay['edges']}
        self.assertLess(edges['z-top']['source_port'][1],edges['a-bottom']['source_port'][1]);self.assertEqual(lay['routing_quality']['crossings'],0)
    def test_crossing_penalty_detours_an_existing_wire(self):
        obstacle=[((50,10),(50,90))]
        old=search((10,50),(90,50),[],obstacle,100,100,crossing_penalty=0)
        new=search((10,50),(90,50),[],obstacle,100,100,crossing_penalty=120)
        def crossings(p):return route_quality([{'id':'existing','points':list(obstacle[0])},{'id':'new','points':p}])['crossings']
        self.assertEqual(crossings(old),1);self.assertEqual(crossings(new),0)
    def test_foreign_managed_service_inside_vpc_frame_is_rejected(self):
        a={'schema_version':'1.0','nodes':[{'id':'a','asset_id':'aws4.lambda','group_id':'vpc'},{'id':'b','asset_id':'aws4.lambda','group_id':'vpc'},{'id':'external','asset_id':'aws4.dynamodb'}],'edges':[],'groups':[{'id':'vpc','type':'group.vpc','role':'containment'}],'layout':{'mode':'manual','positions':[{'node_id':'a','x_pt':100,'y_pt':100},{'node_id':'b','x_pt':400,'y_pt':400},{'node_id':'external','x_pt':300,'y_pt':200}]}}
        with self.assertRaises(Failure) as ctx:layout(normalize(a,manifest()),manifest())
        self.assertEqual(ctx.exception.issue['code'],'E_GROUP_VISUAL_MEMBERSHIP')
    def test_real_world_topology_contracts(self):
        contracts=json.loads((ROOT/'references/acceptance-contracts.json').read_text());m=manifest()
        for name,contract in contracts.items():
            a=normalize(json.loads((ROOT/'examples/real-world'/(name+'.json')).read_text()),m);assets={n['asset_id'] for n in a['nodes']}
            with self.subTest(name=name):
                self.assertTrue(set(contract.get('must_assets',[]))<=assets)
                self.assertGreaterEqual(sum(g['type']=='group.availability-zone' for g in a['groups']),contract['min_az'])
                self.assertGreaterEqual(sum(g['type']=='group.region' for g in a['groups']),contract.get('min_region',0))
                if contract.get('availability_required'):self.assertIn('availability',a)
                if contract.get('all_verified'):self.assertEqual(assets,{k for k,v in m['assets'].items() if v.get('support_status')=='verified'})
    def test_database_is_not_drawn_as_a_direct_iot_publisher(self):
        for name in ('asynchronous','realtime-streaming'):
            a=json.loads((ROOT/'examples/real-world'/(name+'.json')).read_text());nodes={n['id']:n for n in a['nodes']}
            for e in a['edges']:
                if nodes[e['target']]['asset_id']=='aws4.iot_core':self.assertEqual(nodes[e['source']]['asset_id'],'aws4.lambda')

if __name__=='__main__':unittest.main()
