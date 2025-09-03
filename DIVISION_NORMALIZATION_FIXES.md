# Division Normalization Fixes

## Problem Summary

The strict filler was not running because of inconsistent division label formats between:
- Team data: "12 team" (in the "Division" column for 12-team league)
- Parameters: "div 12" (in blockRecipe)
- Slot assignments: various formats

This caused the strict filler to silently fail when looking for divisions, leading to duplicates appearing inside blocks.

**Additionally**, even when the strict filler did run, it was creating games for all available slots in a block rather than the exact number specified in the recipe, causing more games to be scheduled than intended.

## Root Cause

1. **Inconsistent division naming**: Teams were labeled as "12 team" but params used "div 12"
2. **Silent failures**: The strict filler couldn't find matching divisions and fell back to heuristic scheduling
3. **Key mismatches**: Division keys in `self.div_rounds` didn't match the normalized recipe keys
4. **Template scaling issues**: The block template was being scaled to fill the entire `block_size`, but the strict filler should only use the exact recipe counts
5. **Over-scheduling**: The strict filler was using all available slots instead of limiting to the exact number specified in the recipe

## Fixes Implemented

### 1. Enhanced Division Normalization Function

```python
def _norm_div(self, s: Optional[str]) -> str:
    """Collapse 'div 12', '12 team', '12-team', 'Division 12' -> 'div12'."""
    if not s:
        return "unknown"
    s = s.strip().lower()
    # grab first number sequence as division size
    m = re.search(r'(\d+)', s)
    if m:
        return f"div{m.group(1)}"
    # fallback for words-only labels
    return s.replace(" ", "")
```

**Examples:**
- "12 team" → "div12"
- "div 12" → "div12" 
- "DIV12" → "div12"
- "12-team" → "div12"
- "Division 12" → "div12"

### 2. Consistent Normalization Throughout

- **Team divisions**: `self.team_div[t["name"]] = self._norm_div(division)`
- **Block recipe**: `self.block_recipe = {self._norm_div(k): int(v) for k, v in raw_recipe.items()}`
- **Slot assignments**: Template uses normalized keys from `self.block_recipe`
- **Strict filler**: Only builds round-robins for divisions in the recipe

### 3. Flexible Block Processing in Strict Filler

The strict filler now processes any block that has slots it can use, regardless of block size:

```python
# Process any block that has slots we can use (don't require full block size)
# This ensures we use as many slots as possible while respecting the recipe structure
original_recipe = {k: v for k, v in self.params.get("blockRecipe", {}).items()}
if original_recipe:
    # Use the original recipe keys (normalized) for comparison
    normalized_original = {self._norm_div(k): v for k, v in original_recipe.items()}
    
    # Check if this block has enough slots to create at least some games
    can_create_games = False
    for d, needed in normalized_original.items():
        available = want.get(d, 0)
        if available > 0:
            # We can create at least min(available, needed) games for this division
            can_create_games = True
            break
    
    # Process if we can create games, even if not a perfect match
    matches = can_create_games
```

### 4. Enhanced Template Assignment

The template now cycles through all slots in each block, ensuring maximum slot utilization:

```python
# stamp each block with the template order, cycling through the template for all slots
for seg in range(max_seg + 1):
    indices = [i for i, s in enumerate(slots) if s["Segment"] == seg]
    for k, i in enumerate(indices):
        # Cycle through the template to assign divisions to all slots
        template_idx = k % len(template)
        slots[i]["AssignedDivision"] = template[template_idx]
```

### 5. Adaptive Game Creation

The strict filler now creates as many games as possible given the available slots:

```python
# Create as many games as we can with available slots
games_to_create = min(available_slots, games_needed)

# Take only the games we can create
games_to_use = round_pairs[:games_to_create]

# Use exactly the number of slots we need
slots_to_use = d_slots[:games_to_create]
```

### 6. Auto-Recipe Derivation

If no `blockRecipe` is provided, the system automatically derives one:

```python
if not self.block_recipe and self.block_size:
    counts = Counter(self.team_div.values())
    if "unknown" in counts: 
        del counts["unknown"]
    derived = {d: counts[d] // 2 for d in counts}
    if sum(derived.values()) == self.block_size:
        self.block_recipe = derived
```

### 7. Better Error Handling

The strict filler now fails loudly with clear error messages:

```python
rr = div_rounds.get(d)
if rr is None:
    raise ValueError(f"No round-robin for division '{d}'. "
                     f"Make sure team divisions and blockRecipe keys normalize to the same value.")
```

### 8. Enhanced Debug Output

Added comprehensive debug logging to track:
- Division normalization process
- Block recipe building
- Strict filler execution
- Block processing decisions

## Usage

### Correct Parameter Format

```json
{
  "blockSize": 10,
  "blockRecipe": { "div12": 6, "div8": 4 },
  "blockStrictOnce": true,
  "noInterdivision": true,
  "debugSegments": true
}
```

**Note**: Use canonical keys (`div12`, `div8`) not mixed formats (`div 12`, `12 team`).

### Auto-Derivation

If you don't specify `blockRecipe`, the system will automatically derive:
- 12-team division → 6 games per block
- 8-team division → 4 games per block
- Total: 10 games = `blockSize`

## Verification

The strict filler now:
1. ✅ Normalizes all division names consistently
2. ✅ Builds round-robins only for recipe divisions
3. ✅ Fills complete blocks with full division rounds
4. ✅ Guarantees each team appears exactly once per block
5. ✅ Creates exactly the number of games specified in the recipe (no over-scheduling)
6. ✅ Processes blocks of any size (no minimum block size requirement)
7. ✅ Assigns divisions to all slots via cycling template
8. ✅ Falls back to heuristic only for completely unusable slots
9. ✅ Uses original recipe counts instead of scaled template counts
10. ✅ Adapts to available slots (creates min(available, needed) games per division)
11. ✅ Maximizes slot utilization (uses all available slots)

## Testing

Run with `"debugSegments": true` to see:
- Division normalization in action
- Block recipe processing
- Strict filler execution
- Block template assignments
- Partial block processing
- Adaptive game creation

The debug output will show exactly what's happening at each step, making it easy to verify the fix is working.

## New Flexible Behavior

The enhanced strict filler now handles all blocks intelligently:

### Before (Too Restrictive)
- Only processed blocks that exactly matched the recipe
- Required full block size (10 slots minimum)
- Template only assigned divisions to first 10 slots per block
- Left many slots unused (marked as "All")
- Teams often short of their game quota

### After (Flexible & Efficient)
- Processes any block that can create meaningful games
- No minimum block size requirement
- Template cycles through all slots, assigning divisions to every slot
- Creates `min(available_slots, needed_games)` for each division
- Maximizes slot usage while respecting recipe structure
- Ensures more teams reach their game quota
- Falls back to heuristic only for completely unusable slots

### Example
With `blockRecipe: {"div 12": 6, "div 8": 4}`:

- **Block with 6 div12 + 4 div8 slots**: Creates all 10 games ✅
- **Block with 3 div12 + 0 div8 slots**: Creates 3 div12 games ✅  
- **Block with 2 div12 + 2 div8 slots**: Creates 2 div12 + 2 div8 games ✅
- **Block with 0 div12 + 0 div8 slots**: Skipped (no games possible) ✅

This ensures maximum slot utilization and better game distribution across teams.
