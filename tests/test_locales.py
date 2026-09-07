import unittest
from locales import TRANSLATIONS, SUPPORTED_LANGUAGES, get_text

class TestLocales(unittest.TestCase):
    def test_supported_languages_exist(self):
        expected_languages = {"ar", "en", "ur", "ru", "tr", "fa", "hi"}
        self.assertTrue(expected_languages.issubset(set(SUPPORTED_LANGUAGES.keys())))

    def test_key_consistency_across_languages(self):
        required_keys = [
            "welcome_banner", "number_details", "private_otp_msg",
            "btn_change_num", "btn_back", "btn_language", "choose_language",
            "language_changed", "all_numbers_busy", "number_assigned_alert",
            "admin_title", "admin_btn_back", "cookies_panel_title"
        ]
        for lang_code in SUPPORTED_LANGUAGES.keys():
            self.assertIn(lang_code, TRANSLATIONS, f"Language {lang_code} missing from TRANSLATIONS")
            for key in required_keys:
                self.assertIn(key, TRANSLATIONS[lang_code], f"Key {key} missing from language {lang_code}")

    def test_get_text_formatting(self):
        formatted = get_text("number_details", "en", number="123456789", country="United States", flag="🇺🇸", short="US", combo=1, service="WhatsApp")
        self.assertIn("+123456789", formatted)
        self.assertIn("United States", formatted)
        self.assertIn("WhatsApp", formatted)

if __name__ == "__main__":
    unittest.main()
