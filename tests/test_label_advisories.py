"""AZ review hints and old-input guidance must never rewrite or relax inputs."""
import copy
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from build_drawio import normalize, author
from catalog import manifest
from layout import layout
from quality import operational_quality
from run import run
from schema import Failure
from service_labels import az_label_warnings
from test_runner import artifact_directory


def fixture():
    return {'schema_version': '1.0', 'theme': 'both',
            'nodes': [{'id': 'api', 'asset_id': 'aws4.fargate', 'label': 'AWS Fargate',
                       'description': 'ECS API・AZ-A', 'group_id': 'subnet'}], 'edges': [],
            'groups': [{'id': 'az', 'type': 'group.availability-zone', 'role': 'containment', 'label': 'AZ-A'},
                       {'id': 'subnet', 'type': 'group.private-subnet', 'role': 'containment', 'parent_id': 'az'}]}


class AZAdvisoryTests(unittest.TestCase):
    def warnings(self, raw):
        return az_label_warnings(normalize(raw, manifest()))

    def test_nested_redundancy_preserves_input_and_rendered_model(self):
        raw = fixture(); before = copy.deepcopy(raw)
        a = normalize(raw, manifest()); before_normalized = copy.deepcopy(a)
        lay, warnings = layout(a, manifest())
        az = [w for w in warnings if w['code'].startswith('W_AZ_')]
        self.assertEqual(len(az), 1)
        self.assertEqual(az[0]['code'], 'W_AZ_LABEL_REDUNDANT')
        self.assertEqual(az[0]['element_ids'], ['api', 'az'])
        self.assertEqual(az[0]['details']['fields'], ['description'])
        with patch('layout.az_label_warnings', return_value=[]):
            old_lay, _ = layout(a, manifest())
        self.assertEqual(lay, old_lay)
        for theme in ('light', 'dark'):
            self.assertEqual(author(a, lay, manifest(), theme), author(a, old_lay, manifest(), theme))
        self.assertEqual(a, before_normalized)
        self.assertEqual(raw, before)
        quality = operational_quality({'status': 'passed', 'warnings': az}, lay,
                                      {'width_px': 4000, 'height_px': 4000, 'min_text_px': 12})
        self.assertEqual(quality['status'], 'passed')
        self.assertTrue(quality['human_visual_review_required'])

    def test_different_az_is_advisory_in_both_modes(self):
        for mode in ('draft', 'production'):
            raw = fixture(); raw['mode'] = mode
            raw['nodes'][0]['description'] = 'ECS API・AZ-C'
            warning, = self.warnings(raw)
            self.assertEqual(warning['code'], 'W_AZ_LABEL_MISMATCH')
            self.assertEqual(warning['details']['frame_az'], 'AZ-A')
            self.assertEqual(warning['details']['mentioned_az'], 'AZ-C')

    def test_label_and_description_produce_one_warning(self):
        raw = fixture(); raw['nodes'][0].update(asset_id='aws4.user', label='利用者・AZ-A', description='AZ-A')
        warning, = self.warnings(raw)
        self.assertEqual(warning['details']['fields'], ['label', 'description'])

    def test_missing_frame_or_az_mention_is_not_inferred(self):
        raw = fixture(); raw['groups'] = []; raw['nodes'][0].pop('group_id')
        self.assertEqual(self.warnings(raw), [])
        raw = fixture(); raw['nodes'][0]['description'] = 'Writer・障害時に昇格'
        self.assertEqual(self.warnings(raw), [])

    def test_multiple_azs_and_compact_list_are_not_single_membership(self):
        for caption in ('ALBはAZ-AとAZ-Cを利用', 'AZ-A/C', 'AZ-A／C', 'AZ-A / C', 'AZ-A/AZ-C', 'AZ-A,C', 'AZ-A、C'):
            raw = fixture(); raw['nodes'][0]['description'] = caption
            self.assertEqual(self.warnings(raw), [], caption)

    def test_ambiguous_or_custom_frame_heading_is_not_inferred(self):
        for heading in ('AZ-A / AZ-C', '東京AZ', 'Availability Zone A', 'AZ-A/C', 'AZ-A,C', 'AZ-A、C'):
            raw = fixture(); raw['groups'][0]['label'] = heading
            self.assertEqual(self.warnings(raw), [], heading)
        raw = fixture(); raw['groups'][1].update(type='group.availability-zone', label='AZ-C')
        self.assertEqual(self.warnings(raw), [])

    def test_contextual_heading_reports_both_kinds_without_mutation(self):
        for heading in ('東京 AZ-A','東京AZ-A','AZ-A（主系）'):
            for mention,code in (('AZ-A','W_AZ_LABEL_REDUNDANT'),('AZ-C','W_AZ_LABEL_MISMATCH')):
                raw=fixture();raw['groups'][0]['label']=heading
                raw['nodes'][0]['description']='Reader・'+mention+'障害時に昇格'
                before=copy.deepcopy(raw)
                warning,=self.warnings(raw)
                self.assertEqual(warning['code'],code)
                self.assertEqual(warning['details']['frame_az'],'AZ-A')
                self.assertEqual(raw,before)

    def test_real_multi_region_example_heading_is_checked(self):
        raw=json.loads((ROOT/'examples/real-world/multi-region-dr.json').read_text())
        next(n for n in raw['nodes'] if n['id']=='tapia')['description']='ECS API・AZ-C'
        warnings=self.warnings(raw)
        warning,=[w for w in warnings if w['element_ids'][0]=='tapia']
        self.assertEqual(warning['code'],'W_AZ_LABEL_MISMATCH')
        self.assertEqual(warning['details']['frame_az'],'AZ-A')

    def test_review_regression_separators_allow_context_but_not_compact_az_lists(self):
        for location in ('heading','caption'):
            for suffix in (' / 主系','／主系',', primary','，primary','、primary',' / primary',' / DB'):
                for az,code in (('AZ-A','W_AZ_LABEL_REDUNDANT'),('AZ-C','W_AZ_LABEL_MISMATCH')):
                    with self.subTest(location=location,suffix=suffix,az=az):
                        raw=fixture();raw['nodes'][0]['description']='ECS API・'+az
                        if location=='heading':raw['groups'][0]['label']='東京 AZ-A'+suffix
                        else:raw['nodes'][0]['description']+=suffix
                        before=copy.deepcopy(raw)
                        warning,=self.warnings(raw)
                        self.assertEqual(warning['code'],code)
                        self.assertEqual(raw,before)
            for text in ('AZ-A/C','AZ-A / C','AZ-A,C','AZ-A、C','AZ-1/2','AZ-1/22','AZ-1a/2b','AZ-AA/CC','AZ-A / AZ-C'):
                raw=fixture()
                if location=='heading':raw['groups'][0]['label']=text
                else:raw['nodes'][0]['description']=text
                self.assertEqual(self.warnings(raw),[],(location,text))

    def test_only_az_containment_counts(self):
        raw = fixture(); raw['groups'][0]['type'] = 'group.region'
        self.assertEqual(self.warnings(raw), [])
        raw = fixture(); raw['nodes'][0]['description'] = 'prefixAZ-A / AZ-A_suffix / AZ-A-extra'
        warnings = self.warnings(raw)
        # The literal custom AZ name is distinct; AZ-A is never matched as its prefix.
        self.assertEqual(warnings, [])

    def test_role_and_failover_text_is_kept_in_review_candidate(self):
        raw = fixture(); raw['nodes'][0]['description'] = 'Reader・AZ-C障害時にWriterへ昇格'
        warning, = self.warnings(raw)
        self.assertEqual(warning['code'], 'W_AZ_LABEL_MISMATCH')
        self.assertEqual(raw['nodes'][0]['description'], 'Reader・AZ-C障害時にWriterへ昇格')


class MigrationGuidanceTests(unittest.TestCase):
    def failure(self, label, description=None, mode='production'):
        raw = fixture(); raw['mode'] = mode
        raw['nodes'][0].update(asset_id='aws4.aurora', label=label)
        raw['nodes'][0].pop('description')
        if description is not None:
            raw['nodes'][0]['description'] = description
        original = copy.deepcopy(raw)
        with self.assertRaises(Failure) as caught:
            normalize(raw, manifest())
        self.assertEqual(raw, original)
        return raw, caught.exception

    def test_purpose_and_existing_description_are_preserved_in_proposal(self):
        for mode in ('production', 'draft'):
            raw, error = self.failure('Amazon Aurora Writer', '昇格後もReaderを保持', mode)
            self.assertEqual(error.issue['code'], 'E_SERVICE_NAME')
            self.assertEqual(error.exit_code, 2)
            self.assertEqual(error.issue['element_ids'], ['api'])
            hint = error.issue['details']['migration']
            self.assertFalse(hint['automatic'])
            self.assertEqual(hint['field'], 'label')
            self.assertEqual(hint['allowed_names'], ['Amazon Aurora'])
            self.assertEqual(hint['suggested_fields'], {'label': 'Amazon Aurora', 'description': 'Writer / 昇格後もReaderを保持'})
            raw['nodes'][0].update(hint['suggested_fields'])
            self.assertEqual(normalize(raw, manifest())['nodes'][0]['description'], 'Writer / 昇格後もReaderを保持')

    def test_multiline_legacy_label_keeps_original_error_and_all_purpose_text(self):
        raw, error = self.failure('Amazon Aurora\nReader\n障害時に昇格')
        self.assertEqual(error.issue['code'], 'E_SERVICE_LABEL')
        hint = error.issue['details']['migration']
        self.assertEqual(hint['input_label'], raw['nodes'][0]['label'])
        raw['nodes'][0].update(hint['suggested_fields'])
        self.assertEqual(normalize(raw, manifest())['nodes'][0]['description'], 'Reader 障害時に昇格')

    def test_brand_line_break_can_be_reviewed_without_losing_existing_description(self):
        raw, error = self.failure('Amazon\nAurora', 'Writer')
        self.assertEqual(error.issue['code'], 'E_SERVICE_LABEL')
        hint = error.issue['details']['migration']
        self.assertEqual(hint['suggested_fields'], {'label': 'Amazon Aurora'})
        raw['nodes'][0].update(hint['suggested_fields'])
        self.assertEqual(normalize(raw, manifest())['nodes'][0]['description'], 'Writer')

    def test_wrong_service_and_word_break_do_not_get_a_guessed_replacement(self):
        for label in ('Amazon S3', 'Amazon Aur\nora', 'Aurora Writer', 'Amazon AuroraWriter'):
            _, error = self.failure(label)
            self.assertEqual(error.issue['code'], 'E_SERVICE_NAME')
            self.assertNotIn('suggested_fields', error.issue['details']['migration'])

    def test_long_description_is_not_truncated_to_make_a_proposal(self):
        _, error = self.failure('Amazon Aurora Writer', 'x' * 120)
        hint = error.issue['details']['migration']
        self.assertNotIn('suggested_fields', hint)
        self.assertEqual(hint['existing_description'], 'x' * 120)

    def test_failed_run_persists_guidance_without_starting_renderer(self):
        raw, _ = self.failure('Amazon Aurora・Writer')
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory); source = base/'input.json'; source.write_text(json.dumps(raw))
            with patch('legacy_drawio.drawio_version') as renderer:
                result, code = run(source, base/'out', base/'bin', base/'profile', base/'runtime')
            renderer.assert_not_called()
            self.assertEqual(code, 2)
            self.assertEqual(result, json.loads((base/'out/result.json').read_text()))
            self.assertEqual(result['errors'][0]['details']['migration']['suggested_fields']['description'], 'Writer')


@unittest.skipUnless(os.environ.get('AWS_NATIVE_DRAWIO_RUNTIME'), 'Approved native render runtime not specified')
class AdvisoryNativeTests(unittest.TestCase):
    native_render = True
    supports_artifacts = True

    def test_warnings_survive_generation_and_fresh_verification_in_both_themes(self):
        with artifact_directory(self) as directory:
            base = Path(directory); source = base/'input.json'; raw = fixture()
            raw['groups'][0]['label']='東京 AZ-A / 主系'
            raw['nodes'][0].update(asset_id='aws4.ec2',label='Amazon Elastic Compute Cloud',description='EC2アプリ・AZ-A')
            raw['glossary']=[{'asset_id':'aws4.ec2','kind':'note','short_name':'EC2運用','full_name':'夜間停止'}]
            raw['nodes'].append({'id': 'worker', 'asset_id': 'aws4.fargate', 'label': 'AWS Fargate',
                                 'description': 'ECSワーカー・AZ-C', 'group_id': 'subnet'})
            raw['nodes'].append({'id':'storage','asset_id':'aws4.s3','label':'Amazon Simple Storage Service','description':'S3保管'})
            source.write_text(json.dumps(raw, ensure_ascii=False))
            result, code = run(source, base/'out',
                               Path(os.environ.get('AWS_DRAWIO_BINARY', '/Applications/draw.io.app/Contents/MacOS/draw.io')),
                               Path(os.environ['AWS_DRAWIO_PROFILE']), Path(os.environ['AWS_NATIVE_DRAWIO_RUNTIME']))
            self.assertEqual(code, 0, result.get('errors'))
            self.assertTrue(result['production_eligible'])
            self.assertEqual([w['code'] for w in result['warnings'] if w['code'].startswith('W_AZ_')],
                             ['W_AZ_LABEL_REDUNDANT', 'W_AZ_LABEL_MISMATCH'])
            saved = json.loads((base/'out/architecture.json').read_text())
            self.assertEqual(saved['nodes'], normalize(raw, manifest())['nodes'])
            self.assertEqual(sum(e['asset_id']=='aws4.ec2' and e.get('kind')!='note' for e in saved['glossary']),1)
            self.assertTrue(any(e['asset_id']=='aws4.ecs' for e in saved['glossary']))
            self.assertFalse(any(e['asset_id']=='aws4.s3' for e in saved['glossary']))
            positioned=json.loads((base/'out/layout.json').read_text())['glossary']
            definition=next(g for g in positioned if g['text']=='Amazon Elastic Compute Cloud (Amazon EC2)')
            note=next(g for g in positioned if g['text']=='EC2運用：夜間停止')
            self.assertLess(definition['y']+definition['h'],note['y'])
            for theme in ('light', 'dark'):
                self.assertEqual(result['themes'][theme]['images'], 0)
                self.assertTrue((base/('out/qa/'+theme+'.browser.png')).is_file())
                self.assertIn('EC2アプリ・AZ-A', (base/('out/'+theme+'.drawio')).read_text())
                self.assertIn('ECSワーカー・AZ-C', (base/('out/'+theme+'.drawio')).read_text())
