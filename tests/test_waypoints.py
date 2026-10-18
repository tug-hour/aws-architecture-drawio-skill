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

    def test_example_reuses_port_allocation_and_obstacle_validation(self):
        m=manifest();raw=load(ROOT/'examples/real-world/multi-az-waypoints.json');spec=read_spec(ROOT/'examples/real-world/multi-az-waypoints.spec.py')
        before=copy.deepcopy(raw);a,lay,_=build(raw,spec,m);self.assertEqual(raw,before)
        self.assertTrue(all(e.get('waypoints') for e in a['edges']))
        self.assertEqual(len(lay['edges']),len(raw['edges']))
        self.assertEqual(lay['routing_quality']['crossings'],3)
        bad=copy.deepcopy(spec);bad['LANES']['state-a']=[600]
        with self.assertRaises(Failure):build(raw,bad,m)
        for change in ({'POS':{}},{'LANES':{'missing':[0]}},{'W':float('inf')},{'AUTO':['poll-a'],'LANES':{'poll-a':[700]}}):
            with self.subTest(change=change),self.assertRaises(Failure):build(raw,dict(spec,**change),m)
