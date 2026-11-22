"""Protocol and safety tests for the read-only PETRO-TWIN MCP server."""
import asyncio
import os
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

from mcp_server import server as mcp_module
from ml_service.persistence import AnalysisRepository


class PetroTwinMCPTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.database = Path(self.tempdir.name) / "mcp-test.sqlite3"
        self.repository = AnalysisRepository(f"sqlite:///{self.database}")
        self.repository.initialize()
        self.repository.create_well("TEST-WELL-01", {"name": "Test well", "status": "CONFIGURED"})
        self.old_repository = mcp_module.repository
        self.old_mode = mcp_module.config.data_mode
        mcp_module.repository = self.repository
        mcp_module.config.data_mode = "field"

    def tearDown(self):
        mcp_module.repository = self.old_repository
        mcp_module.config.data_mode = self.old_mode
        self.tempdir.cleanup()

    def test_list_wells_hides_synthetic_profiles_in_field_mode(self):
        self.repository.create_well("BW-DEMO-999", {"name": "Demo well"})
        result = mcp_module.list_wells()
        ids = [well["well_id"] for well in result["wells"]]
        self.assertEqual(ids, ["TEST-WELL-01"])
        self.assertEqual(result["data_mode"], "field")

    def test_measurement_tool_returns_traceable_records(self):
        measured_at = datetime.now(timezone.utc).isoformat()
        self.repository.ingest_measurements(
            [{
                "well_id": "TEST-WELL-01", "measured_at": measured_at,
                "variable": "temperature_c", "value": 82.5, "unit": "degC",
                "quality_status": "VALID", "provenance": {"source_row": 1},
            }],
            source_id="test-source", source_type="TEST", rejected=[],
        )
        result = mcp_module.get_measurements("TEST-WELL-01", days=1)
        self.assertEqual(result["count"], 1)
        record = result["records"][0]
        self.assertEqual(record["unit"], "degC")
        self.assertEqual(record["quality_status"], "VALID")
        self.assertTrue(record["measurement_id"])
        self.assertEqual(record["provenance"]["source_row"], 1)

    def test_unknown_and_demo_wells_are_rejected_in_field_mode(self):
        with self.assertRaisesRegex(ValueError, "Unknown well_id"):
            mcp_module.get_well_configuration("MISSING-WELL")
        self.repository.create_well("BW-DEMO-888", {"name": "Demo well"})
        with self.assertRaisesRegex(ValueError, "Synthetic development"):
            mcp_module.get_measurements("BW-DEMO-888")

    def test_protocol_registers_read_only_tools_resource_and_prompt(self):
        async def inspect_protocol():
            tools = await mcp_module.server.list_tools()
            self.assertEqual(len(tools), 8)
            self.assertTrue(all(tool.annotations.read_only_hint for tool in tools))
            self.assertTrue(all(tool.annotations.destructive_hint is False for tool in tools))
            resources = await mcp_module.server.list_resources()
            self.assertIn("petrotwin://domain/overview", [str(item.uri) for item in resources])
            prompts = await mcp_module.server.list_prompts()
            self.assertIn("investigate_well_evidence", [item.name for item in prompts])
            response = await mcp_module.server.call_tool("list_wells", {})
            self.assertFalse(response.is_error)
        asyncio.run(inspect_protocol())

    def test_stdio_transport_handshake_tools_resource_and_prompt(self):
        async def exercise_stdio():
            env = {**os.environ, "DATABASE_URL": f"sqlite:///{self.database}", "PETROTWIN_DATA_MODE": "field"}
            params = StdioServerParameters(
                command=sys.executable,
                args=["-m", "mcp_server.server"],
                cwd=str(Path(__file__).resolve().parents[1]),
                env=env,
            )
            async with stdio_client(params) as (read_stream, write_stream):
                async with ClientSession(read_stream, write_stream) as session:
                    await session.initialize()
                    tools = await session.list_tools()
                    names = {tool.name for tool in tools.tools}
                    self.assertIn("get_measurements", names)
                    self.assertIn("list_css_cycles", names)
                    call = await session.call_tool("list_wells", {})
                    self.assertFalse(call.is_error)
                    resource = await session.read_resource("petrotwin://domain/overview")
                    self.assertTrue(resource.contents)
                    prompt = await session.get_prompt("investigate_well_evidence", {"well_id": "TEST-WELL-01"})
                    self.assertTrue(prompt.messages)
        asyncio.run(exercise_stdio())


if __name__ == "__main__":
    unittest.main()
