"""Independent lexical expectations; no producer/geometry oracle dependency."""
import importlib.util
import tempfile
import unittest
from pathlib import Path

from target_area_route_reconstruction.strict_json import loads_json, load_json, StrictJSONError
from target_area_route_reconstruction._m2d_common import strict_load, BundleJSONError


class StrictJSONAdmissionTests(unittest.TestCase):
    def test_invalid_lexemes_have_explicit_shared_error(self):
        cases = (
            ('{"x":1,"x":2}', "M2D_DUPLICATE_JSON_MEMBER"),
            ('{"a":{"x":1,"x":1}}', "M2D_DUPLICATE_JSON_MEMBER"),
            ('{"a":1,"\\u0061":2}', "M2D_DUPLICATE_JSON_MEMBER"),
            ('NaN', "M2D_NONFINITE_JSON"), ('Infinity', "M2D_NONFINITE_JSON"),
            ('-Infinity', "M2D_NONFINITE_JSON"), ('1e9999', "M2D_NONFINITE_JSON"),
            ('1e-400', "M2D_JSON_NUMBER_UNREPRESENTABLE"),
            ('-1e-400', "M2D_JSON_NUMBER_UNREPRESENTABLE"),
            ('1e-999999999999999999999999999', "M2D_BUNDLE_MALFORMED"),
            ('"\\ud800"', "M2D_BUNDLE_MALFORMED"),
            ('{"\\udfff":1}', "M2D_BUNDLE_MALFORMED"),
            ('"\ud800"', "M2D_BUNDLE_MALFORMED"),
            ('[01]', "M2D_BUNDLE_MALFORMED"), ('[1.]', "M2D_BUNDLE_MALFORMED"),
            ('[+1]', "M2D_BUNDLE_MALFORMED"), ('{"x":}', "M2D_BUNDLE_MALFORMED"),
            ('{} {}', "M2D_BUNDLE_MALFORMED"), ('\ufeff{}', "M2D_BUNDLE_MALFORMED"),
        )
        self.assertIs(BundleJSONError, StrictJSONError)
        for text, code in cases:
            for parser in (loads_json, strict_load):
                with self.subTest(text=repr(text), parser=parser.__name__), self.assertRaises(StrictJSONError) as raised:
                    parser(text)
                self.assertEqual(raised.exception.code, code)
            # Surrogates cannot be encoded as valid raw UTF-8 in the first place.
            if any(0xd800 <= ord(c) <= 0xdfff for c in text):
                continue
            with tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "input.json"
                path.write_bytes(text.encode("utf-8"))
                with self.assertRaises(StrictJSONError) as raised:
                    load_json(path)
                self.assertEqual(raised.exception.code, code)

    def test_raw_utf8_and_extreme_nesting_fail_closed(self):
        for raw in (b'"\xff"', b'"\xed\xa0\x80"', b'\xef\xbb\xbf{}', b'['*3000+b']'*3000):
            with self.subTest(raw=raw[:20]), self.assertRaises(StrictJSONError) as raised:
                loads_json(raw)
            self.assertEqual(raised.exception.code, "M2D_BUNDLE_MALFORMED")

    def test_declared_legal_values_keep_exact_existing_representation(self):
        cases = (
            ('{"x":0,"y":0.0,"z":-0.0}', {"x":0,"y":0.0,"z":-0.0}),
            ('[5e-324,1.7976931348623157e308]', [5e-324,1.7976931348623157e308]),
            ('[0e-9999,-0e9999]', [0.0,-0.0]),
            ('{"x":"\\ud83d\\ude00","y":"中文"}', {"x":"😀","y":"中文"}),
            ('[true,false,null,12345678901234567890]', [True,False,None,12345678901234567890]),
        )
        for raw, expected in cases:
            with self.subTest(raw=raw):
                self.assertEqual(loads_json(raw.encode()), expected)
                self.assertEqual(strict_load(raw), expected)
        self.assertIs(type(loads_json('0')), int)
        self.assertIs(type(loads_json('0.0')), float)
        import math
        self.assertEqual(math.copysign(1, loads_json('-0.0')), -1)

    def test_fixture_adapter_is_same_admission_policy(self):
        root = Path(__file__).resolve().parent
        candidates = (root.parent / "scripts/strict_json.py", root / "scripts/strict_json.py")
        path = next((p for p in candidates if p.exists()), candidates[0])
        if not path.exists():
            self.skipTest("fixture adapter not shipped inside runtime wheel")
        spec = importlib.util.spec_from_file_location("fixture_strict_json", path)
        adapter = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(adapter)
        self.assertIs(adapter.load_json, load_json)


if __name__ == "__main__":
    unittest.main()
