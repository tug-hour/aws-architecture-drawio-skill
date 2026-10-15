"""Regressions for wrongly accepted service identities, breaks and definitions."""
import copy
import json
import sys
import unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from build_drawio import normalize, author
from catalog import manifest
from layout import layout
from schema import Failure
from service_labels import policy
from project import project_views
import xml.etree.ElementTree as ET

class ServiceLabelTests(unittest.TestCase):
    def setUp(self):
        self.m = manifest()
        self.a = {'schema_version':'1.0','nodes':[{'id':'n','asset_id':'aws4.cloudfront'}],'edges':[]}
    def rejected(self, a, code):
        with self.assertRaises(Failure) as ctx:
            normalize(a, self.m)
        self.assertEqual(ctx.exception.issue['code'], code)
    def test_wrong_service_and_unapproved_short_forms_rejected_in_both_modes(self):
        for mode in ('production','draft'):
            for label in ('Amazon S3','CloudFront','Amazon CloudF\nront','AWS CloudFront'):
                a=copy.deepcopy(self.a);a['mode']=mode;a['nodes'][0]['label']=label
                self.rejected(a,'E_SERVICE_NAME')
    def test_brand_and_line_limit(self):
        for label in ('Amazon\nCloudFront','Amazon\nCloud\nFront'):
            a=copy.deepcopy(self.a);a['nodes'][0]['label']=label
            self.rejected(a,'E_SERVICE_LABEL')
    def test_every_character_break_requires_a_word_boundary(self):
        name='Amazon Kinesis Data Streams'
        for i in range(1,len(name)):
            a=copy.deepcopy(self.a);a['nodes'][0]['asset_id']='aws4.kinesis_data_streams'
            if name[i]==' ':
                label=name[:i]+'\n'+name[i+1:]
            else:
                label=name[:i]+'\n'+name[i:]
            a['nodes'][0]['label']=label
            if name[i]==' ' and name[:i]!='Amazon':
                self.assertEqual(normalize(a,self.m)['nodes'][0]['label'],label)
            else:
                with self.assertRaises(Failure):normalize(a,self.m)
    def test_description_separate_from_two_line_service_name(self):
        self.a['nodes'][0].update(asset_id='aws4.kinesis_data_streams',label='Amazon Kinesis\nData Streams',description='日本語の受信データ')
        a=normalize(self.a,self.m);lay,_=layout(a,self.m)
        self.assertEqual(lay['nodes'][0]['label'],['Amazon Kinesis','Data Streams','日本語の受信データ'])
    def test_description_control_multiline_and_length_rejected(self):
        for value,code in [('a\nb','E_DESCRIPTION'),('x'*121,'E_DESCRIPTION'),('\x00','E_TEXT_UNSUPPORTED')]:
            a=copy.deepcopy(self.a);a['nodes'][0]['description']=value;self.rejected(a,code)
    def test_short_name_adds_full_definition(self):
        self.a['nodes'][0]['asset_id']='aws4.s3';a=normalize(self.a,self.m)
        self.assertEqual(a['glossary'],[{'asset_id':'aws4.s3','short_name':'Amazon S3','full_name':'Amazon Simple Storage Service'}])
        self.assertEqual(normalize(a,self.m),a)
    def test_ecs_in_fargate_description_adds_ecs_definition(self):
        self.a['nodes'][0].update(asset_id='aws4.fargate',description='ECS API')
        a=normalize(self.a,self.m)
        self.assertEqual(a['glossary'][0]['full_name'],'Amazon Elastic Container Service')
    def full_ec2(self):
        a=copy.deepcopy(self.a)
        a['nodes'][0].update(asset_id='aws4.ec2',label='Amazon Elastic\nCompute Cloud',description='EC2アプリ')
        return a
    def test_full_caption_defines_its_description_without_extra_glossary(self):
        raw=self.full_ec2();before=copy.deepcopy(raw)
        a=normalize(raw,self.m)
        self.assertEqual(a['glossary'],[])
        self.assertEqual(normalize(a,self.m),a)
        self.assertEqual(raw,before)
        lay,_=layout(a,self.m)
        self.assertFalse(lay.get('glossary'))
        for theme in ('light','dark'):
            doc=ET.fromstring(author(a,lay,self.m,theme))
            label=next(c for c in doc.iter('mxCell') if c.get('id')=='label.n')
            self.assertTrue(label.get('value').endswith('EC2アプリ'))
    def test_abbreviation_outside_defining_node_still_gets_glossary(self):
        for location in ('node','group','edge','note'):
            with self.subTest(location=location):
                a=self.full_ec2()
                a['nodes'].append({'id':'other','asset_id':'aws4.user','label':'利用者'})
                if location=='node':a['nodes'][1]['description']='EC2アプリへ接続'
                elif location=='group':a['groups']=[{'id':'az','type':'group.availability-zone','role':'containment','label':'EC2用 AZ-A'}]
                elif location=='edge':a['edges']=[{'id':'e','source':'other','target':'n','label':'EC2接続'}]
                else:a['glossary']=[{'asset_id':'aws4.ec2','kind':'note','short_name':'補足','full_name':'EC2アプリへ接続'}]
                entries=normalize(a,self.m)['glossary']
                self.assertEqual(sum(e['asset_id']=='aws4.ec2' and e.get('kind')!='note' for e in entries),1)
    def test_manual_definition_and_notes_are_preserved(self):
        a=self.full_ec2()
        a['glossary']=[{'asset_id':'aws4.ec2','short_name':'Amazon EC2','full_name':'Amazon Elastic Compute Cloud'},
                       {'asset_id':'aws4.ec2','kind':'note','short_name':'補足','full_name':'用途説明'}]
        self.assertEqual(normalize(a,self.m)['glossary'],a['glossary'])
    def test_review_regression_note_heading_keeps_definition_before_first_abbreviation(self):
        for heading,body in [('EC2運用','夜間停止'),('補足','EC2を夜間停止'),('EC2運用','EC2を夜間停止')]:
            with self.subTest(heading=heading,body=body):
                raw=self.full_ec2()
                note={'asset_id':'aws4.ec2','kind':'note','short_name':heading,'full_name':body}
                raw['glossary']=[note];before=copy.deepcopy(raw)
                a=normalize(raw,self.m)
                self.assertEqual(raw,before)
                self.assertEqual(normalize(a,self.m),a)
                self.assertEqual(len(a['glossary']),2)
                self.assertEqual(a['glossary'][0]['full_name'],'Amazon Elastic Compute Cloud')
                self.assertEqual(a['glossary'][1],note)
                lay,_=layout(a,self.m)
                self.assertLess(lay['glossary'][0]['y']+lay['glossary'][0]['h'],lay['glossary'][1]['y'])
    def test_unrelated_full_name_does_not_define_another_services_abbreviation(self):
        a=self.full_ec2();a['nodes'][0]['description']='ECSアプリ'
        self.assertEqual(normalize(a,self.m)['glossary'][0]['asset_id'],'aws4.ecs')
    def test_each_view_has_its_own_definition_scope(self):
        a=self.full_ec2()
        b=copy.deepcopy(a);b['nodes'][0]['label']='Amazon EC2'
        self.assertEqual(normalize(a,self.m)['glossary'],[])
        self.assertEqual(normalize(b,self.m)['glossary'][0]['asset_id'],'aws4.ec2')
    def test_incorrect_definition_rejected(self):
        self.a['glossary']=[{'asset_id':'aws4.s3','short_name':'Amazon S3','full_name':'Amazon Simple Queue Service'}]
        self.rejected(self.a,'E_GLOSSARY_NAME')
    def test_false_note_cannot_replace_definition(self):
        self.a['glossary']=[{'asset_id':'aws4.s3','short_name':'S3','full_name':'incorrect','kind':'note'}]
        self.rejected(self.a,'E_GLOSSARY_NAME')
    def test_same_short_name_for_different_service_rejected(self):
        self.a['glossary']=[{'asset_id':'aws4.s3','short_name':'Amazon S3','full_name':'Amazon Simple Storage Service'},{'asset_id':'aws4.sqs','short_name':'Amazon S3','full_name':'Amazon Simple Queue Service'}]
        self.rejected(self.a,'E_GLOSSARY')
    def test_general_label_remains_customizable(self):
        self.a['nodes'][0].update(asset_id='aws4.user',label='利用者\n担当窓口');normalize(self.a,self.m)
    def test_full_names_and_all_supported_service_defaults_pass(self):
        for ident,rules in policy()['services'].items():
            for name in rules['allowed_names']:
                a=copy.deepcopy(self.a);a['nodes'][0].update(asset_id=ident,label=name);normalize(a,self.m)
    def test_glossary_precedes_the_diagram_in_both_themes(self):
        self.a['nodes'][0]['asset_id']='aws4.sqs';a=normalize(self.a,self.m);lay,_=layout(a,self.m)
        self.assertLess(max(g['y']+g['h'] for g in lay['glossary']),min(n['y'] for n in lay['nodes']))
        for theme in ('light','dark'):
            doc=ET.fromstring(author(a,lay,self.m,theme));g=next(c for c in doc.iter('mxCell') if c.get('id')=='glossary.0')
            self.assertEqual(g.get('value'),'Amazon Simple Queue Service (Amazon SQS)')
    def test_all_examples_and_project_views_use_name_contract(self):
        for path in (ROOT/'examples').rglob('*.json'):
            with self.subTest(path=str(path)):
                a=json.loads(path.read_text())
                if 'project_version' in a:project_views(a)
                else:normalize(a,self.m)

    def test_cloud_logo_negative_space_uses_source_palette(self):
        self.a['nodes'][0]['group_id']='cloud'
        self.a['groups']=[{'id':'cloud','type':'group.aws-cloud','role':'containment'}]
        a=normalize(self.a,self.m);lay,_=layout(a,self.m)
        for theme,color in [('light','#FFFFFF'),('dark','#232F3E')]:
            doc=ET.fromstring(author(a,lay,self.m,theme));cell=next(c for c in doc.iter('mxCell') if c.get('id')=='header.base.cloud')
            self.assertIn('fillColor='+color+';',cell.get('style'))
