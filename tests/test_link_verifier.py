import unittest

from socialscraper.link_verifier import validate_social_url


class LinkVerifierTests(unittest.TestCase):
    def test_accepts_x_profile(self):
        self.assertTrue(validate_social_url("x", "https://x.com/SGS_SA")[0])

    def test_rejects_http(self):
        valid, _ = validate_social_url("x", "http://x.com/SGS_SA")
        self.assertFalse(valid)

    def test_rejects_unexpected_host(self):
        valid, _ = validate_social_url("x", "https://x.example.net/SGS_SA")
        self.assertFalse(valid)

    def test_rejects_root_as_profile(self):
        valid, _ = validate_social_url("linkedin", "https://www.linkedin.com/")
        self.assertFalse(valid)


if __name__ == "__main__":
    unittest.main()
