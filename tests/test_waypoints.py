"""Placement helpers reuse routing validation and work without a browser or draw.io."""
import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from waypoints import auto_sides,build_path,build,read_spec,generate
from catalog import manifest
from schema import Failure,load

class WaypointTests(unittest.TestCase):
    def test_relative_sides_and_orthogonal_paths(self):
        cases=[((200,0),('right','left')),((-200,0),('left','right')),((200,200),('right','top')),((-200,200),('left','top')),((200,-200),('top','left')),((-200,-200),('top','right')),((0,200),(None,None))]
        for target,sides in cases:self.assertEqual(auto_sides((0,0),target),sides)
        self.assertEqual(build_path((60,30),(400,330),'right','left',[200]),[[60,30],[200,30],[200,330],[400,330]])
        self.assertEqual(build_path((60,30),(430,300),'right','top',[]),[[60,30],[430,30],[430,300]])
        with self.assertRaises(ValueError):build_path((60,30),(430,300),'right','top',[200])

    def test_native_authoring_without_render_dependencies_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp);source=base/'input.json';spec=base/'placement.py';out=base/'out'
            source.write_text(json.dumps({'schema_version':'1.0','nodes':[{'id':'a','asset_id':'aws4.bedrock'},{'id':'b','asset_id':'aws4.lambda'}],'edges':[{'id':'call','source':'a','target':'b'}]}))
            spec.write_text("POS={'a':(100,100),'b':(500,100)}\nW=800\nH=400\n")
            with patch('waypoints.export_file',side_effect=AssertionError('Must not render')):
                report,code=generate(source,spec,out)
                self.assertEqual(code,0,report);self.assertEqual(report['status'],'authored')
                self.assertEqual(report['measurement'],'estimated')
                a=load(out/'architecture.json');self.assertTrue(a['edges'][0]['waypoints'])
                self.assertEqual(load(out/'layout.json')['measurement'],report['measurement'])
                xml=(out/'light.drawio').read_text();self.assertIn('mxgraph.aws4.bedrock',xml)
                self.assertNotIn('data:image',xml);self.assertFalse((out/'dark.drawio').exists())
                old={p.name:p.read_bytes() for p in out.iterdir()}
                report,code=generate(source,spec,out);self.assertEqual(code,2)
                self.assertEqual(report['errors'][0]['code'],'E_OUTPUT_EXISTS')
                self.assertEqual(old,{p.name:p.read_bytes() for p in out.iterdir()})
            spec.write_text("raise RuntimeError('must not execute')")
            with self.assertRaises(Failure):read_spec(spec)

    def test_shared_ports_and_obstacle_validation(self):
        m=manifest()
        raw={'schema_version':'1.0','nodes':[{'id':n,'asset_id':'aws4.lambda'} for n in ('a','b','c')],
             'edges':[{'id':e,'source':'a','target':t} for e,t in [('ab','b'),('ac','c')]]}
        spec={'POS':{'a':(100,200),'b':(500,100),'c':(500,300)},'W':800,'H':500,
              'SIDES':{'ab':('right','left'),'ac':('right','left')},'LANES':{'ab':[300],'ac':[350]}}
        before=copy.deepcopy(raw);a,lay,_=build(raw,spec,m);self.assertEqual(raw,before)
        self.assertTrue(all(e.get('waypoints') for e in a['edges']))
        self.assertEqual(len(lay['edges']),len(raw['edges']))
        from routing import allocate_ports
        ports=allocate_ports(a,lay['nodes'])
        for edge in lay['edges']:
            self.assertEqual(edge['points'][0],ports[edge['id']]['start'])
            self.assertEqual(edge['points'][-1],ports[edge['id']]['end'])
        self.assertNotEqual(ports['ab']['start'],ports['ac']['start'])
        bad=copy.deepcopy(spec);bad['POS']['c']=(300,200);bad['LANES']['ab']=[400]
        with self.assertRaises(Failure) as error:build(raw,bad,m)
        self.assertEqual(error.exception.issue['code'],'E_EDGE_OBSTACLE')
        self.assertEqual(error.exception.issue['details']['obstacle'],'icon.c')
        for change in ({'POS':{}},{'LANES':{'missing':[0]}},{'W':float('inf')},{'AUTO':['ab'],'LANES':{'ab':[300]}}):
            with self.subTest(change=change),self.assertRaises(Failure):build(raw,dict(spec,**change),m)

    def test_bottom_ports_are_supported_but_labels_still_block_them(self):
        from routing import allocate_ports,check_terminals,_route_edges
        raw={'schema_version':'1.0','nodes':[{'id':n,'asset_id':'aws4.lambda'} for n in ('a','b')],
             'edges':[{'id':'ab','source':'a','target':'b'}]}
        spec={'POS':{'a':(100,100),'b':(100,350)},'W':500,'H':600,
              'SIDES':{'ab':('bottom','top')},'LANES':{'ab':[250]}}
        from waypoints import apply_spec
        a=apply_spec(raw,spec,manifest())
        self.assertEqual(a['edges'][0]['source_side'],'bottom')
        def node(ident,y):
            return dict(id=ident,x=100,y=y,w=60,h=60,label=[],label_x=100,label_w=60)
        nodes=[node('a',100),node('b',350)]
        ports=allocate_ports(a,nodes)['ab']
        self.assertEqual(ports['source_port'],(.5,1))
        path=build_path(ports['start'],ports['end'],'bottom','top',[250])
        check_terminals(a['edges'][0],path,'bottom','top')
        a['edges'][0]['waypoints']=[{'x_pt':130,'y_pt':250}]
        self.assertEqual(_route_edges(a,nodes,[],500,600,a['edges'])[0]['points'],[[130,160],[130,350]])
        nodes[0]['label']=['Name','Role']
        with self.assertRaises(Failure) as error:_route_edges(a,nodes,[],500,600,a['edges'])
        self.assertEqual(error.exception.issue['code'],'E_EDGE_OBSTACLE')
