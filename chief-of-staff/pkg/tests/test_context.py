import unittest

from helper import WorkspaceCase


class PersistentContext(WorkspaceCase):
    def add(self, category, subject, value, attribute=None, ref="hubspot:contact:demo-ct-901", **extra):
        args = ["context", "add", "--category", category, "--subject", subject, "--value", value,
                "--source-type", ref.split(":")[0], "--source-ref", ref]
        if attribute:
            args += ["--attribute", attribute]
        for key, item in extra.items():
            flag = "--" + key.replace("_", "-")
            args += [flag] if item is True else [flag, str(item)]
        return self.ws.cos(*args)

    def test_categories_are_stored_separately(self):
        self.add("preferences", "writing", "Australian English", ref="user:2026-11-12")
        self.add("reference", "pricing", "Three tiers", ref="drive:file:demo")
        self.add("people", "Priya Raman", "Chief Financial Officer", "role")
        self.add("companies", "Kestrel Ridge Minerals", "Perth", "city")
        self.add("opportunities", "Kestrel Ridge Minerals", "Demo scheduled", "stage", ref="hubspot:deal:demo-deal-1001")
        self.add("decisions", "Kestrel Ridge Minerals", "Board decides", ref="fathom:recording:demo-rec-7001", kind="decision")
        self.add("notes", "scratch", "Check the deck link", ref="user:2026-11-12")
        files = sorted(path.name for path in (self.ws.path / "data" / "context").glob("*.json"))
        self.assertEqual(files, ["companies.json", "decisions.json", "notes.json", "opportunities.json", "people.json",
                                 "preferences.json", "reference.json"])

    def test_fact_keeps_source_date_and_verification_status(self):
        code, data = self.add("people", "Priya Raman", "Chief Financial Officer", "role", verified=True,
                              observed_on="2026-11-10")
        self.assertEqual(code, 0, data)
        record = data["record"]
        self.assertEqual(record["source"], {"type": "hubspot", "ref": "hubspot:contact:demo-ct-901", "url": None})
        self.assertEqual(record["observed_on"], "2026-11-10")
        self.assertEqual(record["verification"], "verified")
        unverified = self.add("people", "Tom Whitlock", "IR Manager", "role")[1]["record"]
        self.assertEqual(unverified["verification"], "unverified")
        self.assertIsNone(unverified["verified_at"])

    def test_a_fact_without_a_source_is_rejected(self):
        code, _ = self.ws.cos("context", "add", "--category", "people", "--subject", "X", "--value", "Y")
        self.assertEqual(code, 2)

    def test_future_dates_are_rejected(self):
        code, data = self.add("people", "Priya Raman", "CFO", "role", observed_on="2027-01-01")
        self.assertEqual(code, 2, data)

    def test_seeing_the_same_fact_again_does_not_duplicate_it(self):
        self.add("people", "Priya Raman", "Chief Financial Officer", "role")
        code, data = self.add("people", "priya raman", "chief financial officer", "Role", verified=True)
        self.assertTrue(data["deduplicated"])
        self.assertEqual(data["record"]["verification"], "verified")
        self.assertEqual(self.ws.ok("context", "get", "--subject", "Priya Raman")["count"], 1)

    def test_conflicting_facts_are_flagged_until_resolved(self):
        self.add("opportunities", "Kestrel Ridge Minerals", "Demo scheduled", "stage", ref="hubspot:deal:demo-deal-1001")
        code, data = self.add("opportunities", "Kestrel Ridge Minerals", "Proposal sent", "stage", ref="user:2026-11-12")
        self.assertEqual(data["record"]["conflicts_with"], ["OP-0001"])
        attention = self.ws.ok("context", "attention")
        self.assertEqual(sorted(item["id"] for item in attention["conflicts"]), ["OP-0001", "OP-0002"])
        bundle = self.ws.ok("context", "bundle", "--company", "Kestrel Ridge Minerals")
        self.assertTrue(any("Conflicting" in line for line in bundle["advice"]))
        resolved = self.add("opportunities", "Kestrel Ridge Minerals", "Demo completed", "stage",
                            ref="hubspot:deal:demo-deal-1001", supersede=True, verified=True)[1]
        self.assertEqual(sorted(resolved["superseded"]), ["OP-0001", "OP-0002"])
        self.assertEqual(self.ws.ok("context", "attention")["conflicts"], [])
        active = self.ws.ok("context", "get", "--subject", "Kestrel Ridge Minerals", "--category", "opportunities")
        self.assertEqual([item["value"] for item in active["records"]], ["Demo completed"])

    def test_time_sensitive_facts_go_stale_and_stable_ones_do_not(self):
        self.add("opportunities", "Kestrel Ridge Minerals", "Demo scheduled", "stage", observed_on="2026-10-20")
        self.add("people", "Priya Raman", "Chief Financial Officer", "role", observed_on="2026-10-20")
        self.add("preferences", "writing", "Australian English", ref="user:2025-01-01", observed_on="2025-01-01")
        attention = self.ws.ok("context", "attention")
        self.assertEqual([item["id"] for item in attention["stale"]], ["OP-0001"])
        bundle = self.ws.ok("context", "bundle", "--company", "Kestrel Ridge Minerals")
        self.assertTrue(any("Re-check the live source" in line for line in bundle["advice"]))
        self.ws.ok("context", "verify", "OP-0001", "--source-type", "hubspot", "--source-ref", "hubspot:deal:demo-deal-1001")
        self.assertEqual(self.ws.ok("context", "attention")["stale"], [])

    def test_retrieval_is_a_slice_never_the_whole_history(self):
        code, data = self.ws.cos("context", "get")
        self.assertEqual(code, 2, data)
        for index in range(40):
            self.add("people", "Person %d" % index, "Role %d" % index, "role", related="Big Company")
        self.add("people", "Priya Raman", "Chief Financial Officer", "role", related="Kestrel Ridge Minerals")
        self.add("companies", "Other Company", "Sydney", "city")
        bundle = self.ws.ok("context", "bundle", "--company", "Kestrel Ridge Minerals")
        subjects = [item["subject"] for items in bundle["sections"].values() for item in items]
        self.assertEqual(subjects, ["Priya Raman"])
        big = self.ws.ok("context", "bundle", "--company", "Big Company")
        self.assertEqual(sum(len(items) for items in big["sections"].values()), 25)
        self.assertTrue(big["truncated"])
        self.assertEqual(self.ws.ok("context", "get", "--query", "chief financial")["count"], 1)

    def test_working_notes_expire(self):
        note = self.add("notes", "scratch", "Check the deck link", ref="user:2026-11-12")[1]["record"]
        self.assertEqual(note["expires_on"], "2026-11-19")
        later = "2026-11-25T00:00:00Z"
        self.assertEqual(self.ws.ok("context", "get", "--category", "notes", now=later)["count"], 0)
        self.assertEqual(self.ws.ok("context", "purge-notes", now=later)["expired_notes_removed"], 1)

    def test_dates_follow_the_local_time_zone_not_utc(self):
        # 22:30 UTC on 11 Nov is already 12 Nov in Melbourne.
        record = self.ws.ok("context", "add", "--category", "people", "--subject", "A", "--value", "B", "--source-type",
                            "user", "--source-ref", "user:x", now="2026-11-11T22:30:00Z")["record"]
        self.assertEqual(record["observed_on"], "2026-11-12")

    def test_retired_facts_drop_out_of_retrieval(self):
        self.add("people", "Priya Raman", "Chief Financial Officer", "role")
        self.ws.ok("context", "retire", "PE-0001", "--reason", "Left the company")
        self.assertEqual(self.ws.ok("context", "get", "--subject", "Priya Raman")["count"], 0)
        self.assertEqual(self.ws.ok("context", "get", "--subject", "Priya Raman", "--include-inactive")["count"], 1)


if __name__ == "__main__":
    unittest.main()
