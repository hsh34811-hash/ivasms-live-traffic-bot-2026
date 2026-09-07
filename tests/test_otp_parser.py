import unittest
from main import extract_otp, detect_service

class TestOtpExtraction(unittest.TestCase):
    def test_whatsapp_code(self):
        msg = "Your WhatsApp code is 482-910. Do not share it."
        otp = extract_otp(msg)
        self.assertEqual(otp, "482910")

    def test_telegram_code(self):
        msg = "Telegram code: 82914. You can also tap on this link to log in."
        otp = extract_otp(msg)
        self.assertEqual(otp, "82914")

    def test_arabic_otp(self):
        msg = "رمز تحقق الخاص بك هو: 938210 صالح لمدة 5 دقائق"
        otp = extract_otp(msg)
        self.assertEqual(otp, "938210")

    def test_tiktok_code(self):
        msg = "[TikTok] 748291 is your verification code"
        otp = extract_otp(msg)
        self.assertEqual(otp, "748291")

    def test_google_g_code(self):
        msg = "G-592813 is your Google verification code."
        otp = extract_otp(msg)
        self.assertEqual(otp, "592813")

    def test_no_code(self):
        msg = "Hello from support team, welcome to the platform."
        otp = extract_otp(msg)
        self.assertEqual(otp, "N/A")

class TestServiceDetection(unittest.TestCase):
    def test_detect_whatsapp(self):
        self.assertEqual(detect_service("Your WhatsApp code is 123456"), "#WP")

    def test_detect_telegram(self):
        self.assertEqual(detect_service("Telegram code: 45678"), "#TG")

    def test_detect_tiktok(self):
        self.assertEqual(detect_service("[TikTok] 882910 is your verification code"), "#TT")

    def test_detect_google(self):
        self.assertEqual(detect_service("Google verification code is 112233"), "#GG")

if __name__ == "__main__":
    unittest.main()
