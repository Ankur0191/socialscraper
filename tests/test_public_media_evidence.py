import unittest

from socialscraper.browser import (
    _extract_caption,
    _extract_displayed_time,
    _looks_like_displayed_time,
)


class EmptyLocator:
    def count(self):
        return 0


class FakeArticle:
    def locator(self, _selector):
        return EmptyLocator()


class PublicMediaEvidenceTests(unittest.TestCase):
    def test_caption_fallback_extracts_visible_post_text(self):
        card_text = (
            "SGS\n@SGS_SA\nOct 26\n"
            "Our CEO reflects on quarterly sales growth.\n"
            "#SGSFinancialResults\n01:28\n1\n5\n289"
        )
        caption = _extract_caption(FakeArticle(), card_text)
        self.assertIn("Our CEO reflects on quarterly sales growth.", caption)
        self.assertNotIn("SGS\n@SGS_SA", caption)
        self.assertNotIn("289", caption)

    def test_displayed_time_recognizes_common_x_labels(self):
        self.assertTrue(_looks_like_displayed_time("4h"))
        self.assertTrue(_looks_like_displayed_time("Oct 26"))
        self.assertTrue(_looks_like_displayed_time("Jan 2, 2026"))
        self.assertFalse(_looks_like_displayed_time("Quarterly sales growth"))
        self.assertFalse(_looks_like_displayed_time(""))

    def test_displayed_time_fallback_from_visible_card(self):
        card_text = (
            "SGS\n@SGS_SA\nOct 26\n"
            "Our CEO reflects on quarterly sales growth.\n"
        )
        created_at, displayed_time = _extract_displayed_time(FakeArticle(), card_text)
        self.assertIsNone(created_at)
        self.assertEqual(displayed_time, "Oct 26")

    def test_relative_time_fallback_from_visible_card(self):
        card_text = "SGS\n@SGS_SA\n4h\nCybersecurity webinar announcement\n"
        created_at, displayed_time = _extract_displayed_time(FakeArticle(), card_text)
        self.assertIsNone(created_at)
        self.assertEqual(displayed_time, "4h")


if __name__ == "__main__":
    unittest.main()
