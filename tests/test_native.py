"""Native XML invariants and opt-in real draw.io exports."""
import copy,json,math,os,sys,tempfile,unittest
import xml.etree.ElementTree as E
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from catalog import manifest
from build_drawio import normalize,author,build
from schema import Failure,load
from layout import layout
from verify_native import verify,points
from test_runner import artifact_directory
from run import run

def arrow_fixture():
    a={'schema_version':'1.0','theme':'both','nodes':[],'edges':[],
       'layout':{'mode':'manual','positions':[]},'canvas':{'mode':'fixed','width_pt':580,'height_pt':820}}
    for i,direction in enumerate(('forward','both','none')):
        y=60+250*i
        for name,x,ny in [('source',80,y),('target',380,y+100)]:
            ident=direction+'-'+name
            a['nodes'].append({'id':ident,'asset_id':'aws4.lambda','label':'AWS Lambda','description':direction+' / '+name})
            a['layout']['positions'].append({'node_id':ident,'x_pt':x,'y_pt':ny})
        a['edges'].append({'id':direction,'source':direction+'-source','target':direction+'-target',
                           'direction':direction,'source_side':'right','target_side':'top',
                           'waypoints':[{'x_pt':410,'y_pt':y+30}]})
    return a

class NativeTests(unittest.TestCase):
    def setUp(self):self.m=manifest();self.a=json.loads((ROOT/'examples/japanese-auto.json').read_text())
    def render(self,a=None,theme='light'):
        a=normalize(a or self.a,self.m);lay,_=layout(a,self.m);return a,lay,E.fromstring(author(a,lay,self.m,theme))
    def test_aliases_resolve_to_available_native_stencils(self):
        for target in self.m['aliases'].values():self.assertIn(target,self.m['assets'])
        a=normalize(self.a,self.m);self.assertEqual(a['nodes'][0]['asset_id'],'aws4.lambda')
    def test_no_embedded_images_or_external_icons(self):
        _,_,root=self.render();text=E.tostring(root,encoding='unicode')
        self.assertNotIn('data:image',text);self.assertNotIn('shape=image',text);self.assertNotIn('http',text)
        self.assertTrue(any('shape=mxgraph.aws4.' in c.get('style','') for c in root.iter('mxCell')))
    def test_both_themes_have_same_geometry(self):
        _,_,light=self.render();_,_,dark=self.render(theme='dark')
        self.assertEqual([e.attrib for e in light.iter('mxGeometry')],[e.attrib for e in dark.iter('mxGeometry')])
    def test_verified_resource_style_and_connections(self):
        cases=[('dynamodb-streams','stream','dynamodb_stream','#C925D1',[('changes','target'),('consume','source')]),
               ('s3-bucket','bucket','bucket','#7AA116',[('origin','target')])]
        for example,ident,shape,color,connections in cases:
            with self.subTest(example=example):
                a=json.loads((ROOT/'examples/real-world'/(example+'.json')).read_text())
                geometries=[]
                for theme in ('light','dark'):
                    normalized,lay,root=self.render(a,theme)
                    node=next(n for n in lay['nodes'] if n['id']==ident)
                    self.assertEqual((node['w'],node['h']),(36,36))
                    self.assertEqual(next(n for n in normalized['nodes'] if n['id']==ident)['label_kind'],'resource-name')
                    cells={c.get('id'):c for c in root.iter('mxCell')}
                    self.assertIn('fillColor=none;',cells['icon.base.'+ident].get('style'))
                    glyph=cells['icon.glyph.'+ident].get('style')
                    self.assertIn('shape=mxgraph.aws4.'+shape+';',glyph)
                    self.assertIn('fillColor='+color+';',glyph)
                    for edge,endpoint in connections:
                        self.assertEqual(cells['edge.'+edge].get(endpoint),'icon.base.'+ident)
                    xml=E.tostring(root,encoding='unicode')
                    self.assertNotIn('data:image',xml);self.assertNotIn('shape=image',xml);self.assertNotIn('http',xml)
                    geometries.append([e.attrib for e in root.iter('mxGeometry')])
                self.assertEqual(*geometries)
    def test_cloudsearch_exception_uses_exact_pt_to_px(self):
        self.a['nodes'][0]['asset_id']='service.amazon-cloudsearch';self.a['nodes'][0]['label']='Amazon CloudSearch';_,_,r=self.render();cell=next(c for c in r.iter('mxCell') if c.get('id')=='icon.base.fn')
        self.assertAlmostEqual(float(cell.find('mxGeometry').get('width')),59.76*4/3)
    def test_nested_cells_have_real_parents(self):
        a=json.loads((ROOT/'examples/japanese-nested.json').read_text());_,_,r=self.render(a);cells={c.get('id'):c for c in r.iter('mxCell')}
        self.assertEqual(cells['frame.subnet'].get('parent'),'frame.vpc');self.assertEqual(cells['node.fn'].get('parent'),'frame.subnet')
        self.assertIn('container=1',cells['frame.vpc'].get('style'))
    def test_group_rules_preserve_pptx_units(self):
        a=json.loads((ROOT/'examples/japanese-nested.json').read_text());a['groups'][0]['type']='group.region';_,_,r=self.render(a);cells={c.get('id'):c for c in r.iter('mxCell')}
        self.assertAlmostEqual(float(cells['header.icon.vpc'].find('mxGeometry').get('width')),30*4/3)
        self.assertIn('dashPattern=3 1;',cells['frame.vpc'].get('style'));self.assertIn('fillColor=none;',cells['frame.vpc'].get('style'))
        self.assertIn('fontSize=16.0;',cells['header.label.vpc'].get('style'))
    def test_cloud_logo_choice_and_source_color(self):
        a=json.loads((ROOT/'examples/japanese-nested.json').read_text());a['groups'][0]['type']='group.aws-cloud';a['groups'][0]['cloud_icon']='cloud';_,_,r=self.render(a)
        c=next(c for c in r.iter('mxCell') if c.get('id')=='header.icon.vpc');self.assertIn('shape=mxgraph.aws4.group_aws_cloud;',c.get('style'));self.assertIn('fillColor=#242F3E;',c.get('style'))
    def test_open_6_changes_only_markers_in_both_themes(self):
        a=normalize(arrow_fixture(),self.m);lay,_=layout(a,self.m)
        legacy=copy.deepcopy(self.m);legacy['arrow'].update(native_type='openThin',size_px=8)
        self.assertEqual(lay,layout(a,legacy)[0])
        for theme in ('light','dark'):
            current=E.fromstring(author(a,lay,self.m,theme));old=E.fromstring(author(a,lay,legacy,theme))
            for tree in (current,old):
                for cell in tree.iter('mxCell'):
                    if cell.get('edge')!='1':continue
                    styles=dict(item.split('=',1) for item in cell.get('style').split(';') if '=' in item)
                    direction=cell.get('id')[5:]
                    if tree is current:
                        self.assertEqual(styles['startArrow'],'open' if direction=='both' else 'none')
                        self.assertEqual(styles['endArrow'],'none' if direction=='none' else 'open')
                        self.assertEqual((styles['startSize'],styles['endSize']),('6','6'))
                    for key in ('startArrow','endArrow','startSize','endSize'):styles.pop(key)
                    cell.set('style',';'.join(k+'='+v for k,v in styles.items()))
            self.assertEqual(E.tostring(current),E.tostring(old))
    def test_unknown_icon_is_not_substituted(self):
        self.a['nodes'][0]['asset_id']='aws4.this_does_not_exist'
        with self.assertRaises(Failure):normalize(self.a,self.m)
    def test_cycle_is_rejected_without_layout_mutation(self):
        self.a['edges'].append({'id':'back','source':'store','target':'fn'});a=normalize(self.a,self.m);before=copy.deepcopy(a)
        with self.assertRaises(Failure):layout(a,self.m)
        self.assertEqual(a,before)
    def test_invalid_cloud_icon_is_rejected(self):
        a=json.loads((ROOT/'examples/japanese-nested.json').read_text());a['groups'][0]['cloud_icon']='cloud'
        with self.assertRaises(Failure):normalize(a,self.m)
    def test_service_line_limit_is_retained(self):
        self.a['nodes'][0]['label']='AWS Lambda\n注文\n処理'
        with self.assertRaises(Failure):normalize(self.a,self.m)
    def test_existing_outputs_are_preserved(self):
        with tempfile.TemporaryDirectory() as d:
            base=Path(d);dest=base/'existing';dest.mkdir();(dest/'sentinel').write_text('user work')
            result,code=build(base/'missing',dest,base/'missing-drawio',base/'profile')
            self.assertEqual(result['errors'][0]['code'],'E_OUTPUT_EXISTS');self.assertEqual((dest/'sentinel').read_text(),'user work')
    def test_duplicate_json_key_is_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'input.json';p.write_text('{"nodes":[],"nodes":[]}')
            with self.assertRaises(Failure):load(p)

@unittest.skipUnless(os.environ.get('AWS_NATIVE_DRAWIO_RUNTIME'),'Approved native render runtime not specified')
class NativeIntegration(unittest.TestCase):
    native_render = True
    def setUp(self):
        self.runtime=Path(os.environ['AWS_NATIVE_DRAWIO_RUNTIME']);self.binary=Path(os.environ.get('AWS_DRAWIO_BINARY','/Applications/draw.io.app/Contents/MacOS/draw.io'));self.profile=Path(os.environ['AWS_DRAWIO_PROFILE'])
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.base=Path(self.tmp.name)
    def test_cross_group_export_and_rule_validation(self):
        result,code=build(ROOT/'examples/cross-group.json',self.base/'draw',self.binary,self.profile,self.runtime);self.assertEqual(code,0);self.assertFalse(result['errors'])
        result,code=verify(self.base/'draw',self.base/'qa',self.runtime,self.binary,self.profile);self.assertEqual(code,0);self.assertFalse(result['errors'])
        self.assertEqual(result['themes']['light']['images'],0);self.assertEqual(result['themes']['dark']['images'],0)

@unittest.skipUnless(os.environ.get('AWS_NATIVE_DRAWIO_RUNTIME'),'Approved native render runtime not specified')
class ArrowNativeTests(unittest.TestCase):
    native_render = True
    supports_artifacts = True
    def test_open_6_directions_and_fresh_verification_in_both_themes(self):
        with artifact_directory(self) as base:
            source=base/'input.json';source.write_text(json.dumps(arrow_fixture()))
            result,code=run(source,base/'out',
                            Path(os.environ.get('AWS_DRAWIO_BINARY','/Applications/draw.io.app/Contents/MacOS/draw.io')),
                            Path(os.environ['AWS_DRAWIO_PROFILE']),Path(os.environ['AWS_NATIVE_DRAWIO_RUNTIME']))
            self.assertEqual(code,0,result.get('errors'))
            self.assertEqual(result['aws_conformance'],'partial')
            for theme in ('light','dark'):
                evidence=result['themes'][theme];self.assertEqual(evidence['images'],0)
                self.assertTrue((base/'out/qa'/f'{theme}.browser.png').is_file())
                for edge in evidence['edges']:
                    paths=edge['paths'];direction=edge['id'][5:]
                    self.assertEqual(len(paths),{'forward':2,'both':3,'none':1}[direction])
                    for path in paths[1:]:
                        wing_a,tip,wing_b=points(path['d'])
                        middle=tuple((x+y)/2 for x,y in zip(wing_a,wing_b))
                        # Measured standard Open/6 SVG geometry at the retained 1.25pt line width.
                        self.assertAlmostEqual(math.dist(tip,middle),7.67,delta=.03)
                        self.assertAlmostEqual(math.dist(wing_a,wing_b),7.67,delta=.03)

if __name__=='__main__':unittest.main()
