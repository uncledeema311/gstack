import json
import unittest

from helper import WorkspaceCase


class TaskQueue(WorkspaceCase):
    def test_task_has_every_required_field(self):
        code, data = self.task(deadline="2026-11-13")
        self.assertEqual(code, 0, data)
        task = data["task"]
        self.assertRegex(task["id"], r"^T-\d{4}$")
        self.assertEqual(task["company"], "Kestrel Ridge Minerals")
        self.assertEqual(task["action"], "Send pricing summary")
        self.assertEqual(task["owner"], "Nic")
        self.assertEqual(task["source"]["ref"], "fathom:recording:demo-rec-7001")
        self.assertEqual(task["priority"], "high")
        self.assertEqual(task["priority_rationale"], "Asked for it")
        self.assertEqual(task["status"], "proposed")
        self.assertIsNone(task["evidence"])

    def test_explicit_and_suggested_deadlines_are_labelled_separately(self):
        explicit = self.task(deadline="2026-11-13")[1]["task"]
        suggested = self.task(action="Book the follow-up call", suggested_deadline="2026-11-17")[1]["task"]
        self.assertEqual(explicit["deadline"], {"date": "2026-11-13", "kind": "explicit"})
        self.assertEqual(suggested["deadline"], {"date": "2026-11-17", "kind": "suggested"})
        code, data = self.task(action="Third thing entirely", deadline="2026-11-13", suggested_deadline="2026-11-14")
        self.assertEqual(code, 2, data)

    def test_source_reference_is_mandatory(self):
        code, _ = self.ws.cos("task", "add", "--company", "X", "--action", "Y", "--priority", "low", "--rationale", "z")
        self.assertEqual(code, 2)

    def test_exact_duplicate_returns_the_existing_task(self):
        first = self.task()[1]
        code, second = self.ws.cos("task", "add", "--company", "kestrel ridge minerals", "--action", "SEND pricing  summary.",
                                   "--source-type", "gmail", "--source-ref", "gmail:thread:demo-thr-3001",
                                   "--priority", "low", "--rationale", "seen again in email")
        self.assertEqual(code, 0, second)
        self.assertTrue(first["created"])
        self.assertFalse(second["created"])
        self.assertTrue(second["deduplicated"])
        self.assertEqual(second["task"]["id"], first["task"]["id"])
        self.assertEqual(second["task"]["also_seen_in"], [{"type": "gmail", "ref": "gmail:thread:demo-thr-3001"}])
        self.assertEqual(self.ws.ok("task", "list")["count"], 1)

    def test_near_duplicate_is_refused_until_forced(self):
        self.task()
        code, data = self.task(action="Send the pricing summary")
        self.assertEqual(code, 3, data)
        self.assertEqual(data["possible_duplicates"][0]["id"], "T-0001")
        code, data = self.task(action="Send the pricing summary", force_new=True)
        self.assertEqual(code, 0, data)
        self.assertEqual(data["task"]["id"], "T-0002")
        self.assertEqual(self.ws.ok("task", "duplicates")["possible_duplicate_groups"][0]["task_ids"], ["T-0001", "T-0002"])

    def test_same_action_for_another_company_is_not_a_duplicate(self):
        self.task()
        code, data = self.task(company="Other Company Pty Ltd")
        self.assertEqual(code, 0, data)
        self.assertTrue(data["created"])

    def test_all_seven_states_and_their_requirements(self):
        self.task()
        for status in ("drafted", "awaiting_approval", "in_progress"):
            self.assertEqual(self.ws.ok("task", "update", "T-0001", "--status", status)["task"]["status"], status)
        code, data = self.ws.cos("task", "update", "T-0001", "--status", "waiting_on_other")
        self.assertEqual(code, 2, data)
        self.ws.ok("task", "update", "T-0001", "--status", "waiting_on_other", "--waiting-on", "Tom Whitlock")
        code, data = self.ws.cos("task", "update", "T-0001", "--status", "blocked")
        self.assertEqual(code, 2, data)
        blocked = self.ws.ok("task", "update", "T-0001", "--status", "blocked", "--blocker", "Gmail connector failed")
        self.assertEqual(blocked["task"]["blocker"], "Gmail connector failed")
        code, data = self.ws.cos("task", "update", "T-0001", "--status", "completed")
        self.assertEqual(code, 2, data)
        self.assertIn("evidence", data["error"])
        done = self.ws.ok("task", "complete", "T-0001", "--evidence", "Sent, message id 18c2",
                          "--evidence-ref", "gmail:message:18c2")
        self.assertEqual(done["task"]["status"], "completed")
        self.assertEqual(done["task"]["evidence"]["ref"], "gmail:message:18c2")
        self.assertEqual([step["to"] for step in done["task"]["history"]],
                         ["proposed", "drafted", "awaiting_approval", "in_progress", "waiting_on_other", "blocked",
                          "completed"])

    def test_unknown_status_is_rejected(self):
        self.task()
        code, _ = self.ws.cos("task", "update", "T-0001", "--status", "done")
        self.assertEqual(code, 2)

    def test_completed_task_is_protected_and_frees_its_dedupe_slot(self):
        self.task()
        self.ws.ok("task", "complete", "T-0001", "--evidence", "Sent")
        code, data = self.ws.cos("task", "update", "T-0001", "--status", "in_progress")
        self.assertEqual(code, 5, data)
        code, data = self.task()
        self.assertEqual(code, 0, data)
        self.assertEqual(data["task"]["id"], "T-0002")
        self.assertEqual(self.ws.ok("task", "list")["count"], 1)
        self.assertEqual(self.ws.ok("task", "list", "--all")["count"], 2)

    def test_state_is_on_disk_and_survives_a_new_process(self):
        self.task(deadline="2026-11-13")
        stored = json.loads((self.ws.path / "data" / "tasks" / "tasks.json").read_text())
        self.assertEqual(stored["records"][0]["id"], "T-0001")
        self.assertEqual(self.ws.ok("task", "show", "T-0001")["task"]["action"], "Send pricing summary")

    def test_unreadable_store_is_reported_and_left_untouched(self):
        self.task()
        path = self.ws.path / "data" / "tasks" / "tasks.json"
        path.write_text("{ this is not json")
        code, data = self.task(action="Something new")
        self.assertEqual(code, 4, data)
        self.assertEqual(path.read_text(), "{ this is not json")
        code, data = self.ws.cos("doctor")
        self.assertEqual(code, 1, data)
        self.assertIn("store tasks/tasks.json", [item["check"] for item in data["checks"] if item["status"] == "fail"])

    def test_commitment_creates_a_record_and_a_task_once(self):
        args = ["commitment", "add", "--company", "Kestrel Ridge Minerals", "--who", "Tom Whitlock", "--to", "Nic",
                "--what", "Send the shareholder communications calendar", "--source-type", "transcript",
                "--source-ref", "fathom:recording:demo-rec-7001@00:26", "--suggested-due", "2026-11-17"]
        first = self.ws.ok(*args)
        self.assertEqual(first["task"]["status"], "waiting_on_other")
        self.assertEqual(first["task"]["waiting_on"], "Tom Whitlock")
        self.assertEqual(first["task"]["kind"], "commitment")
        self.assertEqual(first["task"]["decision_id"], first["commitment"]["id"])
        second = self.ws.ok(*args)
        self.assertFalse(second["task_created"])
        self.assertFalse(second["commitment_created"])
        self.assertEqual(self.ws.ok("task", "list")["count"], 1)


if __name__ == "__main__":
    unittest.main()
