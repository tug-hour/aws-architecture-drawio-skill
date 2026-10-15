"""Read-only checksum and archive audit; never extracts or installs a skill."""
import argparse
import hashlib
import json
import re
import stat
import zipfile
from pathlib import Path,PurePosixPath
from version import parse_version,VersionError,unique_fields
from verified_assets import check as check_verified_assets

def audit(archive,checksum,allow_legacy=False):
    try:
        line=checksum.read_text().strip()
        match=re.fullmatch(r'([a-fA-F0-9]{64})\s+\*?([^\n]+)',line)
        if not match or Path(match[2]).name!=archive.name:return {'status':'failed','code':'E_CHECKSUM_FORMAT'},2
        digest=hashlib.sha256(archive.read_bytes()).hexdigest()
        if digest.lower()!=match[1].lower():return {'status':'failed','code':'E_BUNDLE_HASH'},2
        with zipfile.ZipFile(archive) as bundle:
            entries=bundle.infolist();names=[e.filename for e in entries]
            if len(names)!=len(set(names)) or len(names)>1000 or sum(e.file_size for e in entries)>20*1024*1024:return {'status':'failed','code':'E_BUNDLE_LIMIT'},2
            for e in entries:
                path=PurePosixPath(e.filename);mode=e.external_attr>>16
                if path.is_absolute() or '..' in path.parts or '\\' in e.filename or not path.parts or path.parts[0]!='aws-architecture-drawio' or stat.S_ISLNK(mode):return {'status':'failed','code':'E_BUNDLE_PATH'},2
            if bundle.testzip() is not None:return {'status':'failed','code':'E_BUNDLE_CRC'},2
            if 'aws-architecture-drawio/SKILL.md' not in names:return {'status':'failed','code':'E_BUNDLE_SKILL'},2
            manifest_name='aws-architecture-drawio/references/release-manifest.json'
            version=None;warnings=[]
            if manifest_name in names:
                try:value=json.loads(bundle.read(manifest_name),object_pairs_hook=unique_fields)
                except (ValueError,TypeError) as error:return {'status':'failed','code':'E_BUNDLE_MANIFEST','message':str(error)},2
                if not isinstance(value,dict) or not isinstance(value.get('version'),str) or not isinstance(value.get('files'),dict):return {'status':'failed','code':'E_BUNDLE_MANIFEST'},2
                version=value['version'];files=value['files']
                if not all(isinstance(n,str) and isinstance(h,str) for n,h in files.items()):return {'status':'failed','code':'E_BUNDLE_MANIFEST'},2
                actual={n for n in names if not n.endswith('/') and n!=manifest_name}
                expected={'aws-architecture-drawio/'+n for n in files}
                if actual!=expected:return {'status':'failed','code':'E_BUNDLE_FILE_SET'},2
                for name,sha in files.items():
                    if hashlib.sha256(bundle.read('aws-architecture-drawio/'+name)).hexdigest()!=sha:return {'status':'failed','code':'E_BUNDLE_FILE_HASH'},2
            else:
                if not allow_legacy:return {'status':'failed','code':'E_BUNDLE_MANIFEST_REQUIRED'},2
                warnings.append('Legacy bundle: external checksum/CRC verified; no internal release manifest')
            version_name='aws-architecture-drawio/references/version.json'
            if version_name not in names:
                if not allow_legacy:return {'status':'failed','code':'E_BUNDLE_VERSION_REQUIRED'},2
                warnings.append('Legacy bundle: no canonical release version; version consistency not verified')
            else:
                if manifest_name not in names:return {'status':'failed','code':'E_BUNDLE_MANIFEST_REQUIRED'},2
                try:canonical_version=parse_version(bundle.read(version_name))
                except VersionError as error:return {'status':'failed','code':'E_BUNDLE_VERSION_METADATA','message':str(error)},2
                if version!=canonical_version:return {'status':'failed','code':'E_BUNDLE_VERSION_MISMATCH','expected':canonical_version,'actual':version},2
                for filename,field in (('native-catalog.json','candidate_version'),('verified-assets.json','candidate_version'),('provenance.json','candidate_version'),('service-names.json','version')):
                    ref='aws-architecture-drawio/references/'+filename
                    if ref in names and field in json.loads(bundle.read(ref)):
                        return {'status':'failed','code':'E_BUNDLE_VERSION_DUPLICATE','file':filename,'field':field},2
                catalog_name='aws-architecture-drawio/references/native-catalog.json'
                index_name='aws-architecture-drawio/references/verified-assets.json'
                if catalog_name in names or index_name in names:
                    if catalog_name not in names or index_name not in names:return {'status':'failed','code':'E_BUNDLE_VERIFIED_ASSETS'},2
                    try:
                        catalog=json.loads(bundle.read(catalog_name),object_pairs_hook=unique_fields)
                        index=json.loads(bundle.read(index_name),object_pairs_hook=unique_fields)
                        check_verified_assets(catalog,index)
                    except (ValueError,TypeError,KeyError) as error:return {'status':'failed','code':'E_BUNDLE_VERIFIED_ASSETS','message':str(error)},2
        return {'status':'passed','sha256':digest,'version':version,'file_count':len(names),'warnings':warnings,'scope':'Integrity checks only; checksum must come from a trusted source','installed':False,'settings_changed':False},0
    except (OSError,ValueError,KeyError,TypeError,zipfile.BadZipFile) as error:return {'status':'failed','code':'E_BUNDLE_PROCESSING','message':str(error)},2

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--archive',type=Path,required=True);p.add_argument('--checksum',type=Path,required=True);p.add_argument('--allow-legacy',action='store_true',help='Audit old archives without canonical version metadata, with warnings');a=p.parse_args()
    result,code=audit(a.archive,a.checksum,a.allow_legacy);print(json.dumps(result,ensure_ascii=False));raise SystemExit(code)
