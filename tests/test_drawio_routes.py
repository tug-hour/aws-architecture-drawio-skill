"""Optional direct drawing diagnostics never rewrite or gate a diagram."""
import copy
import sys
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))


def drawing():
    root=ET.Element('mxGraphModel',pageWidth='800',pageHeight='500')
    cells=ET.SubElement(root,'root')
    ET.SubElement(cells,'mxCell',id='0')
    ET.SubElement(cells,'mxCell',id='1',parent='0')
    def vertex(ident,x,y,w,h,parent='1',style='shape=mxgraph.aws4.lambda;',value=''):
        c=ET.SubElement(cells,'mxCell',id=ident,parent=parent,vertex='1',style=style,value=value)
        ET.SubElement(c,'mxGeometry',x=str(x),y=str(y),width=str(w),height=str(h),attrib={'as':'geometry'})
    vertex('group',100,100,600,300,style='container=1;')
    vertex('a',20,40,80,80,'group')
    vertex('b',400,40,80,80,'group')
    c=ET.SubElement(cells,'mxCell',id='ab',parent='group',edge='1',source='a',target='b',
                    style='exitX=1;exitY=0.5;entryX=0;entryY=0.5;exitPerimeter=0;entryPerimeter=0;endArrow=open;')
    ET.SubElement(c,'mxGeometry',relative='1',attrib={'as':'geometry'})
    return root,vertex


class DirectRouteTests(unittest.TestCase):
    def review(self,root):
        from drawio_routes import inspect_xml
        return inspect_xml(ET.tostring(root,encoding='unicode'))['pages'][0]

    def test_nested_coordinates_full_text_obstacle_and_read_only(self):
        root,vertex=drawing();before=ET.tostring(root)
        result=self.review(root)
        self.assertEqual(ET.tostring(root),before)
        self.assertEqual(result['analyzed_edges'],['ab'])
        self.assertEqual(result['quality']['total_length_pt'],225)
        self.assertFalse(result['issues'])
        vertex('role',200,40,100,100,'group',style='text;html=0;',value='Name\nRole\nMore')
        result=self.review(root)
        self.assertEqual(result['issues'][0]['code'],'E_EDGE_OBSTACLE')
        self.assertEqual(result['issues'][0]['details']['obstacle'],'role')

    def test_computed_routes_and_relative_text_are_not_reported_as_checked(self):
        root,vertex=drawing()
        c=root.find(".//mxCell[@id='ab']");c.set('style',c.get('style')+'edgeStyle=orthogonalEdgeStyle;')
        result=self.review(root)
        self.assertEqual(result['analyzed_edges'],[])
        self.assertTrue(result['unresolved'])
        c.set('style',c.get('style').replace('edgeStyle=orthogonalEdgeStyle;',''))
        vertex('edge-label',0,0,100,30,'ab',style='text;',value='label')
        self.assertTrue(self.review(root)['unresolved'])

    def test_shared_segment_reuses_existing_diagnostic(self):
        root,_=drawing();cells=root.find('root')
        edge=copy.deepcopy(root.find(".//mxCell[@id='ab']"));edge.set('id','other');cells.append(edge)
        result=self.review(root)
        self.assertIn('E_EDGE_OVERLAP',[issue['code'] for issue in result['issues']])

    def test_comparison_reports_topology_change_instead_of_recommending_missing_edges(self):
        from drawio_routes import compare
        root,_=drawing();other=copy.deepcopy(root)
        other.find('root').remove(other.find(".//mxCell[@id='ab']"))
        report=compare([ET.tostring(r,encoding='unicode') for r in (root,other)])
        self.assertFalse(report['same_topology'])
        self.assertTrue(report['visual_review_required'])

    def test_reordering_icons_reduces_crossings_without_changing_topology(self):
        from drawio_routes import compare
        root,vertex=drawing();cells=root.find('root')
        vertex('c',20,200,80,80,'group');vertex('d',400,200,80,80,'group')
        b=root.find(".//mxCell[@id='b']/mxGeometry");d=root.find(".//mxCell[@id='d']/mxGeometry")
        b.set('y','220');d.set('y','20')
        ab=root.find(".//mxCell[@id='ab']")
        cd=copy.deepcopy(ab);cd.set('id','cd');cd.set('source','c');cd.set('target','d');cells.append(cd)
        for e,x,ys in ((ab,300,(80,260)),(cd,200,(240,60))):
            arr=ET.SubElement(e.find('mxGeometry'),'Array',attrib={'as':'points'})
            for y in ys:ET.SubElement(arr,'mxPoint',x=str(x),y=str(y))
        old=ET.tostring(root,encoding='unicode')
        b.set('y','40');d.set('y','200')
        for e in (ab,cd):
            g=e.find('mxGeometry');g.remove(g.find('Array'))
        result=compare([old,ET.tostring(root,encoding='unicode')])
        self.assertTrue(result['same_topology']);self.assertTrue(result['same_route_coverage'])
        before,after=[r['pages'][0]['quality'] for r in result['results']]
        self.assertGreater(before['crossings'],after['crossings'])
        self.assertGreater(before['bends'],after['bends'])
        self.assertGreater(before['total_length_pt'],after['total_length_pt'])

    def test_compressed_pages_and_backward_segments_keep_geometry(self):
        import base64,zlib
        from urllib.parse import quote
        from drawio_routes import inspect_xml
        root,_=drawing();xml=ET.tostring(root,encoding='unicode')
        compressor=zlib.compressobj(wbits=-15)
        data=base64.b64encode(compressor.compress(quote(xml).encode())+compressor.flush()).decode()
        result=inspect_xml('<mxfile><diagram id="page">'+data+'</diagram></mxfile>')['pages'][0]
        self.assertEqual(result['quality'],self.review(root)['quality'])
        g=root.find(".//mxCell[@id='ab']/mxGeometry")
        arr=ET.SubElement(g,'Array',attrib={'as':'points'})
        for x in (200,0,200):ET.SubElement(arr,'mxPoint',x=str(x),y='80')
        self.assertIn('E_EDGE_REENTRY',[i['code'] for i in self.review(root)['issues']])

    def test_generated_group_wrappers_are_not_visible_frames(self):
        from build_drawio import normalize,author
        from layout import layout
        from catalog import manifest
        from drawio_routes import inspect_xml
        m=manifest()
        a=normalize({'schema_version':'1.0','nodes':[{'id':k,'asset_id':'aws4.lambda'} for k in ('a','b')],
                     'edges':[{'id':'ab','source':'a','target':'b'}]},m)
        lay,_=layout(a,m);report=inspect_xml(author(a,lay,m,'light'))['pages'][0]
        self.assertFalse(report['issues']);self.assertFalse(report['unresolved'])
        self.assertEqual(report['quality'],lay['routing_quality'])

    def test_unbounded_canvas_and_unclassified_frame_do_not_add_false_gates(self):
        root,vertex=drawing()
        root.find(".//mxCell[@id='group']/mxGeometry").set('x','-500')
        self.assertFalse(self.review(root)['issues'])
        vertex('overlay',-300,100,100,200,style='container=1;')
        report=self.review(root)
        self.assertFalse(report['issues'])
        self.assertIn('overlay',[item['element_id'] for item in report['unresolved']])
