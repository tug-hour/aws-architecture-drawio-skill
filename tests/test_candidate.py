"""Regression cases discovered in the review; independent observable contracts."""
import copy
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
import xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from build_drawio import normalize,author,build,export_file
from catalog import manifest
from layout import layout
from routing import rect_hit,shared_length
from schema import Failure
from verify_native import verify
from run import run

class CandidateTests(unittest.TestCase):
    def setUp(self):
        self.m=manifest();self.a=json.loads((ROOT/'examples/japanese-auto.json').read_text())
    def rejected(self,a,code):
        with self.assertRaises(Failure) as ctx:normalize(a,self.m)
        self.assertEqual(ctx.exception.issue['code'],code)
    def test_invalid_root_types_are_schema_errors(self):
        for value in ([],None,7,'input'):
            with self.subTest(value=value):self.rejected(value,'E_SCHEMA')
    def test_array_and_element_types_are_schema_errors(self):
        for key in ('nodes','edges','groups','glossary','callouts','regions','annotations'):
            for value in (None,{},'input'):
                with self.subTest(key=key,value=value):
                    a=copy.deepcopy(self.a);a[key]=value;self.rejected(a,'E_SCHEMA')
        for key in ('nodes','edges','groups','glossary'):
            a=copy.deepcopy(self.a);a[key]=[None];self.rejected(a,'E_SCHEMA')
    def test_unhashable_ids_are_schema_errors(self):
        for category,key in (('nodes','asset_id'),('nodes','group_id'),('edges','source'),('glossary','asset_id')):
            a=copy.deepcopy(self.a);a[category][0][key]=[];self.rejected(a,'E_SCHEMA' if category!='glossary' else 'E_GLOSSARY')
    def test_catalog_history_does_not_restrict_native_assets(self):
        for asset in ('aws4.a1_instance','aws4.bedrock'):
            a={'schema_version':'1.0','nodes':[{'id':'n','asset_id':asset}],'edges':[]}
            normalized=normalize(a,self.m);lay,_=layout(normalized,self.m)
            self.assertIn(self.m['assets'][asset]['shape'],author(normalized,lay,self.m,'light'))
    def test_unverified_asset_is_available_in_explicit_draft(self):
        self.a['mode']='draft';self.a['nodes'][0]['asset_id']='aws4.a1_instance';a=normalize(self.a,self.m)
        self.assertEqual(a['mode'],'draft')
    def test_general_icons_have_source_theme_styles(self):
        for asset_id in ('aws4.user','aws4.users'):
            v=self.m['assets'][asset_id];self.assertEqual(v['role'],'general');self.assertEqual(v['width_pt'],36)
            self.assertEqual(v['theme_colors'],{'light':'#242F3E','dark':'#FFFFFF'})
    def test_glossary_is_visible_in_native_model(self):
        a=normalize(self.a,self.m);lay,_=layout(a,self.m);r=ET.fromstring(author(a,lay,self.m,'light'))
        values=[c.get('value') for c in r.iter('mxCell') if c.get('id','').startswith('glossary.')]
        self.assertEqual(values,['Amazon Simple Storage Service (Amazon S3)'])
        self.assertLess(lay['glossary'][0]['y']+lay['glossary'][0]['h'],min(n['y'] for n in lay['nodes']))
    def test_duplicate_abbreviations_are_rejected(self):
        self.a['glossary'].append(dict(self.a['glossary'][0]));self.rejected(self.a,'E_GLOSSARY')
    def test_direct_edge_avoids_intermediate_icon(self):
        a={'schema_version':'1.0','nodes':[{'id':k,'asset_id':v} for k,v in zip('abc',['aws4.lambda','aws4.s3','aws4.dynamodb'])],'edges':[{'id':'ab','source':'a','target':'b'},{'id':'bc','source':'b','target':'c'},{'id':'ac','source':'a','target':'c'}]}
        a=normalize(a,self.m);lay,_=layout(a,self.m);b=next(n for n in lay['nodes'] if n['id']=='b');edge=next(e for e in lay['edges'] if e['id']=='ac')
        self.assertFalse(any(rect_hit(p,q,b) for p,q in zip(edge['points'],edge['points'][1:])))
        self.assertGreater(len(edge['points']),2)
    def test_edge_segments_do_not_overlap(self):
        a=normalize(json.loads((ROOT/'examples/japanese-branch-vertical.json').read_text()),self.m);lay,_=layout(a,self.m)
        segments=[]
        for e in lay['edges']:
            for p,q in zip(e['points'],e['points'][1:]):
                self.assertFalse(any(shared_length(p,q,u,v)>.01 for ident,u,v in segments if ident!=e['id']))
                segments.append((e['id'],p,q))
    def test_manual_cycle_uses_distinct_same_side_ports(self):
        a={'schema_version':'1.0','nodes':[{'id':'a','asset_id':'aws4.lambda'},{'id':'b','asset_id':'aws4.s3'}],'edges':[{'id':'request','source':'a','target':'b'},{'id':'response','source':'b','target':'a'}],'layout':{'mode':'manual','positions':[{'node_id':'a','x_pt':100,'y_pt':120},{'node_id':'b','x_pt':330,'y_pt':120}]}}
        a=normalize(a,self.m);lay,_=layout(a,self.m);request,response=lay['edges']
        self.assertNotEqual(request['source_port'],response['target_port']);self.assertNotEqual(request['target_port'],response['source_port'])
    def test_manual_diagonal_waypoints_are_rejected(self):
        a=json.loads((ROOT/'examples/manual-waypoints.json').read_text());a['edges'][0]['waypoints']=[{'x_pt':280,'y_pt':160}];a=normalize(a,self.m)
        with self.assertRaises(Failure) as ctx:layout(a,self.m)
        self.assertEqual(ctx.exception.issue['code'],'E_EDGE_OBSTACLE')
    def test_manual_example_and_adaptive_colors(self):
        a=normalize(json.loads((ROOT/'examples/manual-waypoints.json').read_text()),self.m)
        lay,_=layout(a,self.m)
        self.assertEqual(lay['edges'][0]['points'],[[260,210],[290,210],[290,150],[570,150],[570,210],[600,210]])
        from integrity import compare_model
        for theme in ('light','dark'):
            xml=author(a,lay,self.m,theme);root=ET.fromstring(xml)
            model=root.find('diagram/mxGraphModel')
            self.assertEqual(model.get('adaptiveColors'),'none')
            self.assertEqual(model.get('background'),'#FFFFFF' if theme=='light' else '#000000')
            compare_model(xml,xml,theme)
            del model.attrib['adaptiveColors']
            with self.assertRaises(Failure) as ctx:compare_model(ET.tostring(root,encoding='unicode'),xml,theme)
            self.assertEqual(ctx.exception.issue['code'],'E_MODEL_MISMATCH')

    def test_obstacle_failure_identifies_element_and_segment(self):
        from routing import route_edges
        a={'direction':'left-to-right','edges':[{'id':'direct','source':'a','target':'c','direction':'forward','waypoints':[{'x_pt':400,'y_pt':210}]}]}
        nodes=[{'id':k,'x':x,'y':180,'w':60,'h':60,'label_x':x,'label_w':60,'label':['Node']} for k,x in [('a',200),('c',600)]]
        for kind in ('icon','label','header'):
            with self.subTest(kind=kind):
                others=[];groups=[]
                if kind=='header':groups=[{'id':'b','x':370,'y':190,'w':60,'h':100,'role':'containment'}]
                else:others=[{'id':'b','x':370,'y':180 if kind=='icon' else 130,'w':60,'h':60,'label_x':370,'label_w':60,'label':['Node','Details']}]
                with self.assertRaises(Failure) as ctx:route_edges(a,nodes+others,groups,800,350)
                issue=ctx.exception.issue
                self.assertEqual(issue['code'],'E_EDGE_OBSTACLE')
                self.assertEqual(issue['element_ids'],['direct'])
                self.assertEqual(issue['details'],{'obstacle':kind+'.b','segment':[[260,210],[600,210]]})

    def test_waypoints_require_fixed_manual_coordinates(self):
        self.a['edges'][0]['waypoints']=[{'x_pt':1,'y_pt':2}];self.rejected(self.a,'E_WAYPOINT_MODE')
    def test_pipeline_saves_input_failure_report(self):
        with tempfile.TemporaryDirectory() as d:
            d=Path(d);p=d/'input.json';p.write_text('[]');r,code=run(p,d/'output',d/'missing',d/'profile',d/'runtime')
            self.assertEqual(code,2);self.assertEqual(r['errors'][0]['code'],'E_SCHEMA');self.assertEqual(json.loads((d/'output/result.json').read_text())['exit_code'],2)
    def test_export_never_accepts_existing_target(self):
        with tempfile.TemporaryDirectory() as d:
            d=Path(d);p=d/'stale.svg';p.write_text('stale')
            with self.assertRaises(Failure) as ctx:export_file(d/'binary',d/'profile',d/'source',p,'svg')
            self.assertEqual(ctx.exception.issue['code'],'E_EXPORT_EXISTS');self.assertEqual(p.read_text(),'stale')

class ArtifactValidationTests(unittest.TestCase):
    """Synthetic exports test early rejection only; never claim a successful render."""
    def setUp(self):
        from integrity import record
        from version import get_version
        from unittest.mock import patch
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup);base=Path(tmp.name)
        self.source=base/'source';self.source.mkdir();self.qa=base/'qa'
        self.runtime=base/'missing-runtime';self.binary=base/'missing-binary';self.profile=base/'missing-profile'
        model=json.loads((ROOT/'examples/japanese-auto.json').read_text());model['mode']='draft'
        m=manifest();model=normalize(model,m);lay,_=layout(model,m)
        files=[]
        for theme in ('light','dark'):
            for ext,data in (('drawio',author(model,lay,m,theme)),('svg','<svg><g data-cell-id="icon.glyph.fn"><path d="M 0 0 L 1 1"/></g><text>Amazon S3</text></svg>'),('png','synthetic')):
                name=theme+'.'+ext;(self.source/name).write_text(data);files.append(name)
        for name,value in [('architecture.json',model),('layout.json',lay),('measurements.json',None),
                           ('validation.json',{'candidate_version':get_version(),'environment':{},'warnings':[]})]:
            (self.source/name).write_text(json.dumps(value));files.append(name)
        (self.source/'artifact-manifest.json').write_text(json.dumps(record(self.source,files)))
        self.render_calls=[]
        for target in ('legacy_drawio.drawio_version','legacy_drawio.export_file','verify_native.invoke'):
            guard=patch(target);mock=guard.start();self.addCleanup(guard.stop);self.render_calls.append(mock)

    def check(self):
        result=verify(self.source,self.qa,self.runtime,self.binary,self.profile)
        for renderer in self.render_calls:renderer.assert_not_called()
        return result

    def test_native_model_shape_endpoints_and_parent_are_rejected_before_render(self):
        p=self.source/'light.drawio';original=p.read_text()
        for kind,expected in [('shape','E_MODEL_SHAPE'),('source','E_MODEL_ENDPOINT'),
                              ('target','E_MODEL_ENDPOINT'),('parent','E_MODEL_PARENT')]:
            with self.subTest(kind=kind):
                self.qa=self.qa.parent/('qa-'+kind)
                tree=ET.fromstring(original)
                if kind=='shape':
                    cell=next(c for c in tree.iter('mxCell') if c.get('id')=='icon.glyph.store')
                    cell.set('style',cell.get('style').replace('mxgraph.aws4.s3','mxgraph.aws4.lambda'))
                else:
                    cell=next(c for c in tree.iter('mxCell') if c.get('edge')=='1')
                    cell.set(kind,{'source':'icon.base.store','target':'icon.base.fn','parent':'0'}[kind])
                p.write_text(ET.tostring(tree,encoding='unicode'))
                r,code=self.check();self.assertEqual(code,2);self.assertEqual(r['errors'][0]['code'],expected)
    def test_svg_text_change_and_glyph_removal_are_rejected_before_render(self):
        originals={theme:(self.source/(theme+'.svg')).read_text() for theme in ('light','dark')}
        for kind in ('text','glyph'):
            with self.subTest(kind=kind):
                self.qa=self.qa.parent/('qa-'+kind)
                for theme,original in originals.items():
                    data=original
                    if kind=='text' and theme=='light':data=data.replace('Amazon S3','Wrong S3')
                    elif kind=='glyph':
                        tree=ET.fromstring(original)
                        tree.remove(next(c for c in tree if c.get('data-cell-id')=='icon.glyph.fn'))
                        data=ET.tostring(tree,encoding='unicode')
                    (self.source/(theme+'.svg')).write_text(data)
                r,code=self.check();self.assertEqual(code,2);self.assertEqual(r['errors'][0]['code'],'E_ARTIFACT_INTEGRITY')
                self.assertTrue((self.qa/'browser-validation.json').exists());self.assertFalse((self.qa/'light.browser.png').exists())

@unittest.skipUnless(os.environ.get('AWS_NATIVE_DRAWIO_RUNTIME'),'Approved runtime not specified')
class CandidateIntegration(unittest.TestCase):
    native_render = True
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory();cls.base=Path(cls.tmp.name);cls.runtime=Path(os.environ['AWS_NATIVE_DRAWIO_RUNTIME']);cls.profile=Path(os.environ['AWS_DRAWIO_PROFILE']);cls.binary=Path(os.environ.get('AWS_DRAWIO_BINARY','/Applications/draw.io.app/Contents/MacOS/draw.io'))
        r,code=build(ROOT/'examples/japanese-auto.json',cls.base/'baseline',cls.binary,cls.profile,cls.runtime)
        if code:raise RuntimeError(str(r))
    @classmethod
    def tearDownClass(cls):cls.tmp.cleanup()
    def setUp(self):
        self.source=self.base/self._testMethodName;shutil.copytree(self.base/'baseline',self.source);self.qa=self.base/(self._testMethodName+'-qa')
    def check(self):return verify(self.source,self.qa,self.runtime,self.binary,self.profile)
    def test_correct_model_and_glossary_pass_real_render(self):
        r,code=self.check();self.assertEqual(code,0,r)
        for t in ('light','dark'):
            labels={v['id']:v['text'] for v in r['themes'][t]['labels']};self.assertEqual(labels['glossary.0'],'Amazon Simple Storage Service (Amazon S3)')
    def test_stale_svg_with_updated_hash_is_rejected_by_fresh_render(self):
        p=self.source/'light.svg';p.write_text(p.read_text().replace('Amazon S3','Wrong S3'));manifest_path=self.source/'artifact-manifest.json';value=json.loads(manifest_path.read_text());from integrity import sha;value['files']['light.svg']=sha(p);manifest_path.write_text(json.dumps(value))
        r,code=self.check();self.assertEqual(code,2);self.assertEqual(r['errors'][0]['code'],'E_EXPORT_MISMATCH')
    def test_stale_png_with_updated_hash_is_rejected_by_fresh_render(self):
        p=self.source/'light.png';p.write_bytes(b'not the rendered PNG');manifest_path=self.source/'artifact-manifest.json';value=json.loads(manifest_path.read_text());from integrity import sha;value['files']['light.png']=sha(p);manifest_path.write_text(json.dumps(value))
        r,code=self.check();self.assertEqual(code,2);self.assertEqual(r['errors'][0]['code'],'E_PNG_EXPORT_MISMATCH')
    def test_draft_asset_warning_is_preserved(self):
        a=json.loads((ROOT/'examples/simple.json').read_text());a['mode']='draft';a['nodes'][0]['asset_id']='aws4.a1_instance';a['nodes'][0].pop('label_kind',None)
        p=self.base/'draft.json';p.write_text(json.dumps(a));r,code=run(p,self.base/'draft-output',self.binary,self.profile,self.runtime)
        self.assertEqual(code,0,r);self.assertFalse(r['production_eligible']);self.assertIn('W_UNVERIFIED_ASSET',[w['code'] for w in r['warnings']])

if __name__=='__main__':unittest.main()
