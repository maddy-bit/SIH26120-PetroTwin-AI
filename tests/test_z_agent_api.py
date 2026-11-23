import unittest

from fastapi.testclient import TestClient

from ml_service import main


class TestAgentApiReadiness(unittest.TestCase):
    def test_status_is_safe_and_investigation_fails_closed_without_provider(self):
        previous_mode = main.config.auth_mode
        main.config.auth_mode = "disabled"
        well_id = "AGENT-API-READINESS-FIXTURE"
        if main.repository.get_well(well_id) is None:
            main.repository.seed_wells({well_id: {"name": "Agent API readiness fixture"}})
        try:
            client = TestClient(main.app)
            status = client.get("/api/v1/agent/status")
            self.assertEqual(status.status_code, 200)
            self.assertFalse(status.json()["enabled"])
            self.assertNotIn("api_key", status.json())
            response = client.post("/api/v1/agent/investigate", json={
                "well_id": well_id,
                "question": "Summarize current evidence.",
            })
            self.assertEqual(response.status_code, 503)
            self.assertIn("not configured", response.json()["detail"].lower())
        finally:
            main.config.auth_mode = previous_mode


if __name__ == "__main__":
    unittest.main()
