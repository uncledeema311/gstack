"""One complete meeting-to-follow-up workflow on synthetic data.

MOCKED INTEGRATION TEST. MockConnectors stands in for Gmail, Calendar, HubSpot and
the transcript service by reading demo fixtures. run_flow() plays the procedure the
skills describe, step for step, through the real CLI. This proves the state handling
around connector calls. It does not prove that any live integration works, and it
does not prove that the model follows the procedure.
"""
import json
import unittest

from helper import PKG, WorkspaceCase, base_env, run

FIXTURES = PKG / "payload" / "demo" / "fixtures"
COMPANY = "Kestrel Ridge Minerals"


class ConnectorDown(Exception):
    pass


class MockConnectors:
    """MOCK. Serves fixtures, counts calls, and can be told to fail."""

    def __init__(self, down=()):
        self.down = set(down)
        self.drafts_created = 0
        self.emails_sent = 0
        self.crm_writes = 0

    def _need(self, name):
        if name in self.down:
            raise ConnectorDown("%s connector unavailable (mocked failure)" % name)

    def calendar_event(self):
        self._need("calendar")
        return json.loads((FIXTURES / "calendar_event.json").read_text())

    def crm_deal(self):
        self._need("hubspot")
        return json.loads((FIXTURES / "crm_deal.json").read_text())

    def email_thread(self):
        self._need("gmail")
        return json.loads((FIXTURES / "email_thread.json").read_text())

    def transcript(self):
        self._need("transcripts")
        return {"ref": "fathom:recording:demo-rec-7001", "text": (FIXTURES / "transcript.md").read_text()}

    def create_draft(self, to, body):
        self._need("gmail")
        self.drafts_created += 1
        return "gmail:draft:mock-%04d" % self.drafts_created

    def send_email(self, to, body):
        self._need("gmail")
        self.emails_sent += 1
        return "gmail:message:mock-%04d" % self.emails_sent


def run_flow(ws, con):
    """Meeting prep, then post-meeting follow-up, as the skills describe. Returns a report."""
    report = {"done": [], "not_done": [], "needs_you": [], "tracked": []}

    # --- cos-meeting-prep: verify people and deal against the CRM, store with sources
    event = con.calendar_event()
    crm = con.crm_deal()
    for contact in crm["contacts"]:
        ws.ok("context", "add", "--category", "people", "--subject", contact["name"], "--attribute", "role",
              "--value", contact["role"], "--related", COMPANY, "--source-type", "hubspot", "--source-ref",
              contact["ref"], "--verified")
    ws.ok("context", "add", "--category", "opportunities", "--subject", COMPANY, "--attribute", "stage",
          "--value", crm["deal"]["stage"], "--source-type", "hubspot", "--source-ref", crm["ref"], "--verified",
          "--supersede")
    follow = ws.ok("task", "add", "--company", COMPANY, "--action", "Follow up after %s meeting" % COMPANY,
                   "--source-type", "calendar", "--source-ref", event["ref"], "--priority", "high",
                   "--rationale", "Board paper deadline", "--suggested-deadline", "2026-11-13")["task"]["id"]
    report["tracked"].append(follow)

    # --- cos-post-meeting-followup: commitments from the transcript
    try:
        transcript = con.transcript()
    except ConnectorDown as exc:
        ws.ok("connector", "set", "transcripts", "--status", "unavailable", "--evidence", str(exc))
        ws.ok("task", "update", follow, "--status", "blocked", "--blocker",
              "No transcript available and no notes supplied. Nothing was inferred.")
        report["not_done"].append("Follow-up: %s" % exc)
        report["needs_you"].append("Paste the transcript or three lines of notes?")
        return report
    ref = transcript["ref"]
    pricing = ws.ok("commitment", "add", "--company", COMPANY, "--who", "me", "--to", "Priya Raman", "--what",
                    "Send one-page pricing summary for all three tiers", "--source-type", "transcript",
                    "--source-ref", ref + "@00:22", "--verified", "--due", "2026-11-13", "--priority", "high")
    ws.ok("commitment", "add", "--company", COMPANY, "--who", "Tom Whitlock", "--to", "Nic", "--what",
          "Send next year's shareholder communications calendar", "--source-type", "transcript",
          "--source-ref", ref + "@00:26", "--verified", "--suggested-due", "2026-11-17")
    ws.ok("commitment", "add", "--company", COMPANY, "--who", "me", "--to", "Priya Raman", "--what",
          "Propose times for a 30 minute call in the week of 16 November", "--source-type", "transcript",
          "--source-ref", ref + "@00:40", "--verified", "--due", "2026-11-13", "--priority", "high")
    task_id = pricing["task"]["id"]
    report["tracked"].append(task_id)

    # --- the follow-up draft: plan, act, record the outcome
    recipient = next(item["email"] for item in crm["contacts"] if item["name"] == "Priya Raman")  # from the CRM, verified
    plan = ws.ok("action", "plan", "--type", "gmail_draft", "--target", recipient, "--summary",
                 "Follow-up after 12 Nov walkthrough", "--task", task_id, "--fingerprint", "2026-11-12")
    key = plan["action"]["key"]
    if plan["proceed"] is False:
        report["done"].append("Draft already exists: %s" % plan["action"]["system_ref"])
    else:
        try:
            draft_id = con.create_draft(recipient, "body")
            ws.ok("action", "confirm", key, "--system-ref", draft_id)
            ws.ok("task", "update", task_id, "--status", "awaiting_approval", "--note", "Draft ready")
            report["done"].append("Draft saved: %s" % draft_id)
            report["needs_you"].append("Send this email to Priya Raman?")
        except ConnectorDown as exc:
            ws.ok("action", "fail", key, "--error", str(exc))
            ws.ok("task", "update", task_id, "--status", "blocked", "--blocker", str(exc))
            report["not_done"].append("Draft not saved: %s" % exc)

    # --- proposed CRM note: a proposal only
    ws.cos("action", "plan", "--type", "crm_note_draft", "--target", crm["ref"], "--summary",
           "Proposed note for 12 Nov walkthrough", "--task", follow, "--fingerprint", "2026-11-12")
    report["needs_you"].append("Apply the CRM note and changes?")
    report["draft_key"] = key
    report["pricing_task"] = task_id
    return report


class MeetingToFollowUp(WorkspaceCase):
    def tasks(self):
        return self.ws.ok("task", "list", "--all")["tasks"]

    def actions(self):
        return self.ws.ok("action", "list")["actions"]

    def test_complete_flow_from_meeting_context_to_tracked_actions(self):
        con = MockConnectors()
        report = run_flow(self.ws, con)
        self.assertEqual(report["not_done"], [])
        tasks = {item["id"]: item for item in self.tasks()}
        self.assertEqual(len(tasks), 4)
        self.assertEqual(tasks["T-0002"]["status"], "awaiting_approval")
        self.assertEqual(tasks["T-0002"]["deadline"], {"date": "2026-11-13", "kind": "explicit"})
        self.assertEqual(tasks["T-0003"]["status"], "waiting_on_other")
        self.assertEqual(tasks["T-0003"]["deadline"]["kind"], "suggested")
        by_type = {item["type"]: item for item in self.actions()}
        self.assertEqual(by_type["gmail_draft"]["status"], "confirmed")
        self.assertEqual(by_type["gmail_draft"]["system_ref"], "gmail:draft:mock-0001")
        self.assertEqual(by_type["crm_note_draft"]["status"], "planned")
        self.assertEqual(sorted(by_type), ["crm_note_draft", "gmail_draft"])  # nothing was sent or written
        self.assertEqual((con.emails_sent, con.crm_writes), (0, 0))

    def test_every_stored_item_traces_back_to_a_source(self):
        run_flow(self.ws, MockConnectors())
        known = {"calendar:event:demo-evt-2001", "hubspot:deal:demo-deal-1001", "hubspot:contact:demo-ct-901",
                 "hubspot:contact:demo-ct-902", "fathom:recording:demo-rec-7001"}
        for task in self.tasks():
            self.assertIn(task["source"]["ref"].split("@")[0], known, task)
        bundle = self.ws.ok("context", "bundle", "--company", COMPANY)
        facts = [item for items in bundle["sections"].values() for item in items]
        self.assertEqual(len(facts), 6)
        for fact in facts:
            self.assertIn(fact["source"]["ref"].split("@")[0], known, fact)
            self.assertEqual(fact["verification"], "verified")
            self.assertEqual(fact["observed_on"], "2026-11-12")
        shown = self.ws.ok("task", "show", "T-0002")
        self.assertEqual(shown["task"]["decision_id"], "DE-0001")
        self.assertEqual(shown["actions"][0]["system_ref"], "gmail:draft:mock-0001")

    def test_running_the_whole_flow_again_creates_no_duplicates(self):
        con = MockConnectors()
        run_flow(self.ws, con)
        before = (self.tasks(), self.actions())
        second = run_flow(self.ws, con)
        self.assertEqual(con.drafts_created, 1)
        self.assertEqual(second["done"], ["Draft already exists: gmail:draft:mock-0001"])
        after = (self.tasks(), self.actions())
        self.assertEqual([item["id"] for item in before[0]], [item["id"] for item in after[0]])
        self.assertEqual(len(after[1]), 2)
        self.assertEqual(self.ws.ok("context", "bundle", "--company", COMPANY)["sections"]["decisions"].__len__(), 3)

    def test_a_connector_failure_keeps_completed_work_and_states_the_blocker(self):
        con = MockConnectors(down=["gmail"])
        report = run_flow(self.ws, con)
        self.assertEqual(report["not_done"], ["Draft not saved: gmail connector unavailable (mocked failure)"])
        tasks = {item["id"]: item for item in self.tasks()}
        self.assertEqual(len(tasks), 4)  # commitments captured before the failure are kept
        self.assertEqual(tasks["T-0002"]["status"], "blocked")
        self.assertEqual(tasks["T-0002"]["blocker"], "gmail connector unavailable (mocked failure)")
        status = self.ws.ok("action", "status", report["draft_key"])
        self.assertFalse(status["may_report_as_done"])
        self.assertTrue(status["wording"].startswith("Not done."))
        brief = self.ws.ok("brief", "data")
        self.assertEqual([item["id"] for item in brief["tasks"]["blocked"]], ["T-0002"])
        self.assertEqual(brief["actions_not_confirmed"][0]["status"], "failed")
        con.down.clear()  # the connector comes back
        recovered = run_flow(self.ws, con)
        self.assertEqual(recovered["done"], ["Draft saved: gmail:draft:mock-0001"])
        self.assertEqual(self.ws.ok("task", "show", "T-0002")["task"]["status"], "awaiting_approval")
        self.assertIsNone(self.ws.ok("task", "show", "T-0002")["task"]["blocker"])
        self.assertEqual(len(self.tasks()), 4)

    def test_missing_transcript_blocks_the_follow_up_instead_of_inventing_one(self):
        report = run_flow(self.ws, MockConnectors(down=["transcripts"]))
        self.assertEqual(len(report["not_done"]), 1)
        tasks = self.tasks()
        self.assertEqual(len(tasks), 1)  # only the prep task. No commitments were made up
        self.assertEqual(tasks[0]["status"], "blocked")
        self.assertIn("Nothing was inferred", tasks[0]["blocker"])
        self.assertEqual(self.actions(), [])
        self.assertEqual(self.ws.ok("connector", "list")["connectors"]["transcripts"]["status"], "unavailable")
        self.assertEqual(self.ws.ok("context", "get", "--category", "decisions")["count"], 0)

    def test_sending_needs_approval_and_is_only_reported_with_a_message_id(self):
        con = MockConnectors()
        report = run_flow(self.ws, con)
        recipient, task_id = "priya.raman@kestrelridge.example.com", report["pricing_task"]
        send = ["action", "plan", "--type", "email_send", "--target", recipient, "--summary", "Send follow-up",
                "--task", task_id, "--fingerprint", "2026-11-12"]
        code, refused = self.ws.cos(*send)
        self.assertEqual(code, 5, refused)
        self.assertEqual(con.emails_sent, 0)
        approval = self.ws.ok("approval", "record", "--type", "email_send", "--target", recipient, "--quote",
                              "Yes, send it to Priya now", "--task", task_id)["approval"]["id"]
        plan = self.ws.ok(*(send + ["--approval", approval]))
        self.assertIs(plan["proceed"], True)
        message_id = con.send_email(recipient, "body")
        self.ws.ok("action", "confirm", plan["action"]["key"], "--system-ref", message_id)
        self.ws.ok("task", "complete", task_id, "--evidence", "Follow-up email sent", "--evidence-ref", message_id)
        again = self.ws.ok(*(send + ["--approval", approval]))
        self.assertIs(again["proceed"], False)  # a retry does not send twice
        self.assertEqual(con.emails_sent, 1)
        done = self.ws.ok("task", "show", task_id)["task"]
        self.assertEqual((done["status"], done["evidence"]["ref"]), ("completed", "gmail:message:mock-0001"))


class DemoWalkthrough(WorkspaceCase):
    def walkthrough(self):
        code, out, err = run(["bash", self.ws.path / "demo" / "walkthrough.sh"], cwd=self.ws.path, env=base_env())
        self.assertEqual(code, 0, out[-1500:] + err[-1500:])
        return out

    def test_walkthrough_runs_and_shows_each_stage(self):
        out = self.walkthrough()
        for expected in (
            "record.verification: verified",
            'task.deadline: {"date": "2026-11-13", "kind": "suggested"}',
            "task.waiting_on: Tom Whitlock",
            "Email draft - NOT SENT",
            "action.system_ref: gmail:draft:demo-draft-0001 (MOCKED)",
            "reason: already_confirmed",
            "exit_code: 5",
            "Proposed CRM update - NOT WRITTEN",
            "mon 2026-11-16T16:00 Melbourne (+11:00)  =  13:00 Perth (+08:00)",
            "T-0003 [waiting_on_other] Tom Whitlock: Send next year's shareholder communications calendar "
            "(suggested deadline 2026-11-17) <- fathom:recording:demo-rec-7001@00:26",
            "context for Kestrel Ridge Minerals: 7 facts, 4 open tasks",
            "Walkthrough complete.",
        ):
            self.assertIn(expected, out)

    def test_walkthrough_is_repeatable_and_leaves_real_data_alone(self):
        first = self.walkthrough()
        second = self.walkthrough()
        strip = lambda text: [line for line in text.splitlines() if "reset:" not in line]
        self.assertEqual(strip(first), strip(second))
        self.assertEqual(self.ws.ok("task", "list", demo=True)["count"], 4)  # demo state persisted on disk
        self.assertEqual(self.ws.ok("task", "list")["count"], 0)  # real data untouched
        self.assertFalse((self.ws.path / "data" / "tasks").exists())

    def test_first_run_document_matches_the_real_output(self):
        out = self.walkthrough()
        doc = (self.ws.path / "docs" / "FIRST_RUN.md").read_text()
        part_a = doc.split("## Part B")[0]
        blocks = part_a.split("```")[1::2]
        checked = 0
        for block in blocks:
            for line in block.splitlines():
                line = line.rstrip()
                if not line.startswith("  ") or line.strip() == "..." or line.endswith("..."):
                    continue
                self.assertIn(line, out, "FIRST_RUN.md shows a line the walkthrough does not print: %r" % line)
                checked += 1
        self.assertGreater(checked, 25)


if __name__ == "__main__":
    unittest.main()
