import unittest
from unittest.mock import Mock
from socialscraper.link_verifier import validate_social_url, check_link

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
        response=Mock(status_code=403,url="https://x.com/SGS_SA")
        session.get.return_value=response
        result=check_link("SGS","x","https://x.com/SGS_SA",session=session)
        self.assertEqual(result.status,"access_limited")
    def test_404_is_not_found(self):
        session=Mock()
        response=Mock(status_code=404,url="https://x.com/SGS_SA")
        session.get.return_value=response
        result=check_link("SGS","x","https://x.com/SGS_SA",session=session)
        self.assertEqual(result.status,"not_found")
if __name__=="__main__": unittest.main()
