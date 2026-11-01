"""Run isolated tests and local real-render acceptance. No installs or CI mutations."""
import argparse
import json
import os
import subprocess
import sys
import time
from contextlib import contextmanager
from pathlib import Path
from catalog import ROOT
from doctor import diagnose
from run import run
from release_source import snapshot
from schema import Failure
from version import get_version, VersionError


def acceptance(output, binary, profile, runtime, cases_only=False):
    if output.exists():
        return {'status': 'failed', 'errors': [{'code': 'E_OUTPUT_EXISTS'}]}, 2
    output.mkdir(parents=True, exist_ok=False)
    started = time.monotonic()
    report = {'status': 'running', 'scope': 'cases-only' if cases_only else 'tests-and-cases',
              'cases': {}, 'errors': [], 'timings': {}}

    def persist():
        (output / 'acceptance-summary.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')

    def finish(status, code, errors=None):
        report.update(status=status, exit_code=code, seconds=round(time.monotonic() - started, 6))
        if errors is not None: report['errors'] = errors
        persist()
        return report, code

    @contextmanager
    def timed(name):
        start = time.monotonic()
        try:
            yield
        finally:
            report['timings'][name] = round(time.monotonic() - start, 6)

    try:
        with timed('preflight'):
            report['version'] = get_version()
            report['source_binding'] = snapshot(ROOT)
            report['environment_check'] = diagnose(binary, runtime)
        if report['environment_check']['status'] != 'ready':
            return finish('failed', 3, report['environment_check']['errors'])
        persist()
        if not cases_only:
            env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', AWS_NATIVE_DRAWIO_RUNTIME=str(runtime.resolve()),
                       AWS_DRAWIO_PROFILE=str(profile.resolve()), AWS_DRAWIO_BINARY=str(binary.resolve()))
            print('Running unit and native integration tests', flush=True)
            with timed('tests'):
                tests = subprocess.run([sys.executable, '-B', str(ROOT / 'scripts/test_runner.py'), '--group', 'all',
                                        '--output', str(output / 'tests')], env=env, text=True, capture_output=True, timeout=900)
            (output / 'tests.txt').write_text(tests.stdout + tests.stderr)
            report['tests_exit_code'] = tests.returncode
            if tests.returncode:
                return finish('failed', 2, [{'code': 'E_TESTS_FAILED'}])
        print('Rendering architecture examples', flush=True)
        with timed('examples'):
            for path in sorted((ROOT / 'examples/real-world').glob('*.json')):
                start = time.monotonic()
                result, code = run(path, output / path.stem, binary, profile, runtime)
                report['cases'][path.stem] = {'status': result['status'], 'exit_code': code, 'errors': result.get('errors', []),
                                             'warnings': result.get('warnings', []), 'seconds': round(time.monotonic() - start, 6)}
                persist()
                print(json.dumps({path.stem: report['cases'][path.stem]}, ensure_ascii=False), flush=True)
        from project import render_project
        from corpus import corpus
        print('Rendering canonical project and layout corpus', flush=True)
        with timed('project'):
            project_result, project_code = render_project(ROOT / 'examples/projects/modern-web-iot.json', output / 'project', binary, profile, runtime)
        report.update(project_status=project_result['status'], project_exit_code=project_code)
        persist()
        with timed('corpus'):
            corpus_result = corpus(output / 'corpus', binary, profile, runtime)
        report['corpus_status'] = corpus_result['status']
        if snapshot(ROOT) != report['source_binding']:
            return finish('failed', 2, [{'code': 'E_SOURCE_CHANGED', 'message': 'Source changed during acceptance; rerun against fixed inputs'}])
        passed = all(c['exit_code'] == 0 for c in report['cases'].values()) and project_code == 0 and corpus_result['status'] == 'passed'
        return finish('passed' if passed else 'failed', 0 if passed else 2, [] if passed else [{'code': 'E_ACCEPTANCE_FAILED'}])
    except Failure as error:
        return finish('failed', error.exit_code, [error.issue])
    except VersionError as error:
        return finish('failed', 3, [{'code': 'E_VERSION_METADATA', 'message': str(error)}])
    except (OSError, ValueError, TypeError, KeyError, subprocess.TimeoutExpired) as error:
        return finish('failed', 3, [{'code': 'E_ACCEPTANCE_RUNTIME', 'message': str(error)}])


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--runtime', type=Path, required=True)
    parser.add_argument('--profile', type=Path, required=True)
    parser.add_argument('--drawio', type=Path, default=Path('/Applications/draw.io.app/Contents/MacOS/draw.io'))
    parser.add_argument('--cases-only', action='store_true', help='Run acceptance cases without repeating tests; report scope stays explicit')
    args = parser.parse_args()
    result, code = acceptance(args.output, args.drawio, args.profile, args.runtime, args.cases_only)
    print(json.dumps({k: v for k, v in result.items() if k not in ('cases', 'source_binding')}, ensure_ascii=False))
    raise SystemExit(code)
