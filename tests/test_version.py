"""Release metadata parsing without legacy rendering or packaging dependencies."""
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import version
from version import VersionError, get_version, parse_version

class VersionTests(unittest.TestCase):
    def test_bad_metadata_is_rejected(self):
        for data in ('{', 'null', '[]', '{}', '{"version":3}', '{"version":"1.2"}',
                     '{"version":"01.2.3"}', '{"version":"1.2.3","extra":true}',
                     '{"version":"1.2.3","version":"4.5.6"}'):
            with self.subTest(data=data), self.assertRaises(VersionError):
                parse_version(data)

    def test_missing_and_changed_version_has_no_fallback_or_cache(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / 'version.json'
            with patch.object(version, 'VERSION_PATH', path):
                with self.assertRaises(VersionError): get_version()
                path.write_text('{"version":"8.7.6"}')
                self.assertEqual(get_version(), '8.7.6')
                path.write_text('{"version":"8.7.7"}')
                self.assertEqual(get_version(), '8.7.7')


if __name__ == "__main__":
    unittest.main()
