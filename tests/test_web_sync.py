import json
import unittest
from datetime import date
from unittest.mock import patch

from ashare_research.data.demo import DemoDataProvider
from ashare_research.web_sync import sync_research_run
from ashare_research.workflow import ResearchWorkflow


class FakeResponse:
    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None

    def read(self):
        return b'{"item":{"id":7}}'


class WebSyncTests(unittest.TestCase):
    def test_posts_complete_research_state(self):
        state = ResearchWorkflow(DemoDataProvider()).run("00700.HK", date(2026, 8, 18))
        with patch("ashare_research.web_sync._open", return_value=FakeResponse()) as mocked:
            result = sync_research_run(state, "http://localhost:3000/")
        self.assertEqual(result["item"]["id"], 7)
        request = mocked.call_args.args[0]
        payload = json.loads(request.data.decode("utf-8"))
        self.assertEqual(request.full_url, "http://localhost:3000/api/research")
        self.assertEqual(payload["security"]["exchange"], "HK")
        self.assertIn("company_quality", payload["synthesis"])
        self.assertIn("pricing_status", payload["valuation"])
        self.assertNotIn("decision", payload)


if __name__ == "__main__":
    unittest.main()
