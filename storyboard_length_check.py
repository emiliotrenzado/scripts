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
    Wide: the thought I say from the square, then a pause   <- one thought
    Close: the second thought, new angle                    <- one thought
    Drone: the third thought over the rooftops               <- one thought
    VO: Fully scripted lines are counted as spoken words instead.
    B-roll: drone reveal (12s)       <- silent footage; the (12s) is added as-is
    B-roll: walking shots            <- no duration given: default --broll-default
    Duration: 2:00                   <- optional hard override for the scene
    Raw: 14:30                       <- raw footage shot for this card
    Actual: 3:10                     <- what it cut down to in the finished edit
    Estimate: 1:12                   <- written by --annotate; safe to keep on the card

A card is one location. Each camera view on it is one thought: you say one
thing from that angle, pause, and move to the next view. Lines tagged with a
camera view (Wide:, Medium:, Close:, Drone:, Gimbal:, Handheld:, POV:, Selfie:,
Walk:, Insert:, Detail:, Static:, or a generic Thought:) count as one thought
each, at --thought seconds (default 25). A long scripted thought is counted by
its words instead when that comes out longer.

How a card's length is decided, first match wins:
    Actual: (the finished edit)  >  Duration: (your gut number)  >
    Raw: x ratio (raw footage scaled by your cut ratio)  >
    thoughts x --thought + B-roll  >  spoken words + B-roll.

Both --thought and the cut ratio are what past videos taught you. --calibrate
also reports seconds per thought from cards that carry Actual: and thoughts.
The cut ratio is what past videos taught you. Put Raw: and Actual: on the cards
of a finished video and run --calibrate to see the ratio per card and overall.
Pass --ratio 0.22 (or let the file's own Raw/Actual pairs supply it) and any new
card with only a Raw: line is estimated as raw x ratio.

Scenes without any spoken-word tag count every plain paragraph as narration.
Lines that start with a directive (Location:, Shot:, Gear:, Note:, Budget:,
Duration:, B-roll:) are never counted as speech.

Usage:
    python3 storyboard_length_check.py storyboard.md                 # target 20, ceiling 21
    python3 storyboard_length_check.py storyboard.md --annotate      # stamp Estimate: on every card
    python3 storyboard_length_check.py storyboard.md --wpm 145 --max 21
    python3 storyboard_length_check.py last_video.md --calibrate       # raw vs actual per card
    python3 storyboard_length_check.py storyboard.md --ratio 0.22      # raw footage x ratio

--annotate rewrites the file in place, adding or refreshing an "Estimate: m:ss"
line under each scene heading so every card carries its own length. Reorder the
cards however you like; the cumulative column shows where the ceiling is crossed.

Exit code is 1 when the projection is over --max so it can gate a checklist.
"""

import argparse
import re
import sys

SPEECH_TAGS = ("vo", "narration", "talking head", "a-roll", "dialogue", "pieces to camera", "ptc")
THOUGHT_TAGS = ("thought", "beat", "wide", "medium", "med", "close", "close-up", "closeup", "cu", "mcu", "ecu",
                "drone", "gimbal", "handheld", "tripod", "static", "pov", "selfie", "walk", "walk and talk",
                "walk-and-talk", "insert", "detail", "ots", "over the shoulder", "pan", "tilt", "dolly", "slider")
SILENT_TAGS = ("b-roll", "broll", "montage")
DIRECTIVE_TAGS = ("estimate", "raw", "actual", "location", "shot", "shots", "gear", "note", "notes", "budget", "duration", "music", "sfx", "graphics", "text")
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
                       "broll": 0.0, "budget": None, "override": None, "raw": None, "actual": None,
                       "thoughts": []}
            scenes.append(current)
            continue
        if current is None or not line.strip():
            continue
        tag = TAG_RE.match(line)
        key = tag.group(1).strip().lower() if tag else None
        body = tag.group(2) if tag else line
        if key in THOUGHT_TAGS:
            current["thoughts"].append(word_count(body))
        elif key in SPEECH_TAGS:
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
        elif key == "raw":
            current["raw"] = parse_duration(body)
        elif key == "actual":
            current["actual"] = parse_duration(body)
        elif key in DIRECTIVE_TAGS:
            continue
        else:
            # Continuation lines of a tagged block are indented; count them with
            # the tagged words if the scene uses tags, else as plain narration.
            if line.startswith((" ", "\t")) and current["thoughts"]:
                current["thoughts"][-1] += word_count(body)
            elif line.startswith((" ", "\t")) and current["tagged_words"]:
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


def cut_ratio(scenes):
    """Overall final/raw ratio from every card that has both numbers, or None."""
    raw = sum(sc["raw"] for sc in scenes if sc["raw"] and sc["actual"] is not None)
    actual = sum(sc["actual"] for sc in scenes if sc["raw"] and sc["actual"] is not None)
    return actual / raw if raw else None


def thought_seconds(scenes):
    """Average finished seconds per thought from cards with Actual: and thoughts, or None."""
    cards = [sc for sc in scenes if sc["actual"] is not None and sc["thoughts"]]
    n = sum(len(sc["thoughts"]) for sc in cards)
    if not n:
        return None
    return sum(sc["actual"] - sc["broll"] for sc in cards) / n


def calibrate(scenes):
    secs = thought_seconds(scenes)
    if secs:
        cards = [sc for sc in scenes if sc["actual"] is not None and sc["thoughts"]]
        n = sum(len(sc["thoughts"]) for sc in cards)
        print(f"Thoughts: {n} across {len(cards)} finished cards, {secs:.0f}s each after the cut (B-roll excluded). "
              f"Use --thought {secs:.0f} on the next storyboard. At that pace 20:00 holds about {int(20 * 60 / secs)} thoughts.")
        print()

    pairs = [sc for sc in scenes if sc["raw"] and sc["actual"] is not None]
    if not pairs:
        if secs:
            return 0
        print("No cards with both Raw: and Actual: lines. Add them to a finished video's cards and re-run.")
        return 2
    title_w = min(max(max(len(sc["title"]) for sc in pairs), 5), 40)
    header = f"{'Scene':<{title_w}}  {'Raw':>6}  {'Actual':>6}  {'Kept':>5}"
    print(header)
    print("-" * len(header))
    for sc in pairs:
        print(f"{sc['title'][:title_w]:<{title_w}}  {fmt(sc['raw']):>6}  {fmt(sc['actual']):>6}  {sc['actual'] / sc['raw'] * 100:>4.0f}%")
    print("-" * len(header))
    raw = sum(sc["raw"] for sc in pairs)
    actual = sum(sc["actual"] for sc in pairs)
    ratio = actual / raw
    ratios = sorted(sc["actual"] / sc["raw"] for sc in pairs)
    print(f"Overall: {fmt(raw)} raw -> {fmt(actual)} final, ratio {ratio:.2f} (kept {ratio * 100:.0f}%).")
    print(f"Per-card range: {ratios[0] * 100:.0f}% to {ratios[-1] * 100:.0f}%.")
    print(f"Rule of thumb: {fmt(60 / ratio)} of raw footage per finished minute, so a 20 minute video needs about {fmt(20 * 60 / ratio)} raw.")
    print(f"Use it on the next storyboard with --ratio {ratio:.2f}, or keep these cards in the same file and it is picked up automatically.")
    return 0


def main():
    ap = argparse.ArgumentParser(description="Project storyboard runtime per scene.")
    ap.add_argument("storyboard", help="markdown storyboard file")
    ap.add_argument("--target", type=float, default=20.0, help="target runtime in minutes (default 20)")
    ap.add_argument("--wpm", type=float, default=150.0, help="speaking pace, words per minute (default 150)")
    ap.add_argument("--broll-default", type=float, default=6.0, help="seconds per untimed B-roll line (default 6)")
    ap.add_argument("--max", type=float, default=None, help="hard ceiling in minutes; over this fails (default target + 1)")
    ap.add_argument("--annotate", action="store_true", help="write an 'Estimate: m:ss' line under every scene heading in the file")
    ap.add_argument("--ratio", type=float, default=None, help="final/raw cut ratio for cards that only have a Raw: line (default: derived from the file's Raw/Actual pairs)")
    ap.add_argument("--thought", type=float, default=None, help="finished seconds per thought (camera view) on a card (default 25, or derived from the file's Actual: cards)")
    ap.add_argument("--calibrate", action="store_true", help="report Raw: vs Actual: per card and the overall cut ratio, then exit")
    args = ap.parse_args()
    max_minutes = args.max if args.max is not None else args.target + 1

    with open(args.storyboard, encoding="utf-8") as fh:
        lines = fh.readlines()
    scenes = parse_storyboard(lines, args.broll_default)
    if not scenes:
        print("No scenes found. Use one markdown heading per scene, e.g. '## Scene 1 - Airport'.")
        return 2
    if args.calibrate:
        return calibrate(scenes)
    ratio = args.ratio if args.ratio is not None else cut_ratio(scenes)
    per_thought = args.thought if args.thought is not None else (thought_seconds(scenes) or 25.0)

    target_s = args.target * 60
    even_budget = target_s / len(scenes)
    max_s = max_minutes * 60
    total = 0.0
    rows = []
    for sc in scenes:
        words = sc["tagged_words"] if sc["tagged_words"] else sc["plain_words"]
        words += sum(sc["thoughts"])
        speech = words / args.wpm * 60
        if sc["thoughts"]:
            # Each thought is at least --thought seconds; a long scripted one is counted by its words.
            speech = sum(max(per_thought, w / args.wpm * 60) for w in sc["thoughts"]) + (
                (sc["tagged_words"] or 0) / args.wpm * 60)
        if sc["actual"] is not None:
            projected = sc["actual"]
        elif sc["override"] is not None:
            projected = sc["override"]
        elif sc["raw"] and ratio:
            projected = sc["raw"] * ratio
        else:
            projected = speech + sc["broll"]
        budget = sc["budget"] if sc["budget"] is not None else even_budget
        total += projected
        rows.append((sc["title"], len(sc["thoughts"]), speech, sc["broll"], projected, budget, projected - budget, total))

    if args.annotate:
        annotate(args.storyboard, lines, scenes, [r[4] for r in rows])

    title_w = max(len(r[0]) for r in rows)
    title_w = min(max(title_w, 5), 40)
    header = f"{'Scene':<{title_w}}  {'Thgts':>5}  {'Speech':>6}  {'B-roll':>6}  {'Total':>6}  {'Budget':>6}  {'Over':>6}  {'Cum':>6}"
    print(header)
    print("-" * len(header))
    crossed = False
    for title, thoughts, speech, broll, projected, budget, over, cum in rows:
        flag = "  <-- trim" if over > max(10, budget * 0.15) else ""
        if cum > max_s and not crossed:
            flag = "  <-- ceiling crossed here" + ("" if not flag else ", trim")
            crossed = True
        sign = "+" if over > 0 else "-"
        print(f"{title[:title_w]:<{title_w}}  {thoughts:>5}  {fmt(speech):>6}  {fmt(broll):>6}  {fmt(projected):>6}  {fmt(budget):>6}  {sign + fmt(abs(over)):>6}  {fmt(cum):>6}{flag}")
    print("-" * len(header))

    if len(scenes) > 10:
        print(f"Scene count check: {len(scenes)} scenes at {fmt(target_s)} is {fmt(even_budget)} each. Location scenes tend to run about 2:00, so this count would land near {fmt(len(scenes) * 120)}. Merge or cut cards rather than trimming all of them.")
    total_thoughts = sum(len(sc["thoughts"]) for sc in scenes)
    if total_thoughts:
        print(f"Thoughts: {total_thoughts} at {per_thought:.0f}s each. {fmt(target_s)} holds about {int(target_s / per_thought)} at that pace.")
    ratio_note = f", cut ratio {ratio:.2f}" if ratio else ""
    print(f"Projected runtime: {fmt(total)}  (target {fmt(target_s)}, ceiling {fmt(max_s)}, {len(scenes)} scenes, {args.wpm:g} wpm{ratio_note})")
    raw_only = [sc["title"] for sc in scenes if sc["raw"] and sc["actual"] is None and sc["override"] is None and not ratio]
    if raw_only:
        print(f"Cards with Raw: but no ratio to apply (pass --ratio or add Raw/Actual pairs): {', '.join(raw_only)}")
    if args.annotate:
        print(f"Wrote Estimate: lines to {args.storyboard}.")
    if total <= max_s:
        note = "" if total <= target_s else f" ({fmt(total - target_s)} past target, still under the ceiling)"
        print(f"PASS: on length{note}.")
        return 0

    excess = total - target_s
    words_to_cut = int(round(excess / 60 * args.wpm))
    if total_thoughts:
        print(f"OVER the ceiling by {fmt(total - max_s)}. Drop about {int(excess / per_thought + 0.999)} thoughts, or {fmt(excess)} of B-roll, to land on target.")
    else:
        print(f"OVER the ceiling by {fmt(total - max_s)}. Cut about {words_to_cut} spoken words, or {fmt(excess)} of B-roll, to land on target.")
    worst = [r for r in sorted(rows, key=lambda r: r[6], reverse=True)[:3] if r[6] > 0]
    if worst:
        print("Scenes furthest over their budget:")
        for title, _, _, _, projected, budget, over, _ in worst:
            print(f"  - {title}: {fmt(projected)} vs {fmt(budget)} budget (+{fmt(over)})")
    return 1


if __name__ == "__main__":
    sys.exit(main())
