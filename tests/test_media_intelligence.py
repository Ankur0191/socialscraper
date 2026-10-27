import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from socialscraper.browser import _extract_caption, _extract_displayed_time
from socialscraper.media_intelligence import (
    _extract_response_text,
    _post_images,
    _public_image_url,
    analyze_media_report,
)


class EmptyLocator:
    def count(self):
        return 0


class FakeArticle:
    def locator(self, _selector):
        return EmptyLocator()


def valid_analysis():
    return {
        "media_summary": "An infographic with quarterly sales figures.",
        "visible_text": ["Q3 sales growth: 14.6%", "Organic growth: 5.7%"],
        "facts": [
            {
                "claim": "Q3 sales growth was 14.6%.",
                "evidence": "Text visible on the supplied image: '14.6%'",
                "evidence_type": "image",
                "confidence": "high",
            }
        ],
        "entities": [
            {
                "name": "SGS",
                "entity_type": "company",
                "evidence": "The post account is SGS.",
            }
        ],
        "strategic_signals": [
            {
                "signal": "The company is emphasizing quarterly growth.",
                "interpretation": "This may be intended to reinforce the company's performance narrative.",
                "evidence": "The infographic highlights sales growth.",
                "classification": "inference",
                "confidence": "medium",
            }
        ],
        "unknowns": ["The image does not establish the cause of the growth."],
    }


class MediaIntelligenceTests(unittest.TestCase):
    def test_only_allows_public_x_media_urls(self):
        self.assertEqual(
            _public_image_url("https://pbs.twimg.com/media/abc?format=webp"),
            "https://pbs.twimg.com/media/abc?format=webp",
        )
        self.assertIsNone(_public_image_url("http://pbs.twimg.com/media/abc"))
        self.assertIsNone(_public_image_url("https://example.com/image.png"))
        self.assertIsNone(_public_image_url("https://pbs.twimg.com/profile_images/abc"))

    def test_deduplicates_image_and_same_video_poster(self):
        post = {
            "media": [
                {"type": "image", "url": "https://pbs.twimg.com/media/abc?format=webp"},
                {"type": "video", "poster_url": "https://pbs.twimg.com/media/abc?format=webp"},
            ]
        }
        self.assertEqual(
            _post_images(post, 2),
            [{"url": "https://pbs.twimg.com/media/abc?format=webp", "kind": "image"}],
        )

    def test_extracts_response_text_from_responses_api_payload(self):
        payload = {
            "output": [
                {
                    "type": "message",
                    "content": [
                        {"type": "output_text", "text": '{"media_summary":"ok"}'}
                    ],
                }
            ]
        }
        self.assertEqual(_extract_response_text(payload), '{"media_summary":"ok"}')

    def test_falls_back_to_visible_card_for_caption_and_time(self):
        card_text = (
            "SGS\n@SGS_SA\nOct 26\n"
            "Our CEO reflects on quarterly sales growth.\n"
            "#SGSFinancialResults\n01:28\n1\n5\n289"
        )
        caption = _extract_caption(FakeArticle(), card_text)
        created_at, displayed_time = _extract_displayed_time(FakeArticle(), card_text)
        self.assertIn("Our CEO reflects on quarterly sales growth.", caption)
        self.assertNotIn("SGS\n@SGS_SA", caption)
        self.assertNotIn("289", caption)
        self.assertIsNone(created_at)
        self.assertEqual(displayed_time, "Oct 26")

    def test_analyzes_and_saves_json_with_mocked_api(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_path = root / "inspection.json"
            output_path = root / "analysis.json"
            input_path.write_text(
                json.dumps({
                    "status": "ok",
                    "url_final": "https://x.com/SGS_SA",
                    "visible_posts": [{
                        "url": "https://x.com/SGS_SA/status/123",
                        "caption": "Quarterly results",
                        "text": "Quarterly results",
                        "media": [{
                            "type": "image",
                            "url": "https://pbs.twimg.com/media/abc?format=webp",
                        }],
                        "external_links": [],
                    }],
                }),
                encoding="utf-8",
            )

            mock_session = Mock()
            mock_response = Mock()
            mock_response.ok = True
            mock_response.json.return_value = {
                "output": [{
                    "type": "message",
                    "content": [{
                        "type": "output_text",
                        "text": json.dumps(valid_analysis()),
                    }],
                }],
                "usage": {
                    "input_tokens": 600,
                    "output_tokens": 250,
                    "total_tokens": 850,
                },
            }
            mock_session.post.return_value = mock_response

            with patch.dict(os.environ, {"OPENAI_API_KEY": "test-only-key"}, clear=False):
                with patch("socialscraper.media_intelligence.load_dotenv"):
                    with patch("socialscraper.media_intelligence.requests.Session") as session_factory:
                        session_factory.return_value.__enter__.return_value = mock_session
                        result = analyze_media_report(
                            input_path=input_path,
                            output_path=output_path,
                            model="test-vision-model",
                            max_posts=5,
                            max_images_per_post=2,
                        )

            self.assertEqual(result["status"], "ok")
            self.assertEqual(result["posts_analyzed"], 1)
            saved = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertEqual(saved["results"][0]["analysis"]["facts"][0]["claim"],
                             "Q3 sales growth was 14.6%.")
            body = mock_session.post.call_args.kwargs["json"]
            self.assertFalse(body["store"])
            user_content = body["input"][1]["content"]
            self.assertTrue(any(item.get("type") == "input_image" for item in user_content))


if __name__ == "__main__":
    unittest.main()
