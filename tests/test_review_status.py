import contextlib
import copy
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
from review_status import view_presentation, project_presentation
from make_viewer import make
from project import render_project
from version import get_version


def fixture_report():
    base = {'title':'通常ビュー','status':'passed','exit_code':0,'errors':[], 'warnings':[],
            'flow_ids':['flow'], 'display':{'width_px':1200,'height_px':800,'min_text_px':12},
            'omitted_boundary_edges':[], 'omitted_internal_edges':[],
            'operational_quality':{'status':'passed','blocking_warnings':[], 'display_quality':{'status':'passed'}}}
    review = copy.deepcopy(base)
    review.update(title='枠通過の確認', warnings=[{'code':'W_EDGE_FRAME_TRANSIT','element_ids':['edge.a','frame.b'],
                                               'message':'所属と経路を確認してください'}])
    review['operational_quality'].update(status='needs-review-or-split',blocking_warnings=['W_EDGE_FRAME_TRANSIT'])
    failed = copy.deepcopy(base)
    failed.update(title='生成できなかった図',status='failed',exit_code=3,
                  errors=[{'code':'E_RUNTIME_REQUIRED','message':'実行環境を確認してください'}])
    failed.pop('operational_quality')
    return {'version':get_version(),'status':'failed','views':{'ok':base,'review':review,'failed':failed}}


class ReviewStatusTests(unittest.TestCase):
    def test_states_and_input_unchanged(self):
        report=fixture_report(); original=copy.deepcopy(report)
        result=project_presentation(report)
        self.assertEqual(result['state'],'failed')
        self.assertEqual([v['state'] for v in result['views'].values()],['passed','review','failed'])
        self.assertEqual(report,original)

    def test_review_is_distinct_from_failed_project_status(self):
        report=fixture_report(); del report['views']['failed']
        self.assertEqual(report['status'],'failed')
        self.assertEqual(project_presentation(report)['state'],'review')
        report['errors']=[{'code':'E_PROJECT_CHANGED'}]
        self.assertEqual(project_presentation(report)['state'],'failed')

    def test_nonblocking_warnings_do_not_change_state_or_duplicate(self):
        record=fixture_report()['views']['ok']
        record['warnings']=[{'code':'W_AZ_LABEL_REDUNDANT','element_ids':['node']}]
        self.assertEqual(view_presentation(record)['state'],'passed')
        record=fixture_report()['views']['review']
        self.assertEqual(len(view_presentation(record)['issues']),1)

    def test_display_failure_and_missing_warning_details(self):
        record=fixture_report()['views']['review']; record['warnings']=[]
        record['operational_quality']['display_quality']['status']='needs-split'
        result=view_presentation(record)
        self.assertEqual([i['code'] for i in result['issues']],['W_EDGE_FRAME_TRANSIT','needs-split'])

    def test_missing_evidence_is_not_passed(self):
        self.assertEqual(view_presentation({'status':'passed','exit_code':0})['state'],'unknown')
        self.assertEqual(project_presentation({'status':'failed','errors':[]})['state'],'unknown')

    def test_project_result_and_exit_codes_remain_unchanged(self):
        view={'title':'test','architecture':{},'display':{'width_px':1200,'height_px':800,'min_text_px':12},
              'flow_ids':[],'omitted_boundary_edges':[],'omitted_internal_edges':[]}
        for run_code, warnings, expected in ((0,[],0),(0,[{'code':'W_EDGE_CONTACT'}],2),(3,[],2)):
            with self.subTest(run_code=run_code,warnings=warnings), tempfile.TemporaryDirectory() as directory:
                base=Path(directory); source=base/'input.json'; source.write_text('{}')
                result={'status':'passed' if run_code==0 else 'failed','warnings':warnings,'errors':[]}
                with patch('project.project_views',return_value=({}, {'one':view})), patch('project.validate_semantics',return_value={}), \
                     patch('project.run',return_value=(result,run_code)), patch('project.load',return_value={'canvas':{'width_pt':500,'height_pt':300}}), \
                     contextlib.redirect_stdout(io.StringIO()):
                    report,code=render_project(source,base/'out',base/'binary',base/'profile',base/'runtime')
                self.assertEqual(code,expected)
                self.assertEqual(report['status'],'passed' if expected==0 else 'failed')

    def test_viewer_handles_missing_failed_artifacts_and_escapes_content(self):
        with tempfile.TemporaryDirectory() as directory:
            base=Path(directory); report=fixture_report()
            report['views']['review']['warnings'][0]['message']='</script><script>window.injected=true</script>'
            source=base/'project-report.json'; source.write_text(json.dumps(report))
            original=source.read_bytes(); make(base)
            body=(base/'image-review.html').read_text()
            self.assertNotIn('</script><script>',body)
            self.assertIn('W_EDGE_FRAME_TRANSIT',body)
            self.assertEqual(source.read_bytes(),original)
            with self.assertRaises(ValueError):make(base)


if __name__=='__main__':
    unittest.main()
