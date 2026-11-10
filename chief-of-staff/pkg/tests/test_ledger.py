import unittest

from helper import WorkspaceCase

PRIYA = "priya.raman@kestrelridge.example.com"


class ActionLedger(WorkspaceCase):
    def plan(self, kind="gmail_draft", target=PRIYA, **extra):
        args = ["action", "plan", "--type", kind, "--target", target, "--summary", "Follow-up after walkthrough",
                "--task", "T-0001", "--fingerprint", "2026-11-12"]
        now = extra.pop("now", None)
        for key, value in extra.items():
            args += ["--" + key, value]
        return self.ws.cos(*args, now=now)

    def approve(self, kind="email_send", target=PRIYA, quote="Yes, send it to Priya", now=None):
        return self.ws.cos("approval", "record", "--type", kind, "--target", target, "--quote", quote, "--task", "T-0001",
                           now=now)

    def test_drafts_need_no_approval(self):
        code, data = self.plan()
        self.assertEqual(code, 0, data)
        self.assertIs(data["proceed"], True)
        self.assertEqual(data["action"]["class"], "no_approval")

    def test_nothing_is_reportable_as_done_without_a_system_reference(self):
        key = self.plan()[1]["action"]["key"]
        status = self.ws.ok("action", "status", key)
        self.assertFalse(status["may_report_as_done"])
        self.assertIn("Do not describe this as done", status["wording"])
        code, data = self.ws.cos("action", "confirm", key, "--system-ref", "")
        self.assertEqual(code, 2, data)
        self.ws.ok("action", "confirm", key, "--system-ref", "gmail:draft:r-8842")
        status = self.ws.ok("action", "status", key)
        self.assertTrue(status["may_report_as_done"])
        self.assertIn("gmail:draft:r-8842", status["wording"])

    def test_a_retry_after_success_does_not_repeat_the_effect(self):
        key = self.plan()[1]["action"]["key"]
        self.ws.ok("action", "confirm", key, "--system-ref", "gmail:draft:r-8842")
        code, again = self.plan()
        self.assertEqual(code, 0, again)
        self.assertIs(again["proceed"], False)
        self.assertEqual(again["reason"], "already_confirmed")
        self.assertEqual(again["action"]["system_ref"], "gmail:draft:r-8842")
        self.assertEqual(self.ws.ok("action", "list")["count"], 1)

    def test_an_attempt_with_unknown_outcome_must_be_checked_first(self):
        self.plan()
        again = self.plan()[1]
        self.assertEqual(again["proceed"], "verify_first")
        self.assertEqual(self.ws.ok("action", "list")["count"], 1)

    def test_failure_is_recorded_and_a_clean_retry_is_allowed(self):
        key = self.plan()[1]["action"]["key"]
        failed = self.ws.ok("action", "fail", key, "--error", "Gmail connector timed out")
        self.assertEqual(failed["action"]["status"], "failed")
        status = self.ws.ok("action", "status", key)
        self.assertFalse(status["may_report_as_done"])
        self.assertIn("Gmail connector timed out", status["wording"])
        retry = self.plan()[1]
        self.assertIs(retry["proceed"], True)
        self.assertEqual(retry["reason"], "retry")
        self.assertEqual(len(retry["action"]["attempts"]), 3)

    def test_different_content_or_recipient_is_a_different_action(self):
        first = self.plan()[1]["action"]["key"]
        second = self.plan(target="tom.whitlock@kestrelridge.example.com")[1]["action"]["key"]
        self.assertNotEqual(first, second)

    def test_sending_email_is_refused_without_approval(self):
        code, data = self.plan(kind="email_send")
        self.assertEqual(code, 5, data)
        self.assertEqual(data["needs"], "approval")
        self.assertEqual(self.ws.ok("action", "list")["count"], 0)

    def test_every_locked_action_type_needs_approval(self):
        for kind in ("email_send", "calendar_invite", "calendar_event_change", "crm_write", "slack_send"):
            code, data = self.plan(kind=kind, target="x")
            self.assertEqual(code, 5, "%s: %s" % (kind, data))

    def test_approval_is_specific_single_use_and_expires(self):
        approval = self.approve()[1]["approval"]["id"]
        code, data = self.plan(kind="email_send", target="tom.whitlock@kestrelridge.example.com", approval=approval)
        self.assertEqual(code, 5, data)  # approval was for Priya, not Tom
        code, data = self.plan(kind="calendar_invite", approval=approval)
        self.assertEqual(code, 5, data)  # approval was for an email, not an invitation
        code, data = self.plan(kind="email_send", approval=approval)
        self.assertEqual(code, 0, data)
        self.assertIs(data["proceed"], True)
        self.assertEqual(data["action"]["approval_id"], approval)
        code, data = self.ws.cos("action", "plan", "--type", "email_send", "--target", PRIYA, "--summary", "A second email",
                                 "--task", "T-0001", "--fingerprint", "another", "--approval", approval)
        self.assertEqual(code, 5, data)  # one approval, one action
        self.assertIn("already used", data["error"])
        stale = self.approve(now="2026-11-12T00:50:00Z")[1]["approval"]["id"]
        code, data = self.ws.cos("action", "plan", "--type", "email_send", "--target", PRIYA, "--summary", "Late",
                                 "--task", "T-0001", "--fingerprint", "late", "--approval", stale,
                                 now="2026-11-13T00:50:00Z")
        self.assertEqual(code, 5, data)
        self.assertIn("expired", data["error"])

    def test_calendar_invitation_flow_with_approval(self):
        code, data = self.plan(kind="calendar_invite", target="Follow-up call, Mon 16 Nov 16:00 AEDT, Priya Raman")
        self.assertEqual(code, 5)
        approval = self.approve(kind="calendar_invite", target="Follow-up call, Mon 16 Nov 16:00 AEDT, Priya Raman",
                                quote="Yes, send that invite")[1]["approval"]["id"]
        data = self.plan(kind="calendar_invite", target="Follow-up call, Mon 16 Nov 16:00 AEDT, Priya Raman",
                         approval=approval)[1]
        self.assertIs(data["proceed"], True)

    def test_never_permitted_actions_cannot_be_planned_or_approved(self):
        for kind in ("purchase", "record_delete", "permission_change"):
            code, data = self.plan(kind=kind, target="x")
            self.assertEqual(code, 5, data)
            code, data = self.approve(kind=kind, target="x")
            self.assertEqual(code, 5, data)

    def test_unknown_action_type_is_rejected(self):
        code, data = self.plan(kind="telepathy")
        self.assertEqual(code, 2, data)

    def test_approval_needs_the_users_words(self):
        code, data = self.approve(quote="")
        self.assertEqual(code, 2, data)


if __name__ == "__main__":
    unittest.main()
