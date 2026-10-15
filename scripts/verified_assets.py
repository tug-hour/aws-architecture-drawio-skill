"""Generate/check the derived support index; the native catalog owns support decisions."""
import argparse
import json
from pathlib import Path
from catalog import ROOT
from version import unique_fields


def derived_fields(catalog):
    if not isinstance(catalog, dict) or not isinstance(catalog.get('tested_drawio_version'), str):
        raise ValueError('Catalog requires tested_drawio_version')
    assets = catalog.get('assets'); groups = catalog.get('groups')
    if not isinstance(assets, dict) or not isinstance(groups, dict):
        raise ValueError('Catalog requires assets and groups')
    if not all(isinstance(v, dict) for v in assets.values()):
        raise ValueError('Invalid catalog asset')
    return {'drawio_version': catalog['tested_drawio_version'],
            'assets': sorted(k for k, v in assets.items() if v.get('support_status') == 'verified'),
            'group_types': sorted(groups)}


def check(catalog, index):
    if not isinstance(index, dict):
        raise ValueError('Verified asset index must be an object')
    for key, value in derived_fields(catalog).items():
        actual = index.get(key)
        if isinstance(value, list):
            if not isinstance(actual, list) or not all(isinstance(v, str) for v in actual):
                raise ValueError('Invalid verified asset index: ' + key)
            actual = sorted(actual)
        if actual != value:
            raise ValueError('Verified asset index differs from catalog: ' + key)


def read(path):
    return json.loads(path.read_text(), object_pairs_hook=unique_fields)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, help='Generate an index at a NEW path; otherwise check the installed index')
    args = parser.parse_args()
    try:
        catalog = read(ROOT / 'references/native-catalog.json')
        index = read(ROOT / 'references/verified-assets.json')
        if args.output:
            if not isinstance(index, dict): raise ValueError('Invalid index metadata')
            index.update(derived_fields(catalog))
            # Keep descriptive platform/scope metadata; never infer a broader validation claim.
            with args.output.open('x', encoding='utf-8') as stream:
                stream.write(json.dumps(index, ensure_ascii=False, indent=2) + '\n')
        check(catalog, index)
        print(json.dumps({'status': 'passed', 'assets': len(index['assets']), 'groups': len(index['group_types'])}))
    except (OSError, ValueError, TypeError, KeyError) as error:
        print(json.dumps({'status': 'failed', 'message': str(error)}))
        raise SystemExit(2)
