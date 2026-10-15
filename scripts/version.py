"""Read the one authoritative skill release version; never cache or infer it."""
import json
import re
from pathlib import Path

VERSION_PATH = Path(__file__).resolve().parents[1] / 'references/version.json'


class VersionError(ValueError):
    pass


def unique_fields(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise VersionError('Duplicate release metadata field: ' + key)
        result[key] = value
    return result


def parse_version(data):
    try:
        value = json.loads(data, object_pairs_hook=unique_fields)
    except (ValueError, TypeError, UnicodeError) as error:
        raise VersionError('Invalid release version JSON') from error
    if not isinstance(value, dict) or set(value) != {'version'}:
        raise VersionError('Release metadata requires only the version field')
    version = value['version']
    if not isinstance(version, str) or not re.fullmatch(r'(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)', version):
        raise VersionError('Release version must be a stable major.minor.patch number')
    return version


def get_version():
    try:
        return parse_version(VERSION_PATH.read_bytes())
    except OSError as error:
        raise VersionError('Cannot read release metadata: ' + str(VERSION_PATH)) from error
