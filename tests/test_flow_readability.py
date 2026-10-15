import json,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from build_drawio import normalize
from catalog import manifest
from layout import layout
from schema import Failure
from routing import search,readability,border_exposure

class FlowReadabilityTests(unittest.TestCase):
 def setUp(self):self.a=json.loads((ROOT/'examples/real-world/multi-region-dr.json').read_text());self.m=manifest()
 def error(self,code):
  with self.assertRaises(Failure) as ctx:normalize(self.a,self.m)
  self.assertEqual(ctx.exception.issue['code'],code)
 def test_route53_cannot_replace_api_traffic(self):
  next(e for e in self.a['edges'] if e['id']=='apit')['source']='dns';self.error('E_DNS_DATA_PATH')
 def test_served_frontend_must_reach_api(self):
  next(e for e in self.a['edges'] if e['id']=='apit')['source']='tclient';self.error('E_FRONTEND_API_PATH')
 def test_each_reader_has_real_client_or_failover_connection(self):
  self.a['edges']=[e for e in self.a['edges'] if e['id']!='treader'];self.error('E_DB_CLIENT_PATH')
 def test_standby_reader_path_is_conditional(self):
  next(e for e in self.a['edges'] if e['id']=='oreader')['purpose']='traffic';self.error('E_DB_CLIENT_PATH')
 def test_queue_must_have_a_producer_path(self):
  next(e for e in self.a['edges'] if e['id']=='tjob')['direction']='forward';self.error('E_QUEUE_PRODUCER_PATH')
 def test_production_orphan_is_rejected(self):
  a={'schema_version':'1.0','nodes':[{'id':i,'asset_id':'aws4.lambda'} for i in ('a','b','c')],'edges':[{'id':'e','source':'a','target':'b'}]}
  with self.assertRaises(Failure) as ctx:normalize(a,self.m)
  self.assertEqual(ctx.exception.issue['code'],'E_ORPHAN_NODE')
  a['mode']='draft';self.assertEqual(normalize(a,self.m)['mode'],'draft')
 def test_aligned_pair_is_straight_despite_other_ports(self):
  a={'schema_version':'1.0','nodes':[{'id':i,'asset_id':'aws4.lambda'} for i in ('a','b','c')],'edges':[{'id':'direct','source':'a','target':'b'},{'id':'other','source':'a','target':'c'}],'layout':{'mode':'manual','positions':[{'node_id':'a','x_pt':100,'y_pt':100},{'node_id':'b','x_pt':450,'y_pt':100},{'node_id':'c','x_pt':450,'y_pt':450}]}}
  lay,_=layout(normalize(a,self.m),self.m);self.assertEqual(len(next(e for e in lay['edges'] if e['id']=='direct')['points']),2)
 def test_blank_header_area_is_available_to_wire(self):
  a={'schema_version':'1.0','nodes':[{'id':'source','asset_id':'aws4.lambda'},{'id':'inside','asset_id':'aws4.lambda','group_id':'g'},{'id':'left','asset_id':'aws4.lambda','group_id':'g'}],'groups':[{'id':'g','type':'group.region','role':'containment','label':'Region'}],'edges':[{'id':'e','source':'source','target':'inside','source_side':'right','target_side':'top'},{'id':'l','source':'source','target':'left'}],'layout':{'mode':'manual','positions':[{'node_id':'source','x_pt':0,'y_pt':0},{'node_id':'inside','x_pt':600,'y_pt':350},{'node_id':'left','x_pt':300,'y_pt':350}]}}
  lay,_=layout(normalize(a,self.m),self.m);g=lay['groups'][0];self.assertLess(g['header_w'],g['w']/2)
 def test_parallel_frame_proximity_is_reported(self):
  frame={'id':'vpc','x':10,'y':10,'w':100,'h':100}
  self.assertEqual(border_exposure([12,20],[12,100],frame),80)
  q,w=readability([{'id':'e','points':[[12,20],[12,100]]}],[frame]);self.assertIn('W_FRAME_WIRE_PROXIMITY',{x['code'] for x in w})
  self.assertEqual(border_exposure([0,50],[200,50],frame),0)
 def test_relaxed_padding_validated(self):
  self.a['layout']['frame_padding_pt']=2;self.error('E_LAYOUT_PADDING')


class AdditionalReadabilityTests(unittest.TestCase):
 def test_connection_label_does_not_straddle_frame_border(self):
  from connection_labels import place
  a={'edges':[{'id':'e','label':'HTTPS'}]};g={'id':'g','x':200,'y':10,'w':200,'h':180,'role':'containment','header_w':60};r=[{'id':'e','points':[[50,100],[350,100]]}]
  b=place(a,[],[g],r,500,300,None)[0];self.assertTrue(b['x']+b['w']<g['x'] or b['x']>g['x']+g['w'])
 def test_acceptance_snapshot_detects_changed_code(self):
  from release_source import snapshot
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);(root/'scripts').mkdir();(root/'references').mkdir();(root/'SKILL.md').write_text('skill')
   for name in ('native-catalog.json','verified-assets.json','acceptance-contracts.json','service-names.json','version.json'):(root/'references'/name).write_text('{}')
   p=root/'scripts/a.py';p.write_text('value=1');before=snapshot(root);p.write_text('value=2');self.assertNotEqual(before,snapshot(root))
 def test_border_cost_moves_parallel_wire_away_from_frame(self):
  frame={'id':'g','x':0,'y':0,'w':100,'h':100}
  direct=search((10,10),(90,10),[],[],120,120)
  spaced=search((10,10),(90,10),[],[],120,120,frames=[frame])
  total=lambda p:sum(border_exposure(u,v,frame) for u,v in zip(p,p[1:]))
  self.assertLess(total(spaced),total(direct))
 def test_repeated_actor_identity_rejects_different_asset(self):
  a=json.loads((ROOT/'examples/real-world/multi-region-dr.json').read_text());next(n for n in a['nodes'] if n['id']=='browserdr')['asset_id']='aws4.client'
  with self.assertRaises(Failure) as ctx:normalize(a,manifest())
  self.assertEqual(ctx.exception.issue['code'],'E_NODE_IDENTITY')

import os,tempfile
from run import run
from verify_native import points
from routing import rect_hit
@unittest.skipUnless(os.environ.get('AWS_NATIVE_DRAWIO_RUNTIME'),'Approved native render runtime not specified')
class InkBoundsIntegration(unittest.TestCase):
 native_render = True
 def test_blank_label_hitbox_does_not_block_actual_wire(self):
  a={'schema_version':'1.0','theme':'both','nodes':[{'id':'source','asset_id':'aws4.lambda'},{'id':'inside','asset_id':'aws4.lambda','group_id':'g'},{'id':'left','asset_id':'aws4.lambda','group_id':'g'}],'groups':[{'id':'g','type':'group.region','role':'containment','label':'Region'}],'edges':[{'id':'e','source':'source','target':'inside','source_side':'right','target_side':'top'},{'id':'l','source':'source','target':'left'}],'layout':{'mode':'manual','positions':[{'node_id':'source','x_pt':0,'y_pt':0},{'node_id':'inside','x_pt':600,'y_pt':350},{'node_id':'left','x_pt':300,'y_pt':350}]}}
  with tempfile.TemporaryDirectory() as d:
   base=Path(d);p=base/'input.json';p.write_text(json.dumps(a));r,code=run(p,base/'out',Path(os.environ.get('AWS_DRAWIO_BINARY','/Applications/draw.io.app/Contents/MacOS/draw.io')),Path(os.environ['AWS_DRAWIO_PROFILE']),Path(os.environ['AWS_NATIVE_DRAWIO_RUNTIME']));self.assertEqual(code,0,r.get('errors'))
   v=r['themes']['light'];label=next(l for l in v['labels'] if l['id']=='header.label.g');self.assertLess(label['w'],label['cell_box']['w']/2)
   edge=next(e for e in v['edges'] if e['id']=='edge.e');route=max((points(p['d']) for p in edge['paths']),key=len)
   self.assertTrue(any(rect_hit(p,q,label['cell_box']) for p,q in zip(route,route[1:])))
   self.assertFalse(any(rect_hit(p,q,label) for p,q in zip(route,route[1:])))

if __name__=='__main__':unittest.main()
