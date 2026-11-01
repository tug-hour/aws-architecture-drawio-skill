import copy,json,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from build_drawio import normalize,author
from catalog import manifest
from schema import Failure
from topology import validate_availability
from routing import check_terminals,readability

class AvailabilityTests(unittest.TestCase):
 def setUp(self):self.a=json.loads((ROOT/'examples/real-world/multi-region-dr.json').read_text());self.m=manifest()
 def error(self,code):
  with self.assertRaises(Failure) as ctx:normalize(self.a,self.m)
  self.assertEqual(ctx.exception.issue['code'],code)
 def test_web_writer_and_reader_are_in_different_az_subnets(self):
  a=normalize(json.loads((ROOT/'examples/real-world/web-three-tier.json').read_text()),self.m);groups={g['id']:g for g in a['groups']};db=[n for n in a['nodes'] if n['asset_id']=='aws4.aurora'];self.assertEqual(len(db),2);self.assertEqual(len({groups[n['group_id']]['parent_id'] for n in db}),2);self.assertTrue(all(groups[n['group_id']]['type']=='group.private-subnet' for n in db))
 def test_complete_warm_standby_contract(self):
  a=normalize(self.a,self.m);self.assertEqual(validate_availability(a)['regions'],2)
 def test_writer_reader_same_az_rejected(self):
  next(n for n in self.a['nodes'] if n['id']=='tdbb')['group_id']='tdsuba' if False else 'tdbsuba';self.error('E_DB_MULTI_AZ')
 def test_declared_writer_caption_matches_role(self):
  next(n for n in self.a['nodes'] if n['id']=='tdba')['description']='Reader';self.error('E_DB_ROLE_LABEL')
 def test_reverse_aurora_replication_rejected(self):
  e=next(e for e in self.a['edges'] if e['id']=='replicadb');e['source'],e['target']=e['target'],e['source'];self.error('E_REPLICATION_DIRECTION')
 def test_missing_standby_app_path_rejected(self):
  self.a['edges']=[e for e in self.a['edges'] if e['id']!='obalanceb'];self.error('E_APP_ENTRY')
 def test_primary_requires_writer(self):
  self.a['availability']['aurora_clusters'][0]['writer']=None;self.error('E_DB_ROLE')
 def test_standby_writer_before_promotion_rejected(self):
  self.a['availability']['aurora_clusters'][1]['writer']='odba';self.error('E_DB_ROLE')
 def test_missing_cross_region_replication_rejected(self):
  self.a['edges']=[e for e in self.a['edges'] if e['id']!='replicadb'];self.error('E_REPLICATION')
 def test_missing_failover_entry_rejected(self):
  self.a['edges']=[e for e in self.a['edges'] if e['id']!='apio'];self.error('E_REGION_ENTRY')
 def test_standby_sql_is_conditional(self):
  next(e for e in self.a['edges'] if e['id']=='osqla')['purpose']='traffic';self.error('E_STANDBY_WRITE_PATH')
 def test_regional_service_parity_required(self):
  r=self.a['availability']['regions'][1];r['regional_nodes'].remove('oqueue');self.error('E_REGION_SERVICE_PARITY')
 def test_source_target_terminal_clearance(self):
  with self.assertRaises(Failure) as ctx:check_terminals({'id':'e'},[[0,0],[8,0],[8,30],[50,30]],'right','left')
  self.assertEqual(ctx.exception.issue['code'],'E_EDGE_TERMINAL')
  check_terminals({'id':'e'},[[0,0],[24,0],[24,30],[60,30]],'right','left')
 def test_detour_and_close_ports_are_reported(self):
  q,w=readability([{'id':'a','points':[[0,0],[0,200],[40,200],[40,0]]},{'id':'b','points':[[42,0],[100,0]]}]);self.assertEqual({i['code'] for i in w},{'W_EDGE_DETOUR','W_PORT_PROXIMITY'});self.assertEqual(q['terminal_minimum_pt'],24)
 def test_unknown_semantic_purpose_rejected(self):
  self.a['edges'][0]['purpose']='unknown';self.error('E_EDGE_PURPOSE')
 def test_association_has_no_arrow(self):
  next(e for e in self.a['edges'] if e['id']=='wafpolicy')['direction']='forward';self.error('E_EDGE_PURPOSE')
 def test_invalid_availability_type_is_structured(self):
  self.a['availability']=[];self.error('E_SCHEMA')

class DirectedContractTests(unittest.TestCase):
 def setUp(self):
  self.a=json.loads((ROOT/'examples/real-world/multi-region-dr.json').read_text());self.m=manifest()
 def edge(self,ident):return next(e for e in self.a['edges'] if e['id']==ident)
 def reverse_both(self,ident):
  e=self.edge(ident);e['source'],e['target'],e['direction']=e['target'],e['source'],'both'
 def accepted(self):
  before=copy.deepcopy(self.a)
  self.assertEqual(validate_availability(normalize(self.a,self.m))['status'],'passed')
  self.assertEqual(self.a,before)
 def rejected(self,code):
  with self.assertRaises(Failure) as ctx:normalize(self.a,self.m)
  self.assertEqual(ctx.exception.issue['code'],code)
 def test_arrowless_alb_connection_does_not_prove_two_az_reachability(self):
  baseline=copy.deepcopy(self.a)
  for ident in ('tbalancea','obalanceb'):
   with self.subTest(edge=ident):
    self.a=copy.deepcopy(baseline);self.edge(ident)['direction']='none';self.rejected('E_APP_ENTRY')
 def test_reverse_both_alb_connection_remains_a_valid_path(self):
  for ident in ('tbalancea','tbalanceb','obalancea','obalanceb'):self.reverse_both(ident)
  self.accepted()
 def test_reverse_both_region_entries_remain_valid(self):
  for ident in ('apit','apio'):self.reverse_both(ident)
  self.accepted()
 def test_arrowless_entry_rejected_even_without_cloudfront(self):
  frontend=next(n for n in self.a['nodes'] if n['id']=='cf');frontend.update(asset_id='aws4.lambda',label='AWS Lambda')
  baseline=copy.deepcopy(self.a)
  for ident in ('apit','apio'):
   with self.subTest(edge=ident):
    self.a=copy.deepcopy(baseline);self.edge(ident)['direction']='none';self.rejected('E_REGION_ENTRY')
 def test_reverse_both_db_client_paths_remain_valid(self):
  for ident in ('tsqla','tsqlb','osqla','osqlb','treader','oreader'):self.reverse_both(ident)
  self.accepted()
 def test_reverse_forward_db_client_path_is_not_incoming(self):
  e=self.edge('treader');e['source'],e['target']=e['target'],e['source'];self.rejected('E_DB_CLIENT_PATH')
 def test_reverse_both_frontend_fetch_preserves_client_identity(self):
  self.reverse_both('static');self.accepted()
 def test_arrowless_frontend_fetch_does_not_establish_client_identity(self):
  self.edge('static')['direction']='none';self.rejected('E_FRONTEND_API_PATH')
 def test_reverse_both_standby_traffic_still_rejected(self):
  # The valid failover connection remains, so an additional normal path cannot hide behind it.
  self.a['edges'].append({'id':'wrong-normal-db','source':'odba','target':'oapia','direction':'both','purpose':'traffic','label':'通常SQL'})
  self.rejected('E_STANDBY_WRITE_PATH')
 def test_queue_producer_direction_still_requires_an_incoming_arc(self):
  self.edge('tjob')['direction']='forward';self.rejected('E_QUEUE_PRODUCER_PATH')
 def test_reverse_both_queue_connection_remains_valid(self):
  for ident in ('tjob','ojob'):self.reverse_both(ident)
  self.accepted()
 def test_dns_api_connection_is_forbidden_regardless_of_endpoint_order(self):
  baseline=copy.deepcopy(self.a)
  for direction in ('forward','both','none'):
   for source,target in (('dns','talb'),('talb','dns')):
    with self.subTest(direction=direction,source=source):
     self.a=copy.deepcopy(baseline)
     self.a['edges'].append({'id':'wrong-dns','source':source,'target':target,'direction':direction,'purpose':'traffic','label':'API'})
     self.rejected('E_DNS_DATA_PATH')
 def test_contract_is_opt_in_and_required_edges_remain_exact(self):
  self.a.pop('availability');self.edge('tbalancea')['direction']='none'
  normalize(self.a,self.m)
  p=json.loads((ROOT/'examples/projects/modern-web-iot.json').read_text())
  req=p['model']['semantics']['required_edges'][0]
  edge=next(e for e in p['model']['edges'] if e['id']==req['id'])
  edge['source'],edge['target'],edge['direction']=edge['target'],edge['source'],'both'
  with self.assertRaises(Failure) as ctx:normalize(p['model'],self.m)
  self.assertEqual(ctx.exception.issue['code'],'E_REQUIRED_CONNECTION')

if __name__=='__main__':unittest.main()
