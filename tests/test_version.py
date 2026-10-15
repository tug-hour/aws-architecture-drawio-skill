"""Release identity, propagation and integrity regressions without new dependencies."""
import hashlib
import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import version
from version import VersionError, get_version, parse_version
from check_bundle import audit
from package_release import package
from make_viewer import make
from project import render_project
from acceptance import acceptance
from run import run


class VersionTests(unittest.TestCase):
    def test_bad_metadata_is_rejected(self):
        for data in ('{', 'null', '[]', '{}', '{"version":3}', '{"version":"1.2"}',
                     '{"version":"01.2.3"}', '{"version":"1.2.3","extra":true}',
                     '{"version":"1.2.3","version":"4.5.6"}'):
            with self.subTest(data=data), self.assertRaises(VersionError):
                parse_version(data)

    def test_missing_and_changed_version_has_no_fallback_or_cache(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / 'version.json'
            with patch.object(version, 'VERSION_PATH', path):
                with self.assertRaises(VersionError): get_version()
                path.write_text('{"version":"8.7.6"}')
                self.assertEqual(get_version(), '8.7.6')
                path.write_text('{"version":"8.7.7"}')
                self.assertEqual(get_version(), '8.7.7')

    def test_missing_version_prevents_renderer_invocation(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            with patch.object(version, 'VERSION_PATH', root / 'missing'), patch('build_drawio.drawio_version') as renderer:
                result, code = run(ROOT / 'examples/japanese-auto.json', root / 'out', root / 'bin', root / 'profile', root / 'runtime')
                self.assertNotEqual(code, 0)
                self.assertFalse(result['production_eligible'])
                renderer.assert_not_called()

    def test_verifier_rejects_different_generator_version_before_render(self):
        from verify_native import verify
        with tempfile.TemporaryDirectory() as d:
            base = Path(d); source = base / 'source';source.mkdir()
            (source / 'validation.json').write_text('{"candidate_version":"0.0.0"}')
            with patch('build_drawio.drawio_version') as renderer:
                result, code = verify(source, base / 'qa', base / 'runtime', base / 'bin', base / 'profile')
            self.assertEqual(code, 2)
            self.assertEqual(result['errors'][0]['code'], 'E_RELEASE_VERSION_MISMATCH')
            renderer.assert_not_called()

    def assert_validation_metadata_failure(self, value):
        from verify_native import verify
        with tempfile.TemporaryDirectory() as d:
            base = Path(d); source = base / 'source'; source.mkdir()
            metadata = json.dumps(value)
            (source / 'validation.json').write_text(metadata)
            with patch('build_drawio.drawio_version') as renderer, patch('build_drawio.export_file') as exporter, patch('verify_native.invoke') as browser:
                result, code = verify(source, base / 'qa', base / 'runtime', base / 'bin', base / 'profile')
            self.assertEqual(code, 2)
            self.assertEqual(result['status'], 'failed')
            self.assertFalse(result['production_eligible'])
            self.assertEqual(result['errors'][0]['code'], 'E_VALIDATION_METADATA')
            self.assertEqual(json.loads((base / 'qa/browser-validation.json').read_text()), result)
            self.assertEqual({p.name for p in (base / 'qa').iterdir()}, {'browser-validation.json'})
            self.assertEqual((source / 'validation.json').read_text(), metadata)
            renderer.assert_not_called(); exporter.assert_not_called(); browser.assert_not_called()

    def test_verifier_reports_non_object_validation_metadata(self):
        for value in (None, [], '0.6.1', 3, True):
            with self.subTest(value=value):
                self.assert_validation_metadata_failure(value)

    def test_verifier_reports_missing_or_non_string_generator_version(self):
        for value in ({}, {'candidate_version':None}, {'candidate_version':[]}, {'candidate_version':3}):
            with self.subTest(value=value):
                self.assert_validation_metadata_failure(value)

    def test_project_report_and_viewer_follow_changed_definition(self):
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            definition = base / 'version.json'
            definition.write_text('{"version":"8.7.6"}')
            model = {'schema_version':'1.0', 'mode':'draft', 'nodes':[{'id':'n','asset_id':'aws4.s3'}], 'edges':[]}
            project = {'project_version':'1.0', 'model':model, 'views':[{
                'id':'one', 'title':'One view', 'node_ids':['n'], 'edge_ids':[], 'flow_ids':[],
                'layout':{'mode':'auto'}, 'display':{'width_px':1200,'height_px':800,'min_text_px':12},
            }]}
            source = base / 'project.json'
            source.write_text(json.dumps(project))
            # Exercise the real project report on the render-failure path; rendering itself is covered separately.
            with patch.object(version, 'VERSION_PATH', definition), patch('project.run', return_value=({'status':'failed','errors':[]}, 3)):
                result, code = render_project(source, base / 'project', base / 'bin', base / 'profile', base / 'runtime')
                self.assertEqual(code, 2)
                self.assertEqual(result['version'], '8.7.6')
                (base / 'project/one').mkdir()
                (base / 'project/one/architecture.json').write_text(json.dumps(model))
                make(base / 'project')
                self.assertIn('AWS構成図 8.7.6', (base / 'project/image-review.html').read_text())

    def test_viewer_does_not_relabel_old_project(self):
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            (base / 'project-report.json').write_text(json.dumps({'version':'0.0.0','views':{}}))
            with self.assertRaises(ValueError): make(base)
            self.assertFalse((base / 'image-review.html').exists())

    def test_acceptance_report_uses_changed_definition_even_on_environment_failure(self):
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            definition = base / 'version.json'
            definition.write_text('{"version":"8.7.6"}')
            with patch.object(version, 'VERSION_PATH', definition), patch('acceptance.diagnose', return_value={'status':'unavailable','errors':[]}):
                result, code = acceptance(base / 'out', base / 'bin', base / 'profile', base / 'runtime')
            self.assertEqual(code, 3)
            self.assertEqual(result['version'], '8.7.6')
            self.assertEqual(json.loads((base / 'out/acceptance-summary.json').read_text())['version'], '8.7.6')


class ReleaseTests(unittest.TestCase):
    def source(self, base):
        source = base / 'source'
        (source / 'references').mkdir(parents=True)
        (source / 'SKILL.md').write_text('---\nname: aws-architecture-drawio\ndescription: Test\n---\n')
        (source / 'references/version.json').write_text('{"version":"8.7.6"}')
        (source / 'references/release-manifest.json').write_text('{"version":"0.0.0"}')
        for name in ('LICENSE', 'README.md', 'THIRD_PARTY_NOTICES.md'):
            (source / name).write_text('Fixture for ' + name + '\n')
        return source

    def archive(self, base, definition=b'{"version":"8.7.6"}', manifest_version='8.7.6', extra=None, manifest=True, manifest_transform=None):
        files = {'SKILL.md':b'fixture'}
        if definition is not None: files['references/version.json'] = definition
        if extra: files.update(extra)
        record = {'version':manifest_version, 'files':{k:hashlib.sha256(v).hexdigest() for k,v in files.items()}}
        if manifest:
            data = json.dumps(record)
            files['references/release-manifest.json'] = (manifest_transform(data) if manifest_transform else data).encode()
        archive = base / 'release.zip'
        with zipfile.ZipFile(archive,'w') as z:
            for name, data in files.items(): z.writestr('aws-architecture-drawio/' + name, data)
        checksum = base / 'release.zip.sha256'
        checksum.write_text(hashlib.sha256(archive.read_bytes()).hexdigest() + '  release.zip\n')
        return archive, checksum

    def test_package_uses_definition_not_stale_manifest_and_does_not_write_source(self):
        with tempfile.TemporaryDirectory() as d:
            base = Path(d); source = self.source(base)
            before = {p.relative_to(source):p.read_bytes() for p in source.rglob('*') if p.is_file()}
            result, code = package(source, base / 'out')
            self.assertEqual(code, 0, result)
            self.assertEqual(result['version'], '8.7.6')
            self.assertEqual(Path(result['archive']).name, 'aws-architecture-drawio-8.7.6.zip')
            record = json.loads((base / 'out/release-manifest.json').read_text())
            self.assertIn('references/version.json', record['files'])
            self.assertNotIn('references/release-manifest.json', record['files'])
            with zipfile.ZipFile(result['archive']) as bundle:
                for name in ('LICENSE', 'README.md', 'THIRD_PARTY_NOTICES.md'):
                    content = (source / name).read_bytes()
                    self.assertEqual(bundle.read('aws-architecture-drawio/' + name), content)
                    self.assertEqual(record['files'][name], hashlib.sha256(content).hexdigest())
            self.assertEqual(before, {p.relative_to(source):p.read_bytes() for p in source.rglob('*') if p.is_file()})
            second, _ = package(source, base / 'second')
            self.assertEqual(Path(result['archive']).read_bytes(), Path(second['archive']).read_bytes())

    def test_package_refuses_symlink_before_output(self):
        for name in ('references/link.json', 'LICENSE', 'README.md', 'THIRD_PARTY_NOTICES.md'):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as d:
                base = Path(d); source = self.source(base)
                path = source / name
                if path.exists(): path.unlink()
                path.symlink_to(source / 'references/version.json')
                with self.assertRaises(ValueError): package(source, base / 'out')
                self.assertFalse((base / 'out').exists())

    def test_package_refuses_existing_output(self):
        with tempfile.TemporaryDirectory() as d:
            base = Path(d); source = self.source(base); out = base / 'out';out.mkdir()
            (out / 'keep').write_text('keep')
            with self.assertRaises(ValueError): package(source, out)
            self.assertEqual((out / 'keep').read_text(), 'keep')

    def test_package_refuses_output_inside_source(self):
        with tempfile.TemporaryDirectory() as d:
            source = self.source(Path(d))
            with self.assertRaises(ValueError): package(source, source / 'out')
            self.assertFalse((source / 'out').exists())

    def test_package_refuses_missing_required_files_before_output(self):
        for name in ('references/version.json', 'LICENSE', 'README.md', 'THIRD_PARTY_NOTICES.md'):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as d:
                base = Path(d); source = self.source(base)
                (source / name).unlink()
                with self.assertRaises((KeyError, FileNotFoundError)): package(source, base / 'out')
                self.assertFalse((base / 'out').exists())

    def test_recomputed_hashes_cannot_hide_version_mismatch(self):
        with tempfile.TemporaryDirectory() as d:
            archive, checksum = self.archive(Path(d), manifest_version='8.7.5')
            for legacy in (False, True):
                result, code = audit(archive, checksum, allow_legacy=legacy)
                self.assertEqual(code, 2)
                self.assertEqual(result['code'], 'E_BUNDLE_VERSION_MISMATCH')

    def test_manifest_duplicate_version_keys_are_rejected(self):
        for definition in (b'{"version":"8.7.6"}', None):
            for first_version in ('8.7.5', '8.7.6'):
                with self.subTest(definition=definition, first_version=first_version), tempfile.TemporaryDirectory() as d:
                    archive, checksum = self.archive(
                        Path(d), definition=definition,
                        manifest_transform=lambda data: '{"version":' + json.dumps(first_version) + ',' + data[1:])
                    before = (archive.read_bytes(), checksum.read_bytes())
                    for legacy in (False, True):
                        result, code = audit(archive, checksum, allow_legacy=legacy)
                        self.assertEqual(code, 2)
                        self.assertEqual(result['code'], 'E_BUNDLE_MANIFEST')
                    self.assertEqual((archive.read_bytes(), checksum.read_bytes()), before)

    def test_manifest_duplicate_file_keys_are_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            archive, checksum = self.archive(
                Path(d), manifest_transform=lambda data: data.replace('"files": {', '"files": {"SKILL.md":"incorrect",', 1))
            for legacy in (False, True):
                result, code = audit(archive, checksum, allow_legacy=legacy)
                self.assertEqual(code, 2)
                self.assertEqual(result['code'], 'E_BUNDLE_MANIFEST')

    def test_invalid_canonical_metadata_is_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            archive, checksum = self.archive(Path(d), definition=b'{}')
            result, code = audit(archive, checksum)
            self.assertEqual(code, 2)
            self.assertEqual(result['code'], 'E_BUNDLE_VERSION_METADATA')

    def test_duplicate_version_sources_are_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            archive, checksum = self.archive(Path(d), extra={'references/native-catalog.json':b'{"candidate_version":"8.7.6"}'})
            result, code = audit(archive, checksum)
            self.assertEqual(code, 2)
            self.assertEqual(result['code'], 'E_BUNDLE_VERSION_DUPLICATE')

    def test_legacy_requires_explicit_opt_in(self):
        with tempfile.TemporaryDirectory() as d:
            archive, checksum = self.archive(Path(d), definition=None)
            result, code = audit(archive, checksum)
            self.assertEqual(code, 2)
            self.assertEqual(result['code'], 'E_BUNDLE_VERSION_REQUIRED')
            result, code = audit(archive, checksum, allow_legacy=True)
            self.assertEqual(code, 0)
            self.assertTrue(result['warnings'])

    def test_no_manifest_is_rejected_by_default(self):
        with tempfile.TemporaryDirectory() as d:
            archive, checksum = self.archive(Path(d), definition=None, manifest=False)
            result, code = audit(archive, checksum)
            self.assertEqual(code, 2)
            self.assertEqual(result['code'], 'E_BUNDLE_MANIFEST_REQUIRED')

    def test_current_metadata_requires_manifest_even_in_legacy_mode(self):
        with tempfile.TemporaryDirectory() as d:
            archive, checksum = self.archive(Path(d), manifest=False)
            result, code = audit(archive, checksum, allow_legacy=True)
            self.assertEqual(code, 2)
            self.assertEqual(result['code'], 'E_BUNDLE_MANIFEST_REQUIRED')


if __name__ == '__main__':
    unittest.main()
