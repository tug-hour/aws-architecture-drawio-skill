"""Build and audit a new local release. No installation, downloads or source writes."""
import argparse
import hashlib
import json
import zipfile
from pathlib import Path

from check_bundle import audit
from version import parse_version,unique_fields
from verified_assets import check as check_verified_assets

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = 'references/release-manifest.json'
ROOT_DOCUMENTS = ('SKILL.md', 'LICENSE', 'README.md', 'THIRD_PARTY_NOTICES.md')


def release_files(root):
    if any((root / name).is_symlink() for name in ROOT_DOCUMENTS + ('scripts','tests','references','examples')):
        raise ValueError('Release source contains a symlink')
    files = {name: (root / name).read_bytes() for name in ROOT_DOCUMENTS}
    for folder, suffixes in (
        ('scripts', {'.py', '.cjs'}), ('tests', {'.py'}),
        ('references', {'.json', '.md', '.yml'}), ('examples', {'.json', '.py'}),
    ):
        for path in sorted((root / folder).rglob('*')):
            if path.is_symlink():
                raise ValueError('Release source contains a symlink: ' + str(path))
            if path.is_file() and path.suffix in suffixes and '__pycache__' not in path.parts:
                name = path.relative_to(root).as_posix()
                if name != MANIFEST:
                    files[name] = path.read_bytes()
    return files


def package(root, output):
    root = root.resolve()
    output = output.resolve()
    if output == root or root in output.parents:
        raise ValueError('Release output must be outside the skill source')
    if output.exists():
        raise ValueError('Refuse existing release output')
    files = release_files(root)
    release_version = parse_version(files['references/version.json'])
    if 'references/native-catalog.json' in files or 'references/verified-assets.json' in files:
        check_verified_assets(json.loads(files['references/native-catalog.json'],object_pairs_hook=unique_fields),
                              json.loads(files['references/verified-assets.json'],object_pairs_hook=unique_fields))
    record = {
        'schema_version': '1.0', 'version': release_version, 'algorithm': 'sha256',
        'files': {name: hashlib.sha256(data).hexdigest() for name, data in sorted(files.items())},
    }
    manifest_data = (json.dumps(record, ensure_ascii=False, indent=2) + '\n').encode('utf-8')
    output.mkdir(parents=True, exist_ok=False)
    archive = output / ('aws-architecture-drawio-' + release_version + '.zip')
    with zipfile.ZipFile(archive, 'x', zipfile.ZIP_DEFLATED) as bundle:
        for name, data in sorted({**files, MANIFEST: manifest_data}.items()):
            info = zipfile.ZipInfo('aws-architecture-drawio/' + name, (1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            bundle.writestr(info, data)
    checksum = archive.with_suffix('.zip.sha256')
    checksum.write_text(hashlib.sha256(archive.read_bytes()).hexdigest() + '  ' + archive.name + '\n', encoding='utf-8')
    (output / 'release-manifest.json').write_bytes(manifest_data)
    result, code = audit(archive, checksum)
    result.update(archive=str(archive), checksum=str(checksum), source_changed=False)
    (output / 'package-result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return result, code


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    try:
        result, code = package(ROOT, args.output)
    except (OSError, ValueError, KeyError, TypeError, zipfile.BadZipFile) as error:
        result, code = {'status': 'failed', 'code': 'E_PACKAGE_RELEASE', 'message': str(error)}, 2
    print(json.dumps(result, ensure_ascii=False))
    raise SystemExit(code)
