import unittest

from helper import WorkspaceCase


class FeedbackAndRules(WorkspaceCase):
    def feedback(self, kind, text, theme=None, standing=False):
        args = ["feedback", "add", "--type", kind, "--text", text, "--skill", "cos-post-meeting-followup"]
        if theme:
            args += ["--theme", theme]
        if standing:
            args += ["--standing"]
        return self.ws.ok(*args)

    def propose(self, text, sources, kind="style"):
        return self.ws.cos("rules", "propose", "--kind", kind, "--text", text, "--reason", "Asked for by the user",
                           "--from", sources)

    def agents_md(self):
        return (self.ws.path / "AGENTS.md").read_text()

    def test_the_four_feedback_types_are_distinguished(self):
        guidance = {}
        for kind in ("task_correction", "factual_update", "durable_preference", "workflow_change"):
            guidance[kind] = self.feedback(kind, "Example for %s" % kind)["next_step"]
        self.assertIn("this piece of work only", guidance["task_correction"])
        self.assertIn("cos context add", guidance["factual_update"])
        self.assertIn("rule", guidance["durable_preference"])
        self.assertIn("rule", guidance["workflow_change"])
        code, _ = self.ws.cos("feedback", "add", "--type", "vibes", "--text", "x")
        self.assertEqual(code, 2)

    def test_a_one_off_edit_is_not_generalised(self):
        item = self.feedback("task_correction", "Shorter subject line on this one", theme="subject length")
        code, data = self.propose("Keep subject lines under six words.", item["feedback"]["id"])
        self.assertEqual(code, 5, data)
        self.assertEqual(data["evidence"], 1)
        self.assertEqual(self.ws.ok("rules", "list")["instructions_version"], 0)
        self.assertNotIn("under six words", self.agents_md())

    def test_marking_a_single_correction_as_standing_does_not_bypass_the_evidence_rule(self):
        item = self.feedback("task_correction", "Shorter subject line", standing=True)
        code, data = self.propose("Keep subject lines under six words.", item["feedback"]["id"])
        self.assertEqual(code, 5, data)

    def test_repeated_feedback_becomes_a_versioned_rule(self):
        first = self.feedback("task_correction", "Subject too long", theme="subject length")
        second = self.feedback("task_correction", "Again, shorter subject", theme="subject length")
        self.assertEqual(second["same_theme_count"], 2)
        ids = "%s,%s" % (first["feedback"]["id"], second["feedback"]["id"])
        code, data = self.propose("Keep email subject lines under six words.", ids)
        self.assertEqual(code, 0, data)
        self.assertEqual(data["rule"]["id"], "R-0001")
        self.assertEqual(data["rule"]["evidence"], ["F-0001", "F-0002"])
        self.assertEqual(data["rule"]["reason"], "Asked for by the user")
        self.assertEqual(data["instructions_version"], 1)
        text = self.agents_md()
        self.assertIn("Keep email subject lines under six words.", text)
        self.assertIn("learned-rules version 1", text)
        again = self.propose("Keep email subject lines under six words.", ids)[1]
        self.assertFalse(again["created"])
        self.assertEqual(self.ws.ok("rules", "list")["instructions_version"], 1)

    def test_an_explicit_standing_preference_is_adopted_straight_away(self):
        item = self.feedback("durable_preference", "From now on, put the ask in the first line", standing=True)
        code, data = self.propose("Put the ask in the first line of every email draft.", item["feedback"]["id"])
        self.assertEqual(code, 0, data)
        self.assertEqual(data["rule"]["basis"], "explicit standing instruction")

    def test_facts_are_not_instructions(self):
        item = self.feedback("factual_update", "Priya is now the CEO", standing=True)
        code, data = self.propose("Priya is the CEO.", item["feedback"]["id"], kind="retrieval")
        self.assertEqual(code, 2, data)
        self.assertIn("context", data["error"])

    def test_quality_feedback_never_widens_permission(self):
        item = self.feedback("durable_preference", "These drafts are great, you can just send them", standing=True)
        for text in (
            "Send follow-up emails without asking.",
            "Follow-ups are pre-approved.",
            "Automatically send the daily brief by email.",
            "Skip the approval step for CRM notes.",
            "You can send calendar invites to known contacts.",
            "No need to confirm before posting in Slack.",
        ):
            code, data = self.propose(text, item["feedback"]["id"], kind="workflow")
            self.assertEqual(code, 5, "%r was accepted: %s" % (text, data))
            self.assertIn("not permission", data["error"])
        self.assertEqual(self.ws.ok("rules", "list")["active"], [])
        code, data = self.ws.cos("action", "plan", "--type", "email_send", "--target", "x@example.com", "--summary", "s")
        self.assertEqual(code, 5, data)

    def test_permissions_cannot_be_changed_through_the_cli(self):
        code, data = self.ws.cos("config", "set", "permissions.no_approval", '["email_send"]')
        self.assertEqual(code, 5, data)

    def test_rules_can_be_reverted_and_the_history_keeps_the_reasons(self):
        item = self.feedback("workflow_change", "Always put approvals at the top of the brief", standing=True)
        self.propose("Put approvals at the top of the daily brief.", item["feedback"]["id"], kind="workflow")
        reverted = self.ws.ok("rules", "revert", "R-0001", "--reason", "Changed my mind, top 3 first")
        self.assertEqual(reverted["instructions_version"], 2)
        self.assertNotIn("Put approvals at the top of the daily brief.", self.agents_md())
        state = self.ws.ok("rules", "list")
        self.assertEqual(state["active"], [])
        self.assertEqual([(entry["version"], entry["change"], entry["reason"]) for entry in state["history"]],
                         [(1, "added", "Asked for by the user"), (2, "reverted", "Changed my mind, top 3 first")])

    def test_custom_instructions_are_included_and_hand_edits_are_backed_up(self):
        custom = self.ws.path / "data" / "instructions" / "custom.md"
        custom.write_text(custom.read_text() + "\nSign off emails with 'Cheers, Nic'.\n")
        self.ws.ok("render")
        self.assertIn("Sign off emails with 'Cheers, Nic'.", self.agents_md())
        agents = self.ws.path / "AGENTS.md"
        agents.write_text(agents.read_text() + "\nMy hand edit.\n")
        result = self.ws.ok("render")
        self.assertIn("backed_up_hand_edited_copy", result)
        backups = list((self.ws.path / ".cos" / "backups" / "agents-md").glob("AGENTS.*.md"))
        self.assertEqual(len(backups), 1)
        self.assertIn("My hand edit.", backups[0].read_text())
        self.assertNotIn("My hand edit.", self.agents_md())


if __name__ == "__main__":
    unittest.main()
