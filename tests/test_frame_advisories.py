import contextlib
import copy
import io
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from layout import frame_overlap_warnings,layout
from build_drawio import normalize,author
from catalog import manifest
from quality import operational_quality
from project import render_project
from review_status import view_presentation


class FrameAdvisoryTests(unittest.TestCase):
    def frame(self,ident,**values):
        return dict({'id':ident,'role':'containment','x':0,'y':0,'w':100,'h':100},**values)

    def inspect(self,frames):
        a={'groups':frames};original=copy.deepcopy(a)
        warnings=frame_overlap_warnings(a,frames)
        self.assertEqual(a,original)
        return warnings

    def test_partial_overlap_is_reported_once_with_final_rectangle(self):
        frames=[self.frame('b',x=90,y=80),self.frame('a')]
        warnings=self.inspect(frames)
        self.assertEqual(len(warnings),1)
        self.assertEqual(warnings[0]['code'],'W_FRAME_OVERLAP')
        self.assertEqual(warnings[0]['element_ids'],['a','b'])
        self.assertEqual(warnings[0]['details']['overlap_rect_pt'],{'x':90,'y':80,'w':10,'h':20})
        self.assertEqual(warnings,self.inspect(list(reversed(frames))))

    def test_touching_and_disjoint_frames_are_excluded(self):
        for x,y in ((100,0),(0,100),(100,100),(101,0),(0,101)):
            with self.subTest(x=x,y=y):
                self.assertEqual(self.inspect([self.frame('a'),self.frame('b',x=x,y=y)]),[])

    def test_all_ancestors_and_overlay_are_excluded_but_siblings_are_not(self):
        frames=[self.frame('outer'),self.frame('middle',parent_id='outer'),
                self.frame('child',parent_id='middle'),self.frame('sibling',parent_id='middle'),
                self.frame('overlay',role='overlay')]
        self.assertEqual([w['element_ids'] for w in self.inspect(frames)],[['child','sibling']])

    def test_unrelated_nested_and_identical_rectangles_are_reported(self):
        for inner in ({'x':10,'y':10,'w':20,'h':20},{}):
            with self.subTest(inner=inner):
                self.assertEqual(len(self.inspect([self.frame('a'),self.frame('b',**inner)])),1)

    def test_warning_does_not_change_input_layout_models_or_project_exit(self):
        m=manifest()
        a=normalize({'schema_version':'1.0','mode':'draft',
                     'nodes':[{'id':i,'asset_id':'aws4.lambda','group_id':'g'+i} for i in ('a','b')],
                     'groups':[{'id':'g'+i,'type':'group.private-subnet','role':'containment','label':i} for i in ('a','b')],
                     'edges':[], 'glossary':[{'asset_id':'aws4.lambda','kind':'note','short_name':'note','full_name':'test'}],
                     'layout':{'mode':'manual','positions':[{'node_id':'a','x_pt':100,'y_pt':100},
                                                          {'node_id':'b','x_pt':240,'y_pt':100}]}},m)
        original=copy.deepcopy(a)
        with patch('layout.frame_overlap_warnings',return_value=[]):
            baseline,previous=layout(a,m)
        observed,warnings=layout(a,m)
        self.assertEqual(a,original)
        self.assertEqual(observed,baseline)
        added=frame_overlap_warnings(a,observed['groups'])
        self.assertEqual(len(added),1)
        self.assertEqual(warnings,previous+added)
        for theme in ('light','dark'):
            self.assertEqual(author(a,baseline,m,theme),author(a,observed,m,theme))
        display={'width_px':1920,'height_px':1080,'min_text_px':12}
        results=[{'status':'passed','production_eligible':False,'warnings':ws} for ws in (previous,warnings)]
        gates=[operational_quality(r,observed,display) for r in results]
        self.assertEqual(gates[0],gates[1])
        shown=view_presentation(dict(results[1],exit_code=0,operational_quality=gates[1]))
        self.assertEqual(shown['state'],'passed')
        self.assertIn('W_FRAME_OVERLAP',[i['code'] for i in shown['issues']])
        view={'architecture':a,'title':'test','display':display,'flow_ids':[],
              'omitted_boundary_edges':[],'omitted_internal_edges':[]}
        for result in results:
            with tempfile.TemporaryDirectory() as directory:
                base=Path(directory);source=base/'input.json';source.write_text('{}')
                with patch('project.project_views',return_value=({},{'one':view})), \
                     patch('project.validate_semantics',return_value={}),patch('project.run',return_value=(result,0)), \
                     patch('project.load',return_value=observed),contextlib.redirect_stdout(io.StringIO()):
                    report,code=render_project(source,base/'out',base/'binary',base/'profile',base/'runtime')
                self.assertEqual((report['status'],code),('passed',0))


if __name__=='__main__':
    unittest.main()
