import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "qupbig"))

import qupbig


class QupBigTests(unittest.TestCase):
    def test_build_validates(self):
        data = qupbig.build_blueprint()
        qupbig.validate(data)

    def test_round_trip_validates(self):
        data = qupbig.build_blueprint()
        encoded = qupbig.bp.encode(data)
        decoded = qupbig.bp.decode(encoded)
        self.assertEqual(decoded, data)
        qupbig.validate(decoded)

    def test_expected_integrated_entity_count(self):
        data = qupbig.build_blueprint()
        self.assertEqual(len(data["blueprint"]["entities"]), 109)


if __name__ == "__main__":
    unittest.main()
