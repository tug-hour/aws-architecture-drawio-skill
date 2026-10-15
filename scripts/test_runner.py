"""Select unit/native tests explicitly and record timings without installing a runtime."""
import argparse
import contextlib
import json
import os
import tempfile
import time
import unittest
from pathlib import Path
from catalog import ROOT
from version import get_version
from release_source import snapshot


def flatten(suite):
    for test in suite:
        if isinstance(test, unittest.TestSuite):
            yield from flatten(test)
        else:
            yield test


def select(suite, group, match=None):
    return [test for test in flatten(suite)
            if (group == 'all' or bool(getattr(test, 'native_render', False)) == (group == 'native'))
            and (match is None or match in test.id())]


@contextlib.contextmanager
def artifact_directory(test):
    """Use a fresh retained directory only when the runner assigned one."""
    destination = getattr(test, 'artifact_directory', None)
    if destination is None:
        with tempfile.TemporaryDirectory() as directory:
            yield Path(directory)
    else:
        destination.mkdir(parents=True, exist_ok=False)
        yield destination


class TimedResult(unittest.TextTestResult):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.timings = []

    def startTest(self, test):
        self.started = time.monotonic()
        super().startTest(test)

    def stopTest(self, test):
        self.timings.append({'test': test.id(), 'group': 'native' if getattr(test, 'native_render', False) else 'unit',
                             'seconds': round(time.monotonic() - self.started, 6)})
        super().stopTest(test)


def run_tests(group, output, match=None, keep_artifacts=False):
    if output.exists():
        return {'status': 'failed', 'errors': [{'code': 'E_OUTPUT_EXISTS'}]}, 2
    output.mkdir(parents=True, exist_ok=False)
    start = time.monotonic()
    report = {'status': 'running', 'group': group, 'match': match,
              'keep_artifacts': keep_artifacts, 'errors': []}
    tests = []
    retained = []
    def finish(code):
        report['artifacts'] = [{'test': ident, 'directory': str(directory)}
                               for ident, directory in retained if directory.is_dir()]
        report.update(exit_code=code, seconds=round(time.monotonic() - start, 6))
        (output / 'tests-summary.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
        return report, code
    try:
        report.update(version=get_version(), source_binding=snapshot(ROOT))
        tests = select(unittest.defaultTestLoader.discover(str(ROOT / 'tests')), group, match)
        if not tests:
            report.update(status='failed', errors=[{'code': 'E_TEST_SELECTION_EMPTY'}])
            return finish(2)
        if keep_artifacts and any(not getattr(test, 'supports_artifacts', False) for test in tests):
            report.update(status='failed', errors=[{'code':'E_ARTIFACT_RETENTION_UNSUPPORTED',
                          'tests':[test.id() for test in tests if not getattr(test, 'supports_artifacts', False)]}])
            return finish(2)
        for index, test in enumerate(tests):
            test.artifact_directory = (output.resolve()/'artifacts'/str(index)) if keep_artifacts else None
            if keep_artifacts:
                retained.append((test.id(), test.artifact_directory))
        if any(getattr(test, 'native_render', False) for test in tests) and not all(os.environ.get(k) for k in ('AWS_NATIVE_DRAWIO_RUNTIME', 'AWS_DRAWIO_PROFILE')):
            report.update(status='unavailable', errors=[{'code': 'E_RUNTIME_REQUIRED'}])
            return finish(3)
        result = unittest.TextTestRunner(verbosity=2, resultclass=TimedResult).run(unittest.TestSuite(tests))
        report.update(status='passed' if result.wasSuccessful() and not result.skipped else 'failed',
                      tests_run=result.testsRun, skipped=len(result.skipped), timings=result.timings,
                      failures=[test.id() for test, _ in result.failures], errors=[{'test': test.id(), 'traceback': text} for test, text in result.errors])
        if snapshot(ROOT) != report['source_binding']:
            report.update(status='failed', errors=report['errors'] + [{'code': 'E_SOURCE_CHANGED'}])
        return finish(0 if report['status'] == 'passed' else 2)
    except (OSError, ValueError, TypeError, KeyError) as error:
        report.update(status='failed', errors=[{'code': 'E_TEST_RUNNER', 'message': str(error)}])
        return finish(3)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--group', choices=('unit', 'native', 'all'), default='unit')
    parser.add_argument('--match', help='Select test IDs containing this text; no automatic retry')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--keep-artifacts', action='store_true', help='Retain supported tests under the new output directory, including failures')
    args = parser.parse_args()
    result, code = run_tests(args.group, args.output, args.match, args.keep_artifacts)
    print(json.dumps({k: v for k, v in result.items() if k not in ('timings', 'source_binding')}, ensure_ascii=False))
    raise SystemExit(code)
