import hashlib,json,sys,tempfile,unittest,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from lifecycle import unpack
from check_bundle import audit

class StagingTests(unittest.TestCase):
 def bundle(self,base):
  archive=base/'release.zip';data=b'---\nname: aws-architecture-drawio\ndescription: test\n---\n'
  definition=b'{"version":"0.6.0"}'
  record={'version':'0.6.0','files':{'SKILL.md':hashlib.sha256(data).hexdigest(),'references/version.json':hashlib.sha256(definition).hexdigest()}}
  with zipfile.ZipFile(archive,'w') as z:z.writestr('aws-architecture-drawio/references/version.json',definition);z.writestr('aws-architecture-drawio/SKILL.md',data);z.writestr('aws-architecture-drawio/references/release-manifest.json',json.dumps(record))
  checksum=base/'release.zip.sha256';checksum.write_text(hashlib.sha256(archive.read_bytes()).hexdigest()+'  release.zip\n');return archive,checksum
 def test_stage_is_new_and_audited(self):
  with tempfile.TemporaryDirectory() as d:
   b=Path(d);a,c=self.bundle(b);root,r=unpack(a,c,b/'stage');self.assertTrue((root/'SKILL.md').is_file());self.assertEqual(r['status'],'passed')
 def test_existing_stage_preserved(self):
  with tempfile.TemporaryDirectory() as d:
   b=Path(d);a,c=self.bundle(b);stage=b/'stage';stage.mkdir();keep=stage/'user-work';keep.write_text('keep')
   with self.assertRaises(ValueError):unpack(a,c,stage)
   self.assertEqual(keep.read_text(),'keep')
 def test_corruption_rejected_before_extraction(self):
  with tempfile.TemporaryDirectory() as d:
   b=Path(d);a,c=self.bundle(b);a.write_bytes(a.read_bytes()+b'bad')
   with self.assertRaises(ValueError):unpack(a,c,b/'stage')
   self.assertFalse((b/'stage').exists())
 def test_missing_checksum_does_not_extract(self):
  with tempfile.TemporaryDirectory() as d:
   b=Path(d);a,c=self.bundle(b)
   with self.assertRaises(ValueError):unpack(a,b/'missing',b/'stage')
   self.assertFalse((b/'stage').exists())
