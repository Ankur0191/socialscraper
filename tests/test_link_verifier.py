import unittest
from unittest.mock import Mock
from socialscraper.link_verifier import validate_social_url, check_link
from socialscraper.x_api import normalize_handle, post_url

class LinkVerifierTests(unittest.TestCase):
    def test_accepts_x_profile(self):
        self.assertTrue(validate_social_url("x","https://x.com/SGS_SA")[0])
    def test_rejects_http(self):
        self.assertFalse(validate_social_url("x","http://x.com/SGS_SA")[0])
    def test_rejects_unexpected_host(self):
        self.assertFalse(validate_social_url("x","https://x.example.net/SGS_SA")[0])
    def test_rejects_root_as_profile(self):
        self.assertFalse(validate_social_url("linkedin","https://www.linkedin.com/")[0])
    def test_http_403_is_access_limited(self):
        session=Mock()
        session.get.return_value=Mock(status_code=403,url="https://x.com/SGS_SA")
        self.assertEqual(check_link("SGS","x","https://x.com/SGS_SA",session=session).status,"access_limited")
    def test_404_is_not_found(self):
        session=Mock()
        session.get.return_value=Mock(status_code=404,url="https://x.com/SGS_SA")
        self.assertEqual(check_link("SGS","x","https://x.com/SGS_SA",session=session).status,"not_found")
    def test_handle_normalization(self):
        self.assertEqual(normalize_handle("https://x.com/SGS_SA"),"SGS_SA")
        self.assertEqual(normalize_handle("@tuvcom_presse"),"tuvcom_presse")
    def test_invalid_handle(self):
        with self.assertRaises(ValueError): normalize_handle("TÜV Rheinland")
    def test_status_url(self):
        self.assertEqual(post_url("123","SGS_SA"),"https://x.com/SGS_SA/status/123")

if __name__=="__main__":
    unittest.main()
