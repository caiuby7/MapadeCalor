import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

import backend.main as main


class ApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(main.app)

    def test_health(self) -> None:
        response = self.client.get("/api/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")

    def test_demo_heatmap_contract(self) -> None:
        with (
            patch.object(main, "DEMO_MODE", True),
            patch.dict("os.environ", {"OPENAI_API_KEY": ""}),
        ):
            response = self.client.get("/api/heatmap-data", params={"query": "teste"})

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(len(body), len(main.DEMO_COMMENTS))
        self.assertEqual(
            {
                "lat",
                "lng",
                "intensity",
                "sentiment",
                "sentiment_score",
                "location",
                "text",
            },
            set(body[0]),
        )

    def test_reports_missing_youtube_key(self) -> None:
        with (
            patch.object(main, "DEMO_MODE", False),
            patch.dict("os.environ", {"YOUTUBE_API_KEY": ""}),
        ):
            response = self.client.get("/api/heatmap-data", params={"query": "teste"})

        self.assertEqual(response.status_code, 503)
        self.assertIn("YOUTUBE_API_KEY", response.json()["detail"])


if __name__ == "__main__":
    unittest.main()
