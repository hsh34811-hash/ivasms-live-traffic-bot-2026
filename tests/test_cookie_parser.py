import unittest
from main import parse_cookies_input

class TestCookieParsing(unittest.TestCase):
    def test_json_cookie_array(self):
        raw_json = '[{"name": "session_id", "value": "xyz123", "domain": ".ivasms.com", "path": "/"}]'
        cookies = parse_cookies_input(raw_json)
        self.assertEqual(len(cookies), 1)
        self.assertEqual(cookies[0]["name"], "session_id")
        self.assertEqual(cookies[0]["value"], "xyz123")

    def test_json_key_value_pairs(self):
        raw_dict = '{"cf_clearance": "clearance123", "ivas_sms_session": "sess456"}'
        cookies = parse_cookies_input(raw_dict)
        self.assertEqual(len(cookies), 2)
        names = [c["name"] for c in cookies]
        self.assertIn("cf_clearance", names)
        self.assertIn("ivas_sms_session", names)

    def test_netscape_format(self):
        raw_netscape = (
            "# Netscape HTTP Cookie File\n"
            ".ivasms.com\tTRUE\t/\tFALSE\t1788636334\t_fbp\tfb.1.test\n"
            "www.ivasms.com\tFALSE\t/\tTRUE\t1788636334\tcf_clearance\tclearance_value\n"
        )
        cookies = parse_cookies_input(raw_netscape)
        self.assertEqual(len(cookies), 2)
        names = [c["name"] for c in cookies]
        self.assertIn("_fbp", names)
        self.assertIn("cf_clearance", names)

    def test_empty_input_raises_value_error(self):
        with self.assertRaises(ValueError):
            parse_cookies_input("")
        with self.assertRaises(ValueError):
            parse_cookies_input("   ")

if __name__ == "__main__":
    unittest.main()
