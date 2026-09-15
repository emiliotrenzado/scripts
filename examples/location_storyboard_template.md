# Location storyboard template (20 minute target)

Rules that keep the runtime honest:

- Decide the scene count first, then divide the target by that count. Eight scenes at 20 minutes is 2:30 each, including B-roll.
- Give every scene a `Budget:` line before writing its VO. Write to the budget, not to the location.
- At 150 words per minute, 2:30 of talking is about 375 words. Most scenes need less than that because B-roll eats time silently.
- Time every B-roll line in parentheses. Untimed B-roll is where the extra 10 minutes hides.
- Run `python3 storyboard_length_check.py <file> --annotate` after each pass. It stamps an `Estimate:` line on every card and fails past the 21 minute ceiling (target 20, `--max 21`).
- You cannot know a card's length from raw footage alone, so calibrate. After each edit, put `Raw: 14:30` (footage shot) and `Actual: 3:10` (what it cut to) on every card of that video and run `--calibrate`. It prints the kept percentage per card and overall.
- On the next storyboard, a card with only a `Raw:` line is estimated as raw times that ratio (`--ratio 0.25`, or keep last video's cards in the same file). `Duration:` is your gut number and wins over the ratio. `Actual:` wins over everything.
- Keep the `Estimate:` line on the card when you move it. The cumulative column shows exactly which card pushes the video past 21 minutes, so reorder freely and re-run.

## Scene 1 - Arrival
Budget: 1:30
Location: Airport exit, late afternoon
VO: Twelve months ago I was working out whether early retirement was even possible.
    Today I am landing in a city I could not have pointed to on a map.
B-roll: plane taxi through window (6s)
B-roll: walking out with bag (8s)

## Scene 2 - The apartment
Budget: 2:30
Location: Rental flat, living room
Talking head: What this place costs, what it includes, and why it is cheaper than my old
    parking spot back home.
B-roll: room tour pans (20s)
B-roll: view from balcony (8s)
