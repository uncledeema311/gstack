import json
import unittest

from helper import PKG, WorkspaceCase


class Configuration(WorkspaceCase):
    def config_file(self):
        return self.ws.path / "config" / "cos.config.json"

    def test_fresh_config_is_valid_and_matches_the_shipped_example(self):
        result = self.ws.ok("config", "validate")
        self.assertTrue(result["valid"])
        example = json.loads((PKG / "payload" / "config" / "cos.config.example.json").read_text())
        self.assertEqual(self.ws.ok("config", "show")["config"], example)
        self.assertEqual(example["timezone"], "Australia/Melbourne")
        self.assertEqual(example["profile"]["language"], "en-AU")

    def test_invalid_changes_are_refused_and_the_file_is_untouched(self):
        before = self.config_file().read_text()
        for key, value in (("timezone", "Melbourne"), ("working_hours.start", "25:00"),
                           ("scheduling.slot_step_minutes", "0"), ("feedback.promotion_min_evidence", "1")):
            code, data = self.ws.cos("config", "set", key, value)
            self.assertEqual(code, 2, "%s=%s: %s" % (key, value, data))
        self.assertEqual(self.config_file().read_text(), before)

    def test_valid_changes_persist_and_missing_keys_fall_back_to_defaults(self):
        self.ws.ok("config", "set", "timezone", "Australia/Perth")
        self.assertEqual(self.ws.ok("now")["now"]["utc_offset"], "+08:00")
        self.assertIn("Time zone: Australia/Perth", (self.ws.path / "AGENTS.md").read_text())
        self.config_file().write_text(json.dumps({"timezone": "Australia/Brisbane"}))
        config = self.ws.ok("config", "show")["config"]
        self.assertEqual(config["timezone"], "Australia/Brisbane")
        self.assertEqual(config["working_hours"]["start"], "08:30")

    def test_hand_editing_send_permission_into_no_approval_is_caught(self):
        config = json.loads(self.config_file().read_text())
        config["permissions"]["no_approval"].append("email_send")
        self.config_file().write_text(json.dumps(config))
        code, data = self.ws.cos("config", "validate")
        self.assertEqual(code, 2, data)
        self.assertTrue(any("email_send can never run without approval" in item for item in data["errors"]))
        code, data = self.ws.cos("doctor")
        self.assertEqual(code, 1, data)

    def test_broken_config_file_is_reported_not_replaced(self):
        self.config_file().write_text("{ nope")
        code, data = self.ws.cos("config", "validate")
        self.assertEqual(code, 2, data)
        self.assertEqual(self.config_file().read_text(), "{ nope")

    def test_routines_are_installed_but_not_scheduled_by_default(self):
        routines = self.ws.ok("routine", "list")["routines"]
        self.assertEqual(sorted(routines), ["afternoon", "morning", "weekly"])
        for entry in routines.values():
            self.assertTrue(entry["installed"])
            self.assertFalse(entry["enabled"])
            self.assertIsNone(entry["time"])
            self.assertIsNone(entry["timezone"])
            self.assertIsNone(entry["deliver_to"])
            self.assertEqual(entry["state"], "installed, schedule disabled")

    def test_a_routine_needs_time_zone_and_delivery_before_it_can_be_enabled(self):
        code, _ = self.ws.cos("routine", "configure", "morning", "--time", "07:30")
        self.assertEqual(code, 2)
        code, data = self.ws.cos("config", "set", "routines.morning.enabled", "true")
        self.assertEqual(code, 2, data)
        code, data = self.ws.cos("routine", "prompt", "morning")
        self.assertEqual(code, 2, data)
        code, data = self.ws.cos("routine", "confirm", "morning")
        self.assertEqual(code, 2, data)
        code, data = self.ws.cos("routine", "configure", "morning", "--time", "07:30", "--timezone", "Melbourne",
                                 "--deliver-to", "Scheduled inbox")
        self.assertEqual(code, 2, data)

    def test_configured_is_not_the_same_as_active(self):
        configured = self.ws.ok("routine", "configure", "morning", "--time", "07:30", "--timezone",
                                "Australia/Melbourne", "--deliver-to", "Scheduled inbox in the ChatGPT app")
        self.assertEqual(configured["entry"]["state"], "configured, but no schedule exists in Codex yet (not running)")
        prompt = self.ws.ok("routine", "prompt", "morning")
        self.assertIn("$cos-daily-brief", prompt["prompt"])
        self.assertIn("07:30 (Australia/Melbourne)", prompt["schedule"])
        self.assertNotIn("---PROMPT---", prompt["prompt"])
        confirmed = self.ws.ok("routine", "confirm", "morning")
        self.assertTrue(confirmed["entry"]["state"].startswith("active: schedule confirmed in Codex on"))
        changed = self.ws.ok("routine", "configure", "morning", "--time", "08:00", "--timezone", "Australia/Melbourne",
                             "--deliver-to", "Scheduled inbox")
        self.assertIn("not running", changed["entry"]["state"])  # a changed schedule must be confirmed again
        disabled = self.ws.ok("routine", "disable", "morning")
        self.assertEqual(disabled["entry"]["state"], "installed, schedule disabled")
        self.assertIn("Pause or delete the Scheduled task", disabled["reminder"])
        others = self.ws.ok("routine", "list")["routines"]
        self.assertEqual(others["weekly"]["state"], "installed, schedule disabled")

    def test_connectors_start_unknown_and_need_evidence_to_be_marked_connected(self):
        connectors = self.ws.ok("connector", "list")["connectors"]
        self.assertEqual({entry["status"] for entry in connectors.values()}, {"unknown"})
        code, data = self.ws.cos("connector", "set", "gmail", "--status", "connected")
        self.assertEqual(code, 2, data)
        self.ws.ok("connector", "set", "transcripts", "--status", "connected", "--via", "Fathom MCP",
                   "--evidence", "identity call returned the user", "--provider", "fathom")
        self.ws.ok("connector", "set", "hubspot", "--status", "unavailable", "--evidence", "no tool in this session")
        state = self.ws.ok("connector", "list")
        self.assertEqual(state["connectors"]["transcripts"]["status"], "connected")
        self.assertEqual(state["connectors"]["hubspot"]["status"], "unavailable")
        self.assertEqual(state["transcript_provider"], "fathom")
        brief = self.ws.ok("brief", "data")
        self.assertEqual(brief["connectors"]["gmail"], "unknown")

    def test_brief_data_groups_tasks_by_urgency(self):
        def add(action, *flags):
            self.ws.ok("task", "add", "--company", "Kestrel Ridge Minerals", "--action", action, "--source-type", "user",
                       "--source-ref", "user:2026-11-12", "--priority", "medium", "--rationale", "test", *flags)
        add("Overdue item for the board", "--deadline", "2026-11-10")
        add("Pricing summary due today", "--deadline", "2026-11-12")
        add("Call next week about paper", "--suggested-deadline", "2026-11-17")
        add("Waiting for comms calendar", "--status", "waiting_on_other", "--waiting-on", "Tom Whitlock")
        key = self.ws.ok("action", "plan", "--type", "gmail_draft", "--target", "a@example.com", "--summary", "x")["action"]["key"]
        brief = self.ws.ok("brief", "data")
        tasks = brief["tasks"]
        self.assertEqual([item["id"] for item in tasks["overdue"]], ["T-0001"])
        self.assertEqual([item["id"] for item in tasks["due_today"]], ["T-0002"])
        self.assertEqual([item["id"] for item in tasks["due_soon"]], ["T-0003"])
        self.assertEqual(tasks["due_soon"][0]["deadline"]["kind"], "suggested")
        self.assertEqual([item["id"] for item in tasks["waiting_on_other"]], ["T-0004"])
        self.assertEqual([item["key"] for item in brief["actions_not_confirmed"]], [key])
        self.assertEqual(brief["for_date"], "2026-11-12")


if __name__ == "__main__":
    unittest.main()
