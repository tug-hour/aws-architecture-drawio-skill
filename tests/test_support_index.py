"""Catalog-derived support metadata must agree even when archive hashes are valid."""
import hashlib
import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
from verified_assets import derived_fields, check
from check_bundle import audit
from package_release import package


class SupportIndexTests(unittest.TestCase):
    def catalog(self):
        return {'tested_drawio_version':'32.4.1','assets':{'aws4.s3':{'support_status':'verified'},'aws4.other':{'support_status':'unverified'}},'groups':{'group.vpc':{}}}

    def test_installed_index_matches_the_catalog(self):
        check(json.loads((ROOT/'references/native-catalog.json').read_text()),json.loads((ROOT/'references/verified-assets.json').read_text()))

    def test_catalog_owns_assets_groups_and_drawio_version(self):
        catalog=self.catalog();index=derived_fields(catalog)
        self.assertEqual(index['assets'],['aws4.s3'])
        for key,bad in [('assets',[]),('assets',['aws4.s3','aws4.s3']),('group_types',[]),('drawio_version','0.0.0')]:
            with self.subTest(key=key,value=bad), self.assertRaises(ValueError):check(catalog,dict(index,**{key:bad}))

    def test_packager_refuses_stale_index_before_creating_output(self):
        with tempfile.TemporaryDirectory() as d:
            base=Path(d);root=base/'skill';refs=root/'references';refs.mkdir(parents=True)
            (root/'SKILL.md').write_text('fixture');(refs/'version.json').write_text('{"version":"1.2.3"}')
            (refs/'native-catalog.json').write_text(json.dumps(self.catalog()))
            (refs/'verified-assets.json').write_text(json.dumps(dict(derived_fields(self.catalog()),assets=[])))
            with self.assertRaises(ValueError):package(root,base/'out')
            self.assertFalse((base/'out').exists())

    def test_recomputed_archive_hashes_cannot_hide_stale_support_index(self):
        for field,value in [('assets',[]),('group_types',[]),('drawio_version','0.0.0')]:
            with self.subTest(field=field), tempfile.TemporaryDirectory() as d:
                base=Path(d);catalog=self.catalog();index=dict(derived_fields(catalog),**{field:value})
                files={'SKILL.md':b'fixture','references/version.json':b'{"version":"1.2.3"}',
                       'references/native-catalog.json':json.dumps(catalog).encode(),'references/verified-assets.json':json.dumps(index).encode()}
                record={'version':'1.2.3','files':{n:hashlib.sha256(v).hexdigest() for n,v in files.items()}}
                files['references/release-manifest.json']=json.dumps(record).encode()
                archive=base/'fixture.zip';checksum=base/'fixture.zip.sha256'
                with zipfile.ZipFile(archive,'w') as z:
                    for n,v in files.items():z.writestr('aws-architecture-drawio/'+n,v)
                checksum.write_text(hashlib.sha256(archive.read_bytes()).hexdigest()+'  fixture.zip\n')
                for legacy in (False,True):
                    result,code=audit(archive,checksum,allow_legacy=legacy)
                    self.assertEqual(code,2);self.assertEqual(result['code'],'E_BUNDLE_VERIFIED_ASSETS')
