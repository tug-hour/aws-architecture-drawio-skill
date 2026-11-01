"""Acceptance failures and independent test groups, without a rendering runtime."""
import contextlib
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from acceptance import acceptance
from schema import Failure
from test_runner import select, run_tests, artifact_directory


class AcceptanceFailureTests(unittest.TestCase):
    def exercise(self, project_error=None, corpus_error=None, cases_only=False, snapshots=None):
        with tempfile.TemporaryDirectory() as d:
            base = Path(d); output = base / 'out'
            project = Mock(return_value=({'status': 'passed'}, 0), side_effect=project_error)
            corpus = Mock(return_value={'status': 'passed'}, side_effect=corpus_error)
            with patch('acceptance.diagnose', return_value={'status':'ready'}), patch('acceptance.snapshot', side_effect=snapshots or [{}, {}]), \
                 patch('acceptance.subprocess.run', return_value=Mock(returncode=0, stdout='', stderr='')) as tests, \
                 patch('acceptance.run', return_value=({'status':'passed'}, 0)), \
                 patch('project.render_project', project), patch('corpus.corpus', corpus), contextlib.redirect_stdout(io.StringIO()):
                report, code = acceptance(output, base/'bin', base/'profile', base/'runtime', cases_only)
            self.assertEqual(json.loads((output/'acceptance-summary.json').read_text()), report)
            self.assertEqual(report['exit_code'], code)
            self.assertNotEqual(report['status'], 'running')
            self.assertGreater(report['seconds'], 0)
            self.assertTrue(report['cases'])
            return report, code, tests, corpus

    def test_project_failure_keeps_completed_tests_and_examples(self):
        report, code, _, corpus = self.exercise(project_error=Failure('E_VIEW_SCHEMA', 'Invalid view'))
        self.assertEqual(code, 2)
        self.assertEqual(report['errors'][0]['code'], 'E_VIEW_SCHEMA')
        self.assertEqual(report['tests_exit_code'], 0)
        self.assertTrue(all(c['exit_code'] == 0 for c in report['cases'].values()))
        self.assertIn('project', report['timings'])
        corpus.assert_not_called()

    def test_corpus_failure_keeps_completed_project(self):
        report, code, _, _ = self.exercise(corpus_error=Failure('E_SCHEMA', 'Invalid corpus'))
        self.assertEqual(code, 2)
        self.assertEqual(report['project_status'], 'passed')
        self.assertEqual(report['errors'][0]['code'], 'E_SCHEMA')
        self.assertIn('corpus', report['timings'])

    def test_runtime_failure_is_saved_with_distinct_exit_code(self):
        report, code, _, _ = self.exercise(project_error=ValueError('Runtime failure'))
        self.assertEqual(code, 3)
        self.assertEqual(report['errors'][0]['code'], 'E_ACCEPTANCE_RUNTIME')

    def test_cases_only_does_not_repeat_tests_or_claim_they_passed(self):
        report, code, tests, _ = self.exercise(cases_only=True)
        self.assertEqual(code, 0)
        self.assertEqual(report['scope'], 'cases-only')
        self.assertNotIn('tests_exit_code', report)
        tests.assert_not_called()

    def test_source_change_rejects_otherwise_successful_cases(self):
        report, code, _, _ = self.exercise(snapshots=[{}, {'scripts/run.py':'changed'}])
        self.assertEqual(code, 2)
        self.assertEqual(report['errors'][0]['code'], 'E_SOURCE_CHANGED')

    def test_existing_report_is_preserved(self):
        with tempfile.TemporaryDirectory() as d:
            output=Path(d); report=output/'acceptance-summary.json';report.write_text('existing')
            _, code=acceptance(output,output/'bin',output/'profile',output/'runtime')
            self.assertEqual(code,2);self.assertEqual(report.read_text(),'existing')


class TestSelectionTests(unittest.TestCase):
    def fixture(self):
        class Unit(unittest.TestCase):
            def runTest(self): pass
        class Native(Unit):
            native_render = True
        return unittest.TestSuite([Unit(), unittest.TestSuite([Native()])])

    def test_groups_are_disjoint_and_cover_the_full_suite(self):
        unit=select(self.fixture(),'unit');native=select(self.fixture(),'native');all_tests=select(self.fixture(),'all')
        self.assertEqual(len(unit),1);self.assertEqual(len(native),1);self.assertEqual(len(all_tests),2)
        self.assertFalse(getattr(unit[0],'native_render',False));self.assertTrue(native[0].native_render)
        self.assertEqual(len(select(self.fixture(),'all','Native')),1)

    def test_unit_group_does_not_invoke_native_even_with_runtime_environment(self):
        with tempfile.TemporaryDirectory() as d, patch('test_runner.unittest.defaultTestLoader.discover', return_value=self.fixture()), \
             patch.dict(os.environ, {'AWS_NATIVE_DRAWIO_RUNTIME':'present','AWS_DRAWIO_PROFILE':'present'}), \
             contextlib.redirect_stderr(io.StringIO()):
            report,code=run_tests('unit',Path(d)/'out')
        self.assertEqual(code,0);self.assertEqual(report['tests_run'],1)
        self.assertEqual([t['group'] for t in report['timings']],['unit'])

    def test_native_without_runtime_is_unavailable_not_successful_skip(self):
        with tempfile.TemporaryDirectory() as d, patch('test_runner.unittest.defaultTestLoader.discover', return_value=self.fixture()), patch.dict(os.environ,{},clear=True):
            report,code=run_tests('native',Path(d)/'out')
        self.assertEqual(code,3);self.assertEqual(report['status'],'unavailable')
        self.assertEqual(report['errors'][0]['code'],'E_RUNTIME_REQUIRED')

    def test_empty_selection_is_not_a_pass(self):
        with tempfile.TemporaryDirectory() as d, patch('test_runner.unittest.defaultTestLoader.discover', return_value=self.fixture()):
            report,code=run_tests('unit',Path(d)/'out',match='nonexistent')
        self.assertEqual(code,2);self.assertEqual(report['errors'][0]['code'],'E_TEST_SELECTION_EMPTY')


class ArtifactRetentionTests(unittest.TestCase):
    def exercise(self, base, keep, failing=False):
        paths=[]
        class Native(unittest.TestCase):
            native_render=True
            supports_artifacts=True
            def runTest(self):
                with artifact_directory(self) as directory:
                    paths.append(directory)
                    (directory/'probe.txt').write_text('retained evidence')
                    if failing:
                        self.fail('deliberate test failure')
        with patch('test_runner.unittest.defaultTestLoader.discover', return_value=unittest.TestSuite([Native()])), \
             patch.dict(os.environ,{'AWS_NATIVE_DRAWIO_RUNTIME':'present','AWS_DRAWIO_PROFILE':'present'}), \
             contextlib.redirect_stderr(io.StringIO()):
            report,code=run_tests('native',base/'out',keep_artifacts=keep)
        self.assertEqual(json.loads((base/'out/tests-summary.json').read_text()),report)
        self.assertEqual(code,2 if failing else 0)
        return report,paths[0]

    def test_retains_success_and_failure_with_absolute_report_paths(self):
        for failing in (False,True):
            with self.subTest(failing=failing), tempfile.TemporaryDirectory() as directory:
                base=Path(directory)
                report,path=self.exercise(base,True,failing)
                self.assertEqual((path/'probe.txt').read_text(),'retained evidence')
                self.assertTrue(path.is_absolute())
                self.assertEqual(path.parent,(base/'out/artifacts').resolve())
                self.assertEqual(report['artifacts'],[{'test':report['timings'][0]['test'],'directory':str(path)}])
                self.assertEqual(report['status'],'failed' if failing else 'passed')

    def test_default_still_cleans_up_success_and_failure(self):
        for failing in (False,True):
            with self.subTest(failing=failing), tempfile.TemporaryDirectory() as directory:
                report,path=self.exercise(Path(directory),False,failing)
                self.assertFalse(path.exists())
                self.assertEqual(report['artifacts'],[])
                self.assertFalse(report['keep_artifacts'])

    def test_unsupported_selection_does_not_run_or_claim_partial_retention(self):
        for mixed in (False,True):
            with self.subTest(mixed=mixed), tempfile.TemporaryDirectory() as directory:
                called=[]
                class Unsupported(unittest.TestCase):
                    def runTest(self):called.append(True)
                class Supported(Unsupported):
                    supports_artifacts=True
                tests=[Unsupported()]+([Supported()] if mixed else [])
                with patch('test_runner.unittest.defaultTestLoader.discover',return_value=unittest.TestSuite(tests)):
                    report,code=run_tests('unit',Path(directory)/'out',keep_artifacts=True)
                self.assertEqual(code,2)
                self.assertEqual(report['errors'][0]['code'],'E_ARTIFACT_RETENTION_UNSUPPORTED')
                self.assertEqual(report['artifacts'],[])
                self.assertEqual(called,[])

    def test_existing_output_and_existing_artifact_directory_are_not_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory);marker=path/'probe.txt';marker.write_text('existing')
            report,code=run_tests('native',path,keep_artifacts=True)
            self.assertEqual(code,2)
            self.assertEqual(report['errors'][0]['code'],'E_OUTPUT_EXISTS')
            test=unittest.TestCase();test.artifact_directory=path
            with self.assertRaises(FileExistsError):
                with artifact_directory(test):self.fail('Existing directory was accepted')
            self.assertEqual(marker.read_text(),'existing')
