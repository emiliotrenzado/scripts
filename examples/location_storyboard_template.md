# Location storyboard template (20 minute target)

Rules that keep the runtime honest:

- Decide the scene count first, then divide the target by that count. Eight scenes at 20 minutes is 2:30 each, including B-roll.
- One location per card. Each camera view on the card is one thought: say one thing from that angle, pause, move to the next view. Tag the line with the view (`Wide:`, `Close:`, `Drone:`, `Gimbal:`, `Selfie:`) and it counts as one thought, about 25 seconds finished until you calibrate.
- The runtime lever is thoughts per card, not words. 20 minutes holds about 45 thoughts at 25 seconds each. Fifteen cards means three thoughts each; eight cards means five or six.
- Give every card a `Budget:` line before listing its thoughts. Write to the budget, not to the location.
- Time every B-roll line in parentheses. Untimed B-roll is where the extra 10 minutes hides.
- Run `python3 storyboard_length_check.py <file> --annotate` after each pass. It stamps an `Estimate:` line on every card and fails past the 21 minute ceiling (target 20, `--max 21`).
- You cannot know a card's length from raw footage alone, so calibrate. After each edit, put `Raw: 14:30` (footage shot) and `Actual: 3:10` (what it cut to) on every card of that video and run `--calibrate`. It prints the kept percentage per card and overall, and your real seconds per thought to use as `--thought`.
- On the next storyboard, a card with only a `Raw:` line is estimated as raw times that ratio (`--ratio 0.25`, or keep last video's cards in the same file). `Duration:` is your gut number and wins over the ratio. `Actual:` wins over everything.
- Keep the `Estimate:` line on the card when you move it. The cumulative column shows exactly which card pushes the video past 21 minutes, so reorder freely and re-run.

## Scene 1 - Arrival
Budget: 1:30
Location: Airport exit, late afternoon
Selfie: twelve months ago I was working out whether early retirement was even possible
Wide: today I am landing in a city I could not have pointed to on a map
B-roll: plane taxi through window (6s)
B-roll: walking out with bag (8s)

## Scene 2 - The apartment
Budget: 2:30
Location: Rental flat, living room
Gimbal: walking in, first impression
Static: what this place costs and what it includes
Close: why it is cheaper than my old parking spot back home
Selfie: the balcony, and the one thing I would change
B-roll: room tour pans (20s)
B-roll: view from balcony (8s)
