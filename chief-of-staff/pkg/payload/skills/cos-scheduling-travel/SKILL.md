---
name: cos-scheduling-travel
description: Find and propose meeting times from current calendar availability with time zones and buffers, draft the scheduling message, and prepare travel plans and itineraries. Use when the user asks to find a time, book or move a meeting, plan a trip, or prepare for travel to another city. Never sends calendar invitations without approval.
---

# Scheduling and travel coordination

Shared rules are in AGENTS.md. This skill adds procedure only.

## Trigger

- "Find a time with <person>", "when can I meet <company> next week?", "move my 3pm", "plan my Perth trip", "what do I need for Sydney on Thursday?"

## Required inputs

- Scheduling: who, how long, roughly when, and format (video, phone, in person and where).
- Travel: destination, dates, and the meetings or events it is for.
- The other party's city or time zone. If unknown, check the CRM or email signature. If still unknown, ask.

## Retrieval procedure

Scheduling:

1. `bin/cos now` for the local time zone, offset and whether daylight saving applies.
2. Read the user's calendar for the window: every event with start and end, including tentative holds and all-day events. Write the busy blocks to a file as JSON: `[{"start": "<ISO with offset>", "end": "<ISO with offset>"}]`. Note the time you read it.
3. `bin/cos slots --from YYYY-MM-DD --days N --busy-file FILE --calendar-checked-at "<ISO time of the read>" --duration MIN --attendee-tz "<IANA zone>"`
   - Do not suggest times if `availability_verified` is false. Read the calendar again.
   - Slots already respect working hours, the buffer and minimum notice from config.
   - Add `--attendee-hours-only` to leave out times outside the attendee's business hours. If they stated a preference ("early afternoon my time"), pass it in their local time with `--attendee-window 13:00-15:00`. If nothing is left, say so and widen the window.
4. For in-person meetings add travel time each side as extra buffer (`--buffer`), and check the location of the meetings before and after.
5. Verify the attendee's name and email address against a live source.

Travel:

1. Calendar events in the destination for the dates, plus the last event before leaving and the first after returning.
2. Emails with bookings or confirmations for those dates (flights, accommodation, venue). Extract times with their local time zones, booking references and addresses.
3. `bin/cos context bundle --company NAME` for each company being visited. `bin/cos task list` for open items with them.
4. The CRM for other contacts and open deals in that city worth seeing. Offer them as options, not as bookings.

## Output format

Scheduling:

```
Options for <duration> with <name> (<their city>)   calendar read at <time>
1. <Day date>, <start>-<end> <your zone>  =  <start> <their zone>
2. ...
3. ...
Checked: working hours, <n> min buffer, <notes on travel or tight days>

Draft message - NOT SENT
<short message offering 2-3 options, each with both time zones>

Needs you: send the options, or pick one and I will prepare the invitation for your approval?
```

Travel:

```
Trip: <city>, <dates>
Itinerary by day (local times, zone stated)
- <time> <item> - <address> - <booking ref> (source)
Gaps and risks: <tight connections, missing bookings, clashes>
Meetings and prep status
Worth adding while there (optional): <contact, company, reason>
To do before you go: [T-0000] ...
```

## Quality checks

- Every time shows its time zone. Cross-zone options show both local times.
- The calendar was read in this run and the read time is shown.
- Daylight saving differences are handled by `bin/cos slots`, not by mental arithmetic.
- No option overlaps an existing event or its buffer.
- Travel details are copied from confirmations with references. Anything not found is listed as missing, not assumed.

## Permitted actions

- Read from connected systems. Read and write local state.
- Draft the scheduling message (`gmail_draft`, `slack_draft`) and prepare an invitation proposal (`calendar_proposal`).
- Sending the message needs approval. Creating, sending or changing a calendar invitation (`calendar_invite`, `calendar_event_change`) needs explicit approval for that specific invitation: attendees, time, title and location shown in full first.
- Never book or pay for travel. Never accept or decline invitations on the user's behalf without being asked for that event.

## Completion criteria

- Verified options and a draft message are delivered, with a task in `awaiting_approval`, or
- an approved invitation is confirmed by the calendar's event id and recorded in the ledger, or
- the travel plan is delivered with gaps listed and pre-trip tasks tracked.
