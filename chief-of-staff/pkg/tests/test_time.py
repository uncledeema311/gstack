import json
import unittest

from helper import WorkspaceCase

CHECKED = "2026-11-12T00:49:00Z"


class TimeZones(WorkspaceCase):
    def slots(self, *extra, busy=None, checked=CHECKED, now=None):
        args = ["slots"] + list(extra)
        if busy is not None:
            args += ["--busy-json", json.dumps(busy)]
            if checked:
                args += ["--calendar-checked-at", checked]
        return self.ws.cos(*args, now=now)

    def starts(self, data):
        return [slot["start"] for slot in data["slots"]]

    def test_now_reports_daylight_saving_correctly(self):
        summer = self.ws.ok("now", now="2026-11-12T00:50:00Z")["now"]
        self.assertEqual((summer["local"], summer["utc_offset"], summer["abbreviation"], summer["daylight_saving"]),
                         ("2026-11-12T11:50:00+11:00", "+11:00", "AEDT", True))
        winter = self.ws.ok("now", now="2026-06-15T00:50:00Z")["now"]
        self.assertEqual((winter["local"], winter["utc_offset"], winter["daylight_saving"]),
                         ("2026-06-15T10:50:00+10:00", "+10:00", False))
        perth = self.ws.ok("now", "--tz", "Australia/Perth", now="2026-11-12T00:50:00Z")["now"]
        self.assertEqual(perth["utc_offset"], "+08:00")
        self.assertEqual(self.ws.ok("now", now="2026-11-11T22:30:00Z")["now"]["date"], "2026-11-12")

    def test_times_are_not_suggested_without_current_availability(self):
        code, data = self.slots("--from", "2026-11-16")
        self.assertEqual(code, 2, data)
        self.assertIn("Read the calendar first", data["error"])
        code, data = self.slots("--from", "2026-11-16", "--no-calendar")
        self.assertEqual(code, 0, data)
        self.assertFalse(data["availability_verified"])
        self.assertTrue(data["warnings"])
        code, data = self.slots("--from", "2026-11-16", busy=[], checked="2026-11-11T20:00:00Z")
        self.assertFalse(data["availability_verified"])  # read more than an hour ago
        code, data = self.slots("--from", "2026-11-16", busy=[], checked=None)
        self.assertFalse(data["availability_verified"])  # no read time given
        code, data = self.slots("--from", "2026-11-16", busy=[])
        self.assertTrue(data["availability_verified"])

    def test_busy_blocks_and_buffers_are_respected(self):
        busy = [{"start": "2026-11-16T10:00:00+11:00", "end": "2026-11-16T11:00:00+11:00"}]
        data = self.slots("--from", "2026-11-16", "--days", "1", "--limit", "40", busy=busy)[1]
        starts = [item[11:16] for item in self.starts(data)]
        self.assertEqual(starts[:3], ["08:30", "09:00", "11:30"])  # 09:30 would end at 10:00, inside the buffer
        self.assertNotIn("09:30", starts)
        self.assertNotIn("11:00", starts)
        no_buffer = self.slots("--from", "2026-11-16", "--days", "1", "--limit", "40", "--buffer", "0", busy=busy)[1]
        self.assertIn("09:30", [item[11:16] for item in self.starts(no_buffer)])

    def test_busy_times_given_in_another_zone_or_utc_are_converted(self):
        busy = [{"start": "2026-11-15T23:00:00Z", "end": "2026-11-16T00:00:00Z"}]  # 10:00 to 11:00 Melbourne
        data = self.slots("--from", "2026-11-16", "--days", "1", "--limit", "3", busy=busy)[1]
        self.assertEqual([item[11:16] for item in self.starts(data)], ["08:30", "09:00", "11:30"])

    def test_all_day_events_block_the_day_and_weekends_are_skipped(self):
        busy = [{"start": "2026-11-13", "end": "2026-11-14"}]
        data = self.slots("--from", "2026-11-13", "--days", "4", "--limit", "1", busy=busy)[1]
        self.assertEqual(data["slots"][0]["start"], "2026-11-16T08:30:00+11:00")  # Fri blocked, Sat and Sun skipped
        self.assertEqual(data["slots"][0]["weekday"], "mon")

    def test_minimum_notice_is_applied(self):
        # Now is 11:50 on Thu 12 Nov. Four hours of notice means nothing before 15:50.
        data = self.slots("--from", "2026-11-12", "--days", "1", "--limit", "10", busy=[])[1]
        self.assertEqual([item[11:16] for item in self.starts(data)], ["16:00", "16:30", "17:00"])

    def test_other_party_local_time_changes_with_daylight_saving(self):
        november = self.slots("--from", "2026-11-16", "--days", "1", "--limit", "1", "--attendee-tz", "Australia/Perth",
                              busy=[])[1]["slots"][0]
        self.assertEqual(november["start"], "2026-11-16T08:30:00+11:00")
        self.assertEqual(november["attendees"][0]["start"], "2026-11-16T05:30:00+08:00")  # 3 hours behind
        self.assertTrue(november["attendees"][0]["outside_business_hours"])
        june = self.slots("--from", "2026-06-15", "--days", "1", "--limit", "1", "--attendee-tz", "Australia/Perth",
                          busy=[], checked="2026-06-10T00:00:00Z", now="2026-06-10T00:10:00Z")[1]["slots"][0]
        self.assertEqual(june["start"], "2026-06-15T08:30:00+10:00")
        self.assertEqual(june["attendees"][0]["start"], "2026-06-15T06:30:00+08:00")  # 2 hours behind

    def test_attendee_hours_and_stated_preference_filters(self):
        data = self.slots("--from", "2026-11-16", "--days", "1", "--limit", "40", "--attendee-tz", "Australia/Perth",
                          "--attendee-hours-only", busy=[])[1]
        self.assertEqual(self.starts(data)[0], "2026-11-16T11:00:00+11:00")  # 08:00 in Perth
        window = self.slots("--from", "2026-11-16", "--days", "1", "--limit", "40", "--attendee-tz", "Australia/Perth",
                            "--attendee-hours-only", "--attendee-window", "13:00-15:00", busy=[])[1]
        self.assertEqual([item[11:16] for item in self.starts(window)], ["16:00", "16:30", "17:00"])

    def test_far_away_zones_show_the_date_shift(self):
        slot = self.slots("--from", "2026-11-16", "--days", "1", "--limit", "1", "--attendee-tz", "America/New_York",
                          busy=[])[1]["slots"][0]
        self.assertEqual(slot["attendees"][0]["start"], "2026-11-15T16:30:00-05:00")  # still Sunday in New York

    def test_times_skipped_by_daylight_saving_are_never_offered(self):
        # Clocks in Melbourne go from 02:00 straight to 03:00 on Sunday 4 October 2026.
        self.ws.ok("config", "set", "working_hours", '{"start": "01:00", "end": "04:00", "days": ["sun"]}')
        data = self.slots("--from", "2026-10-04", "--days", "1", "--limit", "20", busy=[],
                          checked="2026-10-01T00:00:00Z", now="2026-10-01T00:10:00Z")[1]
        starts = self.starts(data)
        self.assertIn("2026-10-04T01:00:00+10:00", starts)
        self.assertIn("2026-10-04T03:00:00+11:00", starts)
        self.assertFalse([item for item in starts if item[11:13] == "02"], starts)

    def test_bad_input_is_rejected(self):
        code, data = self.slots("--from", "2026-11-16", "--attendee-tz", "Mars/Olympus", busy=[])
        self.assertEqual(code, 2, data)
        code, data = self.slots("--from", "16/11/2026", busy=[])
        self.assertEqual(code, 2, data)
        code, data = self.slots("--from", "2026-11-16", busy=[{"start": "2026-11-16T10:00:00", "end": "2026-11-16T11:00:00"}])
        self.assertEqual(code, 2, data)  # no UTC offset on the busy block
        self.assertIn("offset", data["error"])


if __name__ == "__main__":
    unittest.main()
