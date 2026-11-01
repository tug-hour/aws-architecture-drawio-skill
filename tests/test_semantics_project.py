import copy,json,sys,unittest,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from build_drawio import normalize
from catalog import manifest
from schema import Failure
from project import project_views,display_quality
from semantics import validate_semantics
from quality import operational_quality
from corpus import fixtures
from layout import layout

class GenericFlowTests(unittest.TestCase):
 def setUp(self):
  self.a={'schema_version':'1.0','nodes':[{'id':i,'asset_id':'aws4.lambda'} for i in 'abcd'],'edges':[{'id':s+t,'source':s,'target':t,'purpose':'traffic','label':'処理'} for s,t in zip('abc','bcd')],'semantics':{'flows':[{'id':'end-to-end','kind':'custom','phase':'normal','path':['a','b','c','d']}]}}
 def error(self,code):
  with self.assertRaises(Failure) as c:normalize(self.a,manifest())
  self.assertEqual(c.exception.issue['code'],code)
 def test_missing_path_despite_connected_nodes(self):
  self.a['edges'][1]['source']='a';self.error('E_FLOW_PATH')
 def test_reverse_direction_fails(self):
  self.a['edges'][1].update(source='c',target='b');self.error('E_FLOW_PATH')
 def test_association_is_not_traffic(self):
  self.a['edges'][1].update(purpose='association',direction='none');self.error('E_FLOW_PATH')
 def test_replication_is_not_application_path(self):
  self.a['edges'][1]['purpose']='replication';self.error('E_FLOW_PATH')
 def test_failover_not_available_in_normal_phase(self):
  self.a['edges'][1]['purpose']='failover';self.error('E_FLOW_PATH')
 def test_failover_explicitly_allowed(self):
  self.a['edges'][1]['purpose']='failover';self.a['semantics']['flows'][0]['phase']='failover';self.assertEqual(validate_semantics(normalize(self.a,manifest()))['status'],'passed')
 def test_standby_traffic_rejected(self):
  self.a['semantics']['standby_nodes']=['c'];self.error('E_STANDBY_TRAFFIC')
 def test_dns_cannot_proxy_generic_flow(self):
  self.a['nodes'][1]['asset_id']='aws4.route_53';self.error('E_DNS_DATA_PATH')
 def test_stage_order_required(self):
  self.a['semantics']['flows'][0]['path']=['a','c','b','d'];self.error('E_FLOW_PATH')
 def test_required_edge_direction_binds(self):
  self.a['semantics']['required_edges']=[{'id':'bc','source':'b','target':'c','direction':'both','purpose':'traffic'}];self.error('E_REQUIRED_CONNECTION')
 def test_duplicate_flow_rejected(self):
  self.a['semantics']['flows']*=2;self.error('E_FLOW_SCHEMA')
 def test_unknown_reference_rejected(self):
  self.a['semantics']['flows'][0]['path'].append('missing');self.error('E_FLOW_REFERENCE')

class ProjectTests(unittest.TestCase):
 def setUp(self):self.p=json.loads((ROOT/'examples/projects/modern-web-iot.json').read_text())
 def error(self,code):
  with self.assertRaises(Failure) as c:project_views(self.p)
  self.assertEqual(c.exception.issue['code'],code)
 def test_all_canonical_edges_and_flows_delivered(self):
  model,vs=project_views(self.p);self.assertEqual(set(e['id'] for e in model['edges']),{e['id'] for v in vs.values() for e in v['architecture']['edges']});self.assertEqual(len(vs),13)
 def test_projection_preserves_identity_and_meaning(self):
  model,vs=project_views(self.p);nodes={n['id']:n for n in model['nodes']};edges={e['id']:e for e in model['edges']}
  for v in vs.values():
   for n in v['architecture']['nodes']:self.assertEqual(n,nodes[n['id']])
   for e in v['architecture']['edges']:self.assertEqual(e,edges[e['id']])
 def test_missing_endpoint_rejected(self):
  self.p['views'][0]['node_ids'].remove('tspa');self.error('E_VIEW_ENDPOINT')
 def test_missing_connection_coverage_rejected(self):
  self.p['views']=[v for v in self.p['views'] if v['id']!='observability'];self.error('E_VIEW_COVERAGE')
 def test_missing_flow_coverage_rejected(self):
  self.p['views'][0]['flow_ids'].remove('spa');self.error('E_VIEW_FLOW_COVERAGE')
 def test_no_contract_rejected(self):
  self.p['model'].pop('semantics');self.error('E_PROJECT_CONTRACT')
 def test_path_traversal_rejected(self):
  self.p['views'][0]['id']='../outside';self.error('E_VIEW_ID')
 def test_reserved_view_id_rejected(self):
  self.p['views'][0]['id']='project';self.error('E_VIEW_ID')
 def test_viewport_fail_does_not_shrink_text(self):
  lay={'canvas':{'width_pt':2500,'height_pt':1600}};self.assertEqual(display_quality(lay,{'width_px':1920,'height_px':1080,'min_text_px':12})['status'],'needs-split')
 def test_crossing_blocks_operational_gate(self):
  r={'status':'passed','warnings':[{'code':'W_EDGE_CROSSINGS'}]};g=operational_quality(r,{'canvas':{'width_pt':900,'height_pt':500}},{'width_px':1920,'height_px':1080,'min_text_px':12});self.assertEqual(g['status'],'needs-review-or-split')
 def test_centered_branch_layout_has_no_crossings(self):
  c=fixtures()['fan-4'];lay,w=layout(normalize(c['architecture'],manifest()),manifest());self.assertEqual(lay['routing_quality']['crossings'],0);self.assertFalse(w)
 def test_async_views_keep_subnet_frames_separate(self):
  _,views=project_views(self.p)
  for ident in ('t-async','o-async'):
   with self.subTest(view=ident):
    view=views[ident];lay,warnings=layout(view['architecture'],manifest())
    groups={g['id']:g for g in lay['groups']};prefix=ident[0]
    database=groups[prefix+'dbsuba'];application=groups[prefix+'appa']
    self.assertGreaterEqual(application['y']-(database['y']+database['h']),12)
    self.assertEqual(lay['routing_quality']['crossings'],0)
    self.assertEqual(len(next(e for e in lay['edges'] if e['id']==prefix+'consumeb')['points']),2)
    self.assertFalse(warnings)
    self.assertEqual(display_quality(lay,view['display'])['status'],'passed')
 def test_web_state_access_avoids_database_subnets(self):
  from routing import rect_hit
  _,views=project_views(self.p)
  for ident in ('t-web','o-web'):
   with self.subTest(view=ident):
    view=views[ident];a=view['architecture'];lay,warnings=layout(a,manifest());prefix=ident[0]
    groups={g['id']:g for g in lay['groups']}
    edge=next(e for e in lay['edges'] if e['id']==prefix+'stateaccess')
    for gid in (prefix+'dbsuba',prefix+'dbsubb'):
     self.assertFalse(any(rect_hit(p,q,groups[gid]) for p,q in zip(edge['points'],edge['points'][1:])),gid)
    parents={g['id']:g.get('parent_id') for g in a['groups']}
    ancestors={}
    for gid in groups:
     ancestors[gid]=set();parent=parents[gid]
     while parent:
      ancestors[gid].add(parent);parent=parents[parent]
    frames=[g for g in lay['groups'] if g['role']=='containment']
    for index,g in enumerate(frames):
     for other in frames[index+1:]:
      if g['id'] in ancestors[other['id']] or other['id'] in ancestors[g['id']]:continue
      overlap=max(g['x'],other['x'])<min(g['x']+g['w'],other['x']+other['w']) and max(g['y'],other['y'])<min(g['bottom'],other['bottom'])
      self.assertFalse(overlap,(g['id'],other['id']))
    self.assertEqual(operational_quality({'status':'passed','warnings':warnings},lay,view['display'])['status'],'passed')
 def test_dense_layout_fails_closed(self):
  with self.assertRaises(Failure):layout(normalize(fixtures()['dense-dag']['architecture'],manifest()),manifest())
 def test_three_az_requires_split_at_viewport(self):
  lay,w=layout(normalize(fixtures()['nested-3']['architecture'],manifest()),manifest());self.assertEqual(display_quality(lay,{'width_px':1920,'height_px':1080,'min_text_px':12})['status'],'needs-split')

class ClusterUnitTests(unittest.TestCase):
 def setUp(self):self.p=json.loads((ROOT/'examples/projects/modern-web-iot.json').read_text())
 def test_cluster_replication_cannot_attach_to_instance(self):
  e=next(e for e in self.p['model']['edges'] if e['id']=='replicacluster');e['source']='tdba'
  # Isolate the availability contract from the separate exact-edge contract.
  self.p['model']['semantics']['required_edges']=[]
  self.p['model']['semantics']['flows']=[f for f in self.p['model']['semantics']['flows'] if f['id']!='replicacluster']
  with self.assertRaises(Failure) as c:normalize(self.p['model'],manifest())
  self.assertEqual(c.exception.issue['code'],'E_DB_CLUSTER_UNIT')
 def test_cluster_unit_is_not_a_subnet_endpoint(self):
  next(n for n in self.p['model']['nodes'] if n['id']=='tcluster')['group_id']='tdbsuba'
  with self.assertRaises(Failure) as c:normalize(self.p['model'],manifest())
  self.assertEqual(c.exception.issue['code'],'E_DB_CLUSTER_UNIT')
 def test_missing_az_reader_still_rejected(self):
  self.p['model'].pop('semantics')
  self.p['model']['availability']['aurora_clusters'][0]['readers']=[]
  with self.assertRaises(Failure):normalize(self.p['model'],manifest())

class ExportCoordinateTests(unittest.TestCase):
 def test_native_rounding_does_not_make_every_box_a_collision(self):
  from verify_native import points
  from routing import rect_hit
  route=points('M 1883.96 901.33 L 1971.13 901.33 L 1971.12 1081.61')
  self.assertEqual(route[1][0],route[2][0]);self.assertFalse(rect_hit(route[1],route[2],{'x':0,'y':0,'w':100,'h':100}))
 def test_actual_diagonal_is_preserved_and_rejected(self):
  from verify_native import points
  from routing import rect_hit
  route=points('M 20 30 L 25 80');self.assertTrue(rect_hit(*route,{'x':0,'y':0,'w':1,'h':1}))
 def test_exponent_coordinates_parse_correctly(self):
  from verify_native import points
  self.assertEqual(points('M 1e3 2e2 L 1.2e3 2e2'),[(1000,200),(1200,200)])
 def test_relative_svg_path_is_not_misread_as_absolute(self):
  from verify_native import points
  self.assertEqual(points('M 10 20 l 100 0'),[])

class CorpusAcceptanceTests(unittest.TestCase):
 def test_missing_runtime_is_not_an_expected_layout_rejection(self):
  from corpus import outcome_matches
  c=fixtures()['fan-8'];g={'status':'needs-review-or-split','errors':[{'code':'E_RUNTIME_UNAVAILABLE'}]};self.assertFalse(outcome_matches(c,g,3))
 def test_only_declared_rejection_is_accepted(self):
  from corpus import outcome_matches
  c=fixtures()['fan-8'];g={'status':'needs-review-or-split','errors':[{'code':'E_EDGE_TERMINAL'}]};self.assertTrue(outcome_matches(c,g,2))

class FrontendRegressionTests(unittest.TestCase):
 def test_normal_spa_origin_is_straight(self):
  p=json.loads((ROOT/'examples/projects/modern-web-iot.json').read_text());_,vs=project_views(p);lay,w=layout(vs['frontend']['architecture'],manifest());edge=next(e for e in lay['edges'] if e['id']=='origint');self.assertEqual(len(edge['points']),2);self.assertFalse(w)
 def test_replication_is_explicitly_omitted_and_covered_elsewhere(self):
  p=json.loads((ROOT/'examples/projects/modern-web-iot.json').read_text());_,vs=project_views(p);self.assertIn('replicaspa',vs['frontend']['omitted_internal_edges']);self.assertIn('replicaspa',[e['id'] for e in vs['replication']['architecture']['edges']])
 def test_malformed_required_edge_is_structured_failure(self):
  a={'schema_version':'1.0','nodes':[{'id':'a','asset_id':'aws4.lambda'},{'id':'b','asset_id':'aws4.lambda'}],'edges':[{'id':'e','source':'a','target':'b'}],'semantics':{'flows':[{'id':'f','kind':'custom','phase':'normal','path':['a','b']}],'required_edges':[{'id':[],'source':'a','target':'b','purpose':'traffic','direction':'forward'}]}}
  with self.assertRaises(Failure) as c:normalize(a,manifest())
  self.assertEqual(c.exception.issue['code'],'E_FLOW_SCHEMA')
