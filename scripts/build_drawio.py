"""Generate explicit JSON drawings; load compatibility code only when requested."""
import argparse
import importlib
import json
from pathlib import Path

from drawing import generate
from input_common import Failure, load


def __getattr__(name):
    """Keep the existing Python API available to legacy callers."""
    if name.startswith('_'):
        raise AttributeError(name)
    return getattr(importlib.import_module('legacy_drawio'), name)


def main():
    parser = argparse.ArgumentParser(description='JSON to editable draw.io')
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    # Keep old invocations without making their setup part of normal authoring.
    parser.add_argument('--drawio', type=Path, default=Path('/Applications/draw.io.app/Contents/MacOS/draw.io'), help=argparse.SUPPRESS)
    parser.add_argument('--profile', type=Path, help=argparse.SUPPRESS)
    parser.add_argument('--runtime', type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args()
    try:
        source = load(args.input)
        if isinstance(source, dict) and 'format' in source:
            if args.profile or args.runtime:
                parser.error('drawio/1 authors only; open/export the generated file separately')
            result, code = generate(args.input, args.output)
        else:
            if args.profile is None:
                parser.error('Legacy schema_version input requires --profile; see legacy_drawio.py')
            from legacy_drawio import build
            result, code = build(args.input, args.output, args.drawio, args.profile, args.runtime)
    except Failure as error:
        result, code = {'status': 'failed', 'errors': [error.issue]}, error.exit_code
    except (OSError, ValueError, TypeError, KeyError) as error:
        result, code = {'status': 'failed', 'errors': [{'code': 'E_PROCESSING', 'message': str(error)}]}, 4
    print(json.dumps(result, ensure_ascii=False))
    return code


if __name__ == '__main__':
    raise SystemExit(main())
