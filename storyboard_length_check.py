#!/usr/bin/env python3
"""Project the runtime of a location storyboard and flag scene creep.

Why: a 20 minute plan keeps landing at 30 minutes because every scene grows a
little. This script turns a markdown storyboard into a per-scene time table so
the overrun is visible while the storyboard is still being written, not in the
edit.

Storyboard format (markdown, one heading per scene):

    ## Scene 3 - Old Town square
    Budget: 1:30                     <- optional per-scene target (m:ss or 90s)
    Location: Piata Sfatului, morning
    VO: Spoken words go here. Every line tagged VO:, Narration:, Talking head:,
        A-roll: or Dialogue: is counted as spoken words.
    B-roll: drone reveal (12s)       <- silent footage; the (12s) is added as-is
    B-roll: walking shots            <- no duration given: default --broll-default
    Duration: 2:00                   <- optional hard override for the scene
    Estimate: 1:12                   <- written by --annotate; safe to keep on the card

Scenes without any spoken-word tag count every plain paragraph as narration.
Lines that start with a directive (Location:, Shot:, Gear:, Note:, Budget:,
Duration:, B-roll:) are never counted as speech.

Usage:
    python3 storyboard_length_check.py storyboard.md                 # target 20, ceiling 21
    python3 storyboard_length_check.py storyboard.md --annotate      # stamp Estimate: on every card
    python3 storyboard_length_check.py storyboard.md --wpm 145 --max 21

--annotate rewrites the file in place, adding or refreshing an "Estimate: m:ss"
line under each scene heading so every card carries its own length. Reorder the
cards however you like; the cumulative column shows where the ceiling is crossed.

Exit code is 1 when the projection is over --max so it can gate a checklist.
"""

import argparse
import re
import sys

SPEECH_TAGS = ("vo", "narration", "talking head", "a-roll", "dialogue", "pieces to camera", "ptc")
SILENT_TAGS = ("b-roll", "broll", "montage")
DIRECTIVE_TAGS = ("estimate", "location", "shot", "shots", "gear", "note", "notes", "budget", "duration", "music", "sfx", "graphics", "text")
HEADING_RE = re.compile(r"^\s*#{1,6}\s+(.*\S)\s*$")
TAG_RE = re.compile(r"^\s*([A-Za-z][A-Za-z \-]*?)\s*:\s*(.*)$")
PAREN_DURATION_RE = re.compile(r"\((\d+(?::\d{2})?)\s*(s|sec|secs|m|min)?\)")


def parse_duration(text):
    """Return seconds from '1:30', '90', '90s', '2m', '2 min'. None if unparseable."""
    text = text.strip().lower()
    m = re.match(r"^(\d+):(\d{2})$", text)
    if m:
        return int(m.group(1)) * 60 + int(m.group(2))
    m = re.match(r"^(\d+(?:\.\d+)?)\s*(s|sec|secs|seconds)?$", text)
    if m:
        return float(m.group(1))
    m = re.match(r"^(\d+(?:\.\d+)?)\s*(m|min|mins|minutes)$", text)
    if m:
        return float(m.group(1)) * 60
    return None


def fmt(seconds):
    seconds = int(round(seconds))
    return f"{seconds // 60}:{seconds % 60:02d}"


def word_count(text):
    return len(re.findall(r"[A-Za-z0-9'’]+", text))


def parse_storyboard(lines, broll_default):
    scenes = []
    current = None
    for idx, raw in enumerate(lines):
        line = raw.rstrip("\n")
        heading = HEADING_RE.match(line)
        if heading:
            title = heading.group(1)
            # A level-1 heading is the document title, not a scene. Scenes are
            # level 2 or deeper.
            if line.lstrip().startswith("# "):
                continue
            current = {"title": title, "heading_index": idx, "tagged_words": 0, "plain_words": 0,
                       "broll": 0.0, "budget": None, "override": None}
            scenes.append(current)
            continue
        if current is None or not line.strip():
            continue
        tag = TAG_RE.match(line)
        key = tag.group(1).strip().lower() if tag else None
        body = tag.group(2) if tag else line
        if key in SPEECH_TAGS:
            current["tagged_words"] += word_count(body)
        elif key in SILENT_TAGS:
            m = PAREN_DURATION_RE.search(body)
            if m:
                secs = parse_duration(m.group(1) + (m.group(2) or ""))
                current["broll"] += secs if secs is not None else broll_default
            else:
                current["broll"] += broll_default
        elif key == "budget":
            current["budget"] = parse_duration(body)
        elif key == "duration":
            current["override"] = parse_duration(body)
        elif key in DIRECTIVE_TAGS:
            continue
        else:
            # Continuation lines of a tagged block are indented; count them with
            # the tagged words if the scene uses tags, else as plain narration.
            if line.startswith((" ", "\t")) and current["tagged_words"]:
                current["tagged_words"] += word_count(body)
            else:
                current["plain_words"] += word_count(body)
    return scenes


def annotate(path, lines, scenes, estimates):
    """Insert or refresh an 'Estimate: m:ss' line right under each scene heading."""
    out = list(lines)
    # Work from the bottom so earlier indexes stay valid while inserting.
    for sc, est in sorted(zip(scenes, estimates), key=lambda p: p[0]["heading_index"], reverse=True):
        i = sc["heading_index"] + 1
        # Drop an existing Estimate line if it sits within the scene's first few lines.
        j = i
        while j < len(out) and j < i + 4 and out[j].strip():
            if re.match(r"^\s*estimate\s*:", out[j], re.I):
                del out[j]
                break
            j += 1
        out.insert(i, f"Estimate: {fmt(est)}\n")
    with open(path, "w", encoding="utf-8") as fh:
        fh.writelines(out)


def main():
    ap = argparse.ArgumentParser(description="Project storyboard runtime per scene.")
    ap.add_argument("storyboard", help="markdown storyboard file")
    ap.add_argument("--target", type=float, default=20.0, help="target runtime in minutes (default 20)")
    ap.add_argument("--wpm", type=float, default=150.0, help="speaking pace, words per minute (default 150)")
    ap.add_argument("--broll-default", type=float, default=6.0, help="seconds per untimed B-roll line (default 6)")
    ap.add_argument("--max", type=float, default=None, help="hard ceiling in minutes; over this fails (default target + 1)")
    ap.add_argument("--annotate", action="store_true", help="write an 'Estimate: m:ss' line under every scene heading in the file")
    args = ap.parse_args()
    max_minutes = args.max if args.max is not None else args.target + 1

    with open(args.storyboard, encoding="utf-8") as fh:
        lines = fh.readlines()
    scenes = parse_storyboard(lines, args.broll_default)
    if not scenes:
        print("No scenes found. Use one markdown heading per scene, e.g. '## Scene 1 - Airport'.")
        return 2

    target_s = args.target * 60
    even_budget = target_s / len(scenes)
    max_s = max_minutes * 60
    total = 0.0
    rows = []
    for sc in scenes:
        words = sc["tagged_words"] if sc["tagged_words"] else sc["plain_words"]
        speech = words / args.wpm * 60
        projected = sc["override"] if sc["override"] is not None else speech + sc["broll"]
        budget = sc["budget"] if sc["budget"] is not None else even_budget
        total += projected
        rows.append((sc["title"], words, speech, sc["broll"], projected, budget, projected - budget, total))

    if args.annotate:
        annotate(args.storyboard, lines, scenes, [r[4] for r in rows])

    title_w = max(len(r[0]) for r in rows)
    title_w = min(max(title_w, 5), 40)
    header = f"{'Scene':<{title_w}}  {'Words':>5}  {'Speech':>6}  {'B-roll':>6}  {'Total':>6}  {'Budget':>6}  {'Over':>6}  {'Cum':>6}"
    print(header)
    print("-" * len(header))
    crossed = False
    for title, words, speech, broll, projected, budget, over, cum in rows:
        flag = "  <-- trim" if over > max(10, budget * 0.15) else ""
        if cum > max_s and not crossed:
            flag = "  <-- ceiling crossed here" + ("" if not flag else ", trim")
            crossed = True
        sign = "+" if over > 0 else "-"
        print(f"{title[:title_w]:<{title_w}}  {words:>5}  {fmt(speech):>6}  {fmt(broll):>6}  {fmt(projected):>6}  {fmt(budget):>6}  {sign + fmt(abs(over)):>6}  {fmt(cum):>6}{flag}")
    print("-" * len(header))

    print(f"Projected runtime: {fmt(total)}  (target {fmt(target_s)}, ceiling {fmt(max_s)}, {len(scenes)} scenes, {args.wpm:g} wpm)")
    if args.annotate:
        print(f"Wrote Estimate: lines to {args.storyboard}.")
    if total <= max_s:
        note = "" if total <= target_s else f" ({fmt(total - target_s)} past target, still under the ceiling)"
        print(f"PASS: on length{note}.")
        return 0

    excess = total - target_s
    words_to_cut = int(round(excess / 60 * args.wpm))
    print(f"OVER the ceiling by {fmt(total - max_s)}. Cut about {words_to_cut} spoken words, or {fmt(excess)} of B-roll, to land on target.")
    worst = [r for r in sorted(rows, key=lambda r: r[6], reverse=True)[:3] if r[6] > 0]
    if worst:
        print("Scenes furthest over their budget:")
        for title, _, _, _, projected, budget, over, _ in worst:
            print(f"  - {title}: {fmt(projected)} vs {fmt(budget)} budget (+{fmt(over)})")
    return 1


if __name__ == "__main__":
    sys.exit(main())
