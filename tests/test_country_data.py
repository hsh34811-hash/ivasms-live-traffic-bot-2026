import unittest
from country_data import COUNTRY_CODES, get_country_details_smart, get_app_badge, get_service_display

class TestCountryData(unittest.TestCase):
    def test_known_country_code(self):
        self.assertIn("1", COUNTRY_CODES)
        name, flag, short = COUNTRY_CODES["1"]
        self.assertEqual(short, "US")
        self.assertEqual(flag, "🇺🇸")

    def test_smart_details_by_dial_code(self):
        code, name, flag, short = get_country_details_smart("201001234567")
        self.assertEqual(code, "20")
        self.assertEqual(name, "Egypt")
        self.assertEqual(flag, "🇪🇬")
        self.assertEqual(short, "EG")

    def test_smart_details_by_range_name(self):
        code, name, flag, short = get_country_details_smart("", range_name="Germany Live 100")
        self.assertEqual(code, "49")
        self.assertEqual(flag, "🇩🇪")

    def test_fallback_logic(self):
        code, name, flag, short = get_country_details_smart("991234567")
        self.assertEqual(code, "99")
        self.assertEqual(short, "UN")

    def test_app_badge(self):
        self.assertEqual(get_app_badge("whatsapp"), "[WS]")
        self.assertEqual(get_app_badge("telegram"), "[TG]")
        self.assertEqual(get_app_badge("all apps"), "")

if __name__ == "__main__":
    unittest.main()
