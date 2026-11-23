import asyncio
import tempfile
import unittest
from pathlib import Path

from agent.agent_runtime import AgentExecutionError, AgentRuntime
from ml_service.persistence import AnalysisRepository


class TestAgentRuntime(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.database_url = f"sqlite:///{Path(self.tempdir.name) / 'agent.sqlite3'}"
        self.repository = AnalysisRepository(self.database_url)
        self.repository.initialize()
        self.repository.create_well("FIELD-AGENT-001", {"name": "MCP agent fixture", "status": "CONFIGURED"})
        self.repository.ingest_measurements([{
            "well_id": "FIELD-AGENT-001",
            "measured_at": "2026-11-22T10:00:00+00:00",
            "variable": "temperature_c",
            "value": 81.5,
            "unit": "°C",
            "quality_status": "VALID",
            "provenance": {"source_file": "agent-fixture.csv", "source_row": 2},
        }], source_id="agent-fixture", source_type="TEST", rejected=[])

    def tearDown(self):
        self.tempdir.cleanup()

    def runtime(self, completion, max_tool_calls=8):
        return AgentRuntime(
            self.repository,
            database_url=self.database_url,
            data_mode="field",
            model="test-provider",
            max_tool_calls=max_tool_calls,
            completion=completion,
        )

    def test_real_stdio_mcp_evidence_is_supplied_and_run_is_persisted(self):
        observed = {}

        async def fake_completion(messages, tools):
            observed["messages"] = messages
            observed["tools"] = tools
            evidence_message = messages[-1]["content"]
            self.assertIn("FIELD-AGENT-001", evidence_message)
            self.assertIn("agent-fixture.csv", evidence_message)
            self.assertTrue(all(tool["function"]["name"] for tool in tools))
            return {"choices": [{"message": {
                "role": "assistant",
                "content": "Measured record found: 81.5 °C at 2026-11-22T10:00:00+00:00. "
                           "This single record does not establish model calibration or operating readiness."
            }}]}

        result = asyncio.run(self.runtime(fake_completion).investigate(
            "FIELD-AGENT-001", "Summarize available thermal evidence."
        ))
        self.assertEqual(result["status"], "COMPLETED")
        self.assertEqual(result["tool_calls"], 7)
        self.assertIn("get_data_quality", result["tools_used"])
        self.assertTrue(all(trace["read_only"] for trace in result["tool_trace"]))
        saved = self.repository.list_agent_runs("FIELD-AGENT-001")
        self.assertEqual(len(saved), 1)
        self.assertEqual(saved[0]["run_id"], result["run_id"])
        self.assertEqual(saved[0]["status"], "COMPLETED")
        self.assertEqual(len(saved[0]["tool_trace"]), 7)

    def test_agent_cannot_execute_a_tool_outside_the_read_only_allowlist(self):
        async def malicious_completion(messages, tools):
            return {"choices": [{
                "message": {
                    "role": "assistant",
                    "tool_calls": [{
                        "id": "unsafe-call",
                        "type": "function",
                        "function": {"name": "create_well", "arguments": "{}"},
                    }],
                }
            }]}

        with self.assertRaisesRegex(AgentExecutionError, "not in the approved read-only allowlist"):
            asyncio.run(self.runtime(malicious_completion).investigate(
                "FIELD-AGENT-001", "Try an unapproved operation."
            ))
        self.assertEqual(self.repository.list_agent_runs("FIELD-AGENT-001"), [])

    def test_unconfigured_agent_is_disabled(self):
        agent = AgentRuntime(
            self.repository,
            database_url=self.database_url,
            data_mode="field",
            base_url="",
            model="",
        )
        self.assertFalse(agent.enabled)
        self.assertEqual(agent.status()["provider_model"], "not-configured")


if __name__ == "__main__":
    unittest.main()
