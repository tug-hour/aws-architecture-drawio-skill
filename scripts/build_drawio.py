"""Author one explicit JSON drawing with no legacy or rendering dependencies."""
import argparse
import json
from pathlib import Path

from drawing import generate
from input_common import Failure


def main():
    parser = argparse.ArgumentParser(description='JSON to editable draw.io')
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    try:
        result, code = generate(args.input, args.output)
    except Failure as error:
        result, code = {'status': 'failed', 'errors': [error.issue]}, error.exit_code
    except (OSError, ValueError, TypeError, KeyError) as error:
        result, code = {'status': 'failed', 'errors': [{'code': 'E_PROCESSING', 'message': str(error)}]}, 4
    print(json.dumps(result, ensure_ascii=False))
    return code


if __name__ == '__main__':
    raise SystemExit(main())
