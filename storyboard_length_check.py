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

Scenes without any spoken-word tag count every plain paragraph as narration.
Lines that start with a directive (Location:, Shot:, Gear:, Note:, Budget:,
Duration:, B-roll:) are never counted as speech.

Usage:
    python3 storyboard_length_check.py storyboard.md --target 20
    python3 storyboard_length_check.py storyboard.md --target 20 --wpm 145

Exit code is 1 when the projection is over target so it can gate a checklist.
"""

import argparse
import re
import sys

SPEECH_TAGS = ("vo", "narration", "talking head", "a-roll", "dialogue", "pieces to camera", "ptc")
SILENT_TAGS = ("b-roll", "broll", "montage")
DIRECTIVE_TAGS = ("location", "shot", "shots", "gear", "note", "notes", "budget", "duration", "music", "sfx", "graphics", "text")
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
    for raw in lines:
        line = raw.rstrip("\n")
        heading = HEADING_RE.match(line)
        if heading:
            title = heading.group(1)
            # A level-1 heading is the document title, not a scene. Scenes are
            # level 2 or deeper.
            if line.lstrip().startswith("# "):
                continue
            current = {"title": title, "words": 0, "tagged_words": 0, "plain_words": 0,
                       "broll": 0.0, "budget": None, "override": None, "lines": []}
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


def main():
    ap = argparse.ArgumentParser(description="Project storyboard runtime per scene.")
    ap.add_argument("storyboard", help="markdown storyboard file")
    ap.add_argument("--target", type=float, default=20.0, help="target runtime in minutes (default 20)")
    ap.add_argument("--wpm", type=float, default=150.0, help="speaking pace, words per minute (default 150)")
    ap.add_argument("--broll-default", type=float, default=6.0, help="seconds per untimed B-roll line (default 6)")
    ap.add_argument("--tolerance", type=float, default=5.0, help="percent over target that still passes (default 5)")
    args = ap.parse_args()

    with open(args.storyboard, encoding="utf-8") as fh:
        scenes = parse_storyboard(fh.readlines(), args.broll_default)
    if not scenes:
        print("No scenes found. Use one markdown heading per scene, e.g. '## Scene 1 - Airport'.")
        return 2

    target_s = args.target * 60
    even_budget = target_s / len(scenes)
    total = 0.0
    rows = []
    for sc in scenes:
        words = sc["tagged_words"] if sc["tagged_words"] else sc["plain_words"]
        speech = words / args.wpm * 60
        projected = sc["override"] if sc["override"] is not None else speech + sc["broll"]
        budget = sc["budget"] if sc["budget"] is not None else even_budget
        total += projected
        rows.append((sc["title"], words, speech, sc["broll"], projected, budget, projected - budget))

    title_w = max(len(r[0]) for r in rows)
    title_w = min(max(title_w, 5), 40)
    header = f"{'Scene':<{title_w}}  {'Words':>5}  {'Speech':>6}  {'B-roll':>6}  {'Total':>6}  {'Budget':>6}  {'Over':>6}"
    print(header)
    print("-" * len(header))
    for title, words, speech, broll, projected, budget, over in rows:
        flag = "  <-- trim" if over > max(10, budget * 0.15) else ""
        sign = "+" if over > 0 else "-"
        print(f"{title[:title_w]:<{title_w}}  {words:>5}  {fmt(speech):>6}  {fmt(broll):>6}  {fmt(projected):>6}  {fmt(budget):>6}  {sign + fmt(abs(over)):>6}{flag}")
    print("-" * len(header))

    limit = target_s * (1 + args.tolerance / 100)
    print(f"Projected runtime: {fmt(total)}  (target {fmt(target_s)}, pass limit {fmt(limit)}, {len(scenes)} scenes, {args.wpm:g} wpm)")
    if total <= limit:
        print("PASS: on length.")
        return 0

    excess = total - target_s
    words_to_cut = int(round(excess / 60 * args.wpm))
    print(f"OVER by {fmt(excess)}. Cut about {words_to_cut} spoken words, or {fmt(excess)} of B-roll, to land on target.")
    worst = sorted(rows, key=lambda r: r[6], reverse=True)[:3]
    print("Scenes furthest over their budget:")
    for title, _, _, _, projected, budget, over in worst:
        if over > 0:
            print(f"  - {title}: {fmt(projected)} vs {fmt(budget)} budget (+{fmt(over)})")
    return 1


if __name__ == "__main__":
    sys.exit(main())
