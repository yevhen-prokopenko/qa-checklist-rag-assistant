"""Reset the demo to a clean state so the FULL scenario (see
../04_Demo_Scenario.md) can be run again from scratch — including the
write-first gate: the demo subtask must come back truly EMPTY, so the next
run exercises "empty -> gate blocks -> tester writes checklist -> generate ->
apply" end to end, not just the generate/apply half.

Three kinds of state accumulate during a demo run:
  1. Knowledge base (pgvector): /apply-to-jira writes the final checklist back
     into the store (self-learning). Left as-is, the next run would retrieve
     those added rows and drift.
  2. Jira comments: each Apply posts a comment on the demo issue; they pile up.
  3. Demo subtask description: the tester (or a prior run) fills in a
     checklist. For a full-cycle re-test it must go back to empty.

What this does:
  - Rebuilds the knowledge base from data/knowledge/*.json (via ingest, which
    truncates first) -> back to exactly the original 10 tasks.
  - Deletes only the assistant's own comments (marker below) from the demo
    issue(s) and their subtasks — never touches human comments.
  - Wipes the description of the demo subtask(s) (subtasks of the given
    parent issues) back to empty, so checklist_parser finds nothing and the
    write-first gate triggers on the next run.

    CAUTION: this targets the SUBTASKS of whatever --issues you pass. The
    default (KAN-11) is safe — its only subtask is KAN-22, the demo probe.
    Do NOT pass knowledge-base parents (KAN-1..KAN-10) unless you actually
    want their Jira subtask checklists wiped too (the vector DB itself is
    unaffected either way, since ingest reads local JSON, not Jira).

Usage:
    python reset_demo.py                     # full reset (KB + comments + demo checklist wipe)
    python reset_demo.py --no-jira            # KB rebuild only (skip Jira)
    python reset_demo.py --keep-checklist     # reset KB + comments, but keep the demo checklist text
    python reset_demo.py --issues KAN-11 KAN-3
"""
import sys
import ingest
import jira_client
import db

ASSISTANT_MARKER = "QA Checklist Assistant"  # matches comments api.py posts
DEFAULT_ISSUES = ["KAN-11"]


def clean_jira_comments(issue_keys):
    keys_to_clean = []
    for key in issue_keys:
        keys_to_clean.append(key)
        try:
            iss = jira_client.get_issue(key)
            keys_to_clean.extend(iss.get("subtask_keys", []))
        except Exception as e:
            print(f"  {key}: could not fetch subtasks ({e})")

    # Dedup keys
    seen = set()
    unique_keys = [k for k in keys_to_clean if not (k in seen or seen.add(k))]

    for key in unique_keys:
        try:
            comments = jira_client.get_comments(key)
        except Exception as e:
            print(f"  {key}: could not read comments ({e})")
            continue
        removed = 0
        for c in comments:
            body = c.get("body", "")
            if isinstance(body, str) and ASSISTANT_MARKER in body:
                try:
                    jira_client.delete_comment(key, c["id"])
                    removed += 1
                except Exception as e:
                    print(f"  {key}: failed to delete comment {c.get('id')} ({e})")
        print(f"  {key}: removed {removed} assistant comment(s)")


def wipe_demo_checklists(parent_keys):
    """Empty the description of every subtask under the given parents, so the
    write-first gate has something to actually block on the next run."""
    for parent_key in parent_keys:
        try:
            parent = jira_client.get_issue(parent_key)
        except Exception as e:
            print(f"  {parent_key}: could not fetch (skip) ({e})")
            continue
        subtasks = parent.get("subtask_keys", [])
        if not subtasks:
            print(f"  {parent_key}: no subtasks found")
            continue
        for sub_key in subtasks:
            try:
                jira_client.update_description(sub_key, "")
                print(f"  {sub_key}: description wiped (now empty)")
            except Exception as e:
                print(f"  {sub_key}: failed to wipe description ({e})")


def main(argv):
    do_jira = "--no-jira" not in argv
    keep_checklist = "--keep-checklist" in argv
    issues = DEFAULT_ISSUES
    if "--issues" in argv:
        issues = argv[argv.index("--issues") + 1:]

    print("1) Rebuilding knowledge base...")
    ingest.main()
    conn = db.connect()
    print(f"   knowledge rows now: {db.count_knowledge(conn)}")
    conn.close()

    if do_jira:
        print("2) Cleaning assistant comments in Jira...")
        clean_jira_comments(issues)
        if keep_checklist:
            print("3) Skipping demo checklist wipe (--keep-checklist).")
        else:
            print("3) Wiping demo subtask checklist (full-cycle re-test)...")
            wipe_demo_checklists(issues)
    else:
        print("2) Skipping Jira cleanup (--no-jira).")

    print("Done. Demo is reset — ready for a fresh full-cycle run.")


if __name__ == "__main__":
    main(sys.argv[1:])
