"""Read-only release archive integrity failures, without installing or extracting."""
import hashlib
import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from check_bundle import audit

class BundleTests(unittest.TestCase):
    def fixture(self,base,unsafe=False):
        archive=base/'release.zip';checksum=base/'release.zip.sha256';source=b'---\nname: aws-architecture-drawio\ndescription: Test\n---\n'
        definition=b'{"version":"0.3.0"}'
        manifest={'version':'0.3.0','files':{'SKILL.md':hashlib.sha256(source).hexdigest(),'references/version.json':hashlib.sha256(definition).hexdigest()}}
        with zipfile.ZipFile(archive,'w') as z:
            z.writestr('aws-architecture-drawio/references/version.json',definition);z.writestr('aws-architecture-drawio/SKILL.md',source);z.writestr('aws-architecture-drawio/references/release-manifest.json',json.dumps(manifest))
            if unsafe:z.writestr('aws-architecture-drawio/../../outside','bad')
        checksum.write_text(hashlib.sha256(archive.read_bytes()).hexdigest()+'  release.zip\n');return archive,checksum
    def test_valid_bundle_is_read_only(self):
        with tempfile.TemporaryDirectory() as d:
            base=Path(d);archive,checksum=self.fixture(base);before={p.name:p.read_bytes() for p in base.iterdir()};r,code=audit(archive,checksum)
            self.assertEqual(code,0,r);self.assertFalse(r['installed']);self.assertEqual(before,{p.name:p.read_bytes() for p in base.iterdir()})
    def test_changed_bundle_is_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            archive,checksum=self.fixture(Path(d));archive.write_bytes(archive.read_bytes()+b'changed');r,code=audit(archive,checksum);self.assertEqual(code,2);self.assertEqual(r['code'],'E_BUNDLE_HASH')
    def test_path_traversal_is_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            archive,checksum=self.fixture(Path(d),unsafe=True);r,code=audit(archive,checksum);self.assertEqual(code,2);self.assertEqual(r['code'],'E_BUNDLE_PATH')

if __name__=='__main__':unittest.main()
