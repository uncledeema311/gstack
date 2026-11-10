#!/bin/bash
# First-run walkthrough on SYNTHETIC data. Touches no live system.
# Run from the workspace root:  bash demo/walkthrough.sh
#
# It plays the state side of one complete flow:
#   meeting context -> evidence-backed prep -> follow-up draft -> proposed CRM note
#   -> tracked next action -> verified persistence in a separate process.
# The prep, email and CRM note shown are the reference outputs in demo/expected/.
# Inside Codex the assistant writes those itself (see docs/FIRST_RUN.md, part B).
set -euo pipefail
cd "$(dirname "$0")/.."

# The demo clock is fixed just after the synthetic meeting so output is repeatable.
export COS_NOW="2026-11-12T00:50:00Z"
COS="bin/cos --demo"
FX="demo/fixtures"
PY="${COS_PYTHON:-python3}"

say() { printf '\n== %s ==\n' "$1"; }
pick() { "$PY" -c 'import json,sys
d=json.load(sys.stdin)
for path in sys.argv[1:]:
    v=d
    for part in path.split("."):
        v=v[int(part)] if isinstance(v,list) else v[part]
    print("  %s: %s" % (path, json.dumps(v) if isinstance(v,(dict,list)) else v))' "$@"; }

say "0. Fresh demo data (synthetic, separate from your real data)"
$COS demo init --reset | pick demo_data_dir reset
$COS now | pick now.local now.abbreviation now.utc_offset

say "1. Meeting context: facts read from the (synthetic) CRM and email, stored with sources"
$COS context add --category people --subject "Priya Raman" --attribute role --value "Chief Financial Officer" \
  --related "Kestrel Ridge Minerals" --source-type hubspot --source-ref "hubspot:contact:demo-ct-901" --verified | pick record.id record.verification
$COS context add --category people --subject "Tom Whitlock" --attribute role --value "Investor Relations Manager" \
  --related "Kestrel Ridge Minerals" --source-type hubspot --source-ref "hubspot:contact:demo-ct-902" --verified | pick record.id
$COS context add --category opportunities --subject "Kestrel Ridge Minerals" --attribute stage --value "Demo scheduled" \
  --source-type hubspot --source-ref "hubspot:deal:demo-deal-1001" --verified | pick record.id record.value
$COS context add --category companies --subject "Kestrel Ridge Minerals" --attribute "stated priority" \
  --value "Reduce manual work on quarterly updates and understand the cost. Board meets 3 December." \
  --source-type gmail --source-ref "gmail:thread:demo-thr-3001" --observed-on 2026-10-29 | pick record.id record.verification

say "2. Evidence-backed preparation (reference output)"
sed -n '1,200p' demo/expected/meeting-prep.md
$COS task add --company "Kestrel Ridge Minerals" --action "Follow up after Kestrel Ridge Minerals meeting" \
  --source-type calendar --source-ref "calendar:event:demo-evt-2001" --priority high \
  --rationale "Board paper deadline makes this week decisive" --suggested-deadline 2026-11-13 | pick task.id task.status task.deadline

say "3. After the meeting: commitments from the (synthetic) transcript become tracked actions"
$COS commitment add --company "Kestrel Ridge Minerals" --who me --to "Priya Raman" \
  --what "Send one-page pricing summary for all three tiers" --quote "I will send you a one-page pricing summary for all three by Friday" \
  --source-type transcript --source-ref "fathom:recording:demo-rec-7001@00:22" --verified --due 2026-11-13 --priority high \
  --rationale "Priya needs a number before the board paper is due" | pick task.id task.owner task.deadline commitment.id
$COS commitment add --company "Kestrel Ridge Minerals" --who "Tom Whitlock" --to Nic \
  --what "Send next year's shareholder communications calendar" \
  --source-type transcript --source-ref "fathom:recording:demo-rec-7001@00:26" --verified --suggested-due 2026-11-17 | pick task.id task.status task.waiting_on task.deadline
$COS commitment add --company "Kestrel Ridge Minerals" --who me --to "Priya Raman" \
  --what "Propose times for a 30 minute call in the week of 16 November" \
  --source-type transcript --source-ref "fathom:recording:demo-rec-7001@00:40" --verified --due 2026-11-13 --priority high | pick task.id task.deadline

say "4. Follow-up draft: planned, saved as a draft (MOCKED connector), confirmed with the draft id"
sed -n '1,200p' demo/expected/followup-email.md
PLAN=$($COS action plan --type gmail_draft --target "priya.raman@kestrelridge.example.com" \
  --summary "Follow-up after 12 Nov walkthrough" --task T-0002 --fingerprint "2026-11-12")
echo "$PLAN" | pick proceed reason action.key
KEY=$(echo "$PLAN" | "$PY" -c 'import json,sys; print(json.load(sys.stdin)["action"]["key"])')
echo "  (mocked) Gmail draft created, id demo-draft-0001"
$COS action confirm "$KEY" --system-ref "gmail:draft:demo-draft-0001 (MOCKED)" | pick action.status action.system_ref
$COS task update T-0002 --status awaiting_approval --note "Draft ready for review" | pick task.id task.status

say "5. Retry safety: planning the same draft again does not create a second one"
$COS action plan --type gmail_draft --target "priya.raman@kestrelridge.example.com" \
  --summary "Follow-up after 12 Nov walkthrough" --task T-0002 --fingerprint "2026-11-12" | pick proceed reason

say "6. Approval boundary: sending without approval is refused (exit code 5 is the expected result)"
set +e
$COS action plan --type email_send --target "priya.raman@kestrelridge.example.com" --summary "Send follow-up" --task T-0002 | pick ok exit_code error
set -e

say "7. Proposed CRM note: recorded as a proposal, NOT written to the CRM"
sed -n '1,200p' demo/expected/crm-note.md
$COS action plan --type crm_note_draft --target "hubspot:deal:demo-deal-1001" --summary "Proposed note for 12 Nov walkthrough" \
  --task T-0001 --fingerprint "2026-11-12" | pick proceed action.type action.status

say "8. Times for the follow-up call: early afternoon Perth time as Priya asked, buffers applied"
$COS slots --from 2026-11-16 --days 5 --busy-file "$FX/calendar_busy.json" --calendar-checked-at "2026-11-12T00:49:00Z" \
  --duration 30 --attendee-tz Australia/Perth --attendee-window 13:00-15:00 --attendee-hours-only --limit 3 \
  | "$PY" -c 'import json,sys
d=json.load(sys.stdin)
print("  availability_verified:", d["availability_verified"], "| buffer:", d["buffer_minutes"], "min")
for s in d["slots"]:
    print("  %s %s Melbourne (%s)  =  %s Perth (%s)" % (s["weekday"], s["start"][:16], s["utc_offset"], s["attendees"][0]["start"][11:16], s["attendees"][0]["utc_offset"]))'

say "9. Verified persistence: a separate process reads everything back from disk"
$COS task list | "$PY" -c 'import json,sys
d=json.load(sys.stdin)
for t in d["tasks"]:
    due=t["deadline"]
    label=("deadline " if due["kind"]=="explicit" else "suggested deadline ")+due["date"]
    print("  %s [%s] %s: %s (%s) <- %s" % (t["id"], t["status"], t["owner"], t["action"], label, t["source"]["ref"]))'
$COS action list | "$PY" -c 'import json,sys
for a in json.load(sys.stdin)["actions"]:
    print("  action %s: %s -> %s %s" % (a["type"], a["target"], a["status"], a["system_ref"] or ""))'
$COS context bundle --company "Kestrel Ridge Minerals" | "$PY" -c 'import json,sys
d=json.load(sys.stdin)
n=sum(len(v) for v in d["sections"].values())
print("  context for Kestrel Ridge Minerals: %d facts, %d open tasks" % (n, len(d["open_tasks"])))
for line in d["advice"]: print("  advice:", line)'

printf '\nWalkthrough complete. Nothing left this computer. Demo data is in data-demo/.\n'
