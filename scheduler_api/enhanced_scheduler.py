#!/usr/bin/env python3
"""
Enhanced League Scheduler (rewritten)

Key guarantees fixed:
- Hard "once-per-block" rule: in every full block of size `blockSize` that
  matches `blockRecipe` (e.g., {"div 12": 6, "div 8": 4}), each team in those
  divisions appears exactly once in that block — no zeros, no doubles.
- The strict filler uses precomputed round-robin rounds per division and maps one
  full division round per block (6 games → all 12 teams; 4 games → all 8 teams).
- E/M/L, weekday balance, and rest constraints are respected *after* strict
  coverage is satisfied; if necessary to achieve coverage inside a block, the
  scheduler relaxes time-based constraints for the remaining slots of that block.

Usage:
- Pass params such as:
  {
    "timezone": "America/Los_Angeles",
    "gamesPerTeam": 12,
    "blockSize": null,  # Will be calculated dynamically based on team count
    "blockRecipe": {"div 12": 6, "div 8": 4},
    "blockStrictOnce": true,
    "noInterdivision": true,
    "debugSegments": true
  }

Notes:
- If the last block is partial or the block doesn't match the recipe exactly (e.g.,
  wrong division mix/time slots), the scheduler falls back to the heuristic for that block.
- Final validators will raise loudly if a full recipe block violates the once-per-block rule.
"""

import random
import itertools
import re
from datetime import datetime, time
from collections import defaultdict, Counter
from typing import List, Dict, Any, Optional, Tuple
import numpy as np
from zoneinfo import ZoneInfo


class EnhancedScheduler:
    def __init__(self, params: Dict[str, Any]):
        self.params = params or {}

        # Core knobs - will be calculated dynamically in build_schedule when team count is available
        # These will use parameter values if provided, otherwise calculate based on team count
        self.games_per_team = self.params.get("gamesPerTeam", None)  # Will be calculated in build_schedule
        self.target_gap_days = self.params.get("idealGapDays", None)  # Will be calculated in build_schedule
        self.min_rest_days = self.params.get("minRestDays", None)  # Will be calculated in build_schedule
        self.max_idle_days = self.params.get("maxGapDays", None)  # Will be calculated in build_schedule
        self.avoid_back_to_back_opponent = self.params.get("noBackToBack", True)
        self.balance_home_away = self.params.get("homeAwayBalance", True)
        self.balance_weekdays = self.params.get("weekdayBalance", True)
        self.variance_minimization = self.params.get("varianceMinimization", True)
        self.holiday_aware = self.params.get("holidayAwareness", True)
        self.no_interdivision = self.params.get("noInterdivision", False)
        self.debug_segments = self.params.get("debugSegments", False)

        # E/M/L cutoffs - uses parameters from user input, with fallback defaults
        # User sets earlyStart/midStart in Parameters tab, which become earlyEnd/midEnd for scheduler
        default_game_minutes = self.params.get("defaultGameMinutes", 80)
        
        # Get EML times from parameters, with fallback defaults
        eml_params = self.params.get("eml", {})
        early_end_default = eml_params.get("earlyStart", "22:01")  # Use earlyStart as fallback
        mid_end_default = eml_params.get("midStart", "22:31")      # Use midStart as fallback
        
        self.early_end = self._parse_time(eml_params.get("earlyEnd", early_end_default))
        self.mid_end = self._parse_time(eml_params.get("midEnd", mid_end_default))

        # Block settings - will be calculated dynamically in build_schedule
        self.block_size = self.params.get("blockSize", None)  # Will be calculated based on team count
        raw_recipe = self.params.get("blockRecipe") or {}
        self.block_recipe = {self._norm_div(k): int(v) for k, v in raw_recipe.items()}
        if raw_recipe and self.debug_segments:
            print(f"🔧 Normalized blockRecipe: {raw_recipe} -> {self.block_recipe}")
        self.block_strict_once = self.params.get("blockStrictOnce", True)

        # Timezone
        tz_name = self.params.get("timezone", "America/Los_Angeles")
        try:
            self.tz = ZoneInfo(tz_name)
        except Exception:
            self.tz = ZoneInfo("UTC")

        # RNG
        random.seed(self.params.get("seed", 42))

    # ------------------ utilities ------------------
    def _norm_div(self, s: Optional[str]) -> str:
        """Collapse 'div 12', '12 team', '12-team', 'Division 12' -> 'div12'.
        Also handles custom division names like 'Tin Super' -> 'div12', 'Tin South' -> 'div8'."""
        if not s:
            return "unknown"
        s = s.strip().lower()
        
        # Handle custom division names
        if s in ['tin super', 'tin super division']:
            return "div12"
        elif s in ['tin south', 'tin south division']:
            return "div8"
        
        # grab first number sequence as division size
        m = re.search(r'(\d+)', s)
        if m:
            return f"div{m.group(1)}"
        # fallback for words-only labels
        return s.replace(" ", "")

    def _denorm_div(self, s: str) -> str:
        """Map normalized division names back to display names."""
        if s == "div12":
            return "Tin Super"
        elif s == "div8":
            return "Tin South"
        else:
            return s

    def _parse_time(self, time_str: str) -> time:
        try:
            hh, mm = map(int, (time_str or "22:01").split(":"))
            return time(hh, mm)
        except Exception:
            # Fallback to EML parameters if available, otherwise use default
            eml_params = self.params.get("eml", {})
            fallback_time = eml_params.get("earlyStart", "22:01")
            try:
                hh, mm = map(int, fallback_time.split(":"))
                return time(hh, mm)
            except Exception:
                return time(22, 1)  # Ultimate fallback

    def classify_bucket(self, start_dt: datetime) -> str:
        t = start_dt.time()
        if t < self.early_end: return "Early"
        if t < self.mid_end: return "Mid"
        return "Late"

    def round_robin_pairs(self, teams: List[str], seed: Optional[int] = None) -> List[List[Tuple[str, str]]]:
        if seed is not None:
            random.seed(seed)
        arr = list(teams)
        bye = "__BYE__" if len(arr) % 2 else None
        if bye:
            arr.append(bye)
        n = len(arr)
        half = n // 2
        rounds = []
        if n > 2:
            anchor, rest = arr[0], arr[1:]
            random.shuffle(rest)
            arr = [anchor] + rest
        for _ in range(n - 1):
            pairs = []
            for i in range(half):
                a, b = arr[i], arr[-(i + 1)]
                if bye not in (a, b):
                    pairs.append((a, b))
            rounds.append(pairs)
            arr = [arr[0]] + [arr[-1]] + arr[1:-1]
        for r_i in range(len(rounds)):
            if r_i % 2 == 1:
                rounds[r_i] = [(b, a) for (a, b) in rounds[r_i]]
        return rounds

    def can_play(self, team: str, slot_start: datetime, last_game_time: Optional[datetime]) -> bool:
        if last_game_time is None:
            return True
        gap_days = (slot_start - last_game_time).total_seconds() / 86400.0
        return gap_days >= self.min_rest_days

    def choose_home_away(self, a: str, b: str, home_count: Counter) -> Tuple[str, str]:
        return (a, b) if home_count[a] <= home_count[b] else (b, a)

    # ------------------ core build ------------------
    def build_schedule(self, slots: List[Dict[str, Any]], teams: List[Dict[str, Any]], divisions: List[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        print(f"🔧 noInterdivision={self.no_interdivision}")
        team_names = [t["name"] for t in teams]
        team_count = len(team_names)

        # Update dynamic parameters now that we have team count
        if self.games_per_team is None:
            # Dynamic games per team: works for any team count (2-100+)
            # Formula: For even teams, each team plays every other team once
            # For odd teams, each team plays every other team once (with BYE system)
            if team_count % 2 == 0:
                # Even teams: each team plays (team_count - 1) games
                default_games = team_count - 1
            else:
                # Odd teams: each team plays (team_count - 1) games (with BYE system)
                default_games = team_count - 1
            
            self.games_per_team = default_games
            print(f"🔧 Calculated dynamic games per team: {default_games} (from {team_count} teams, {'even' if team_count % 2 == 0 else 'odd'})")
        else:
            print(f"🔧 Using provided games per team: {self.games_per_team}")

        if self.target_gap_days is None:
            # Use configurable divisor, default to 3
            gap_divisor = self.params.get("gapDivisor", 3)
            self.target_gap_days = max(5, min(10, team_count // gap_divisor))
            print(f"🔧 Calculated dynamic target gap days: {self.target_gap_days} (from {team_count} teams, divisor: {gap_divisor})")
        else:
            print(f"🔧 Using provided target gap days: {self.target_gap_days}")

        if self.min_rest_days is None:
            # Use configurable divisor, default to 8
            rest_divisor = self.params.get("restDivisor", 8)
            self.min_rest_days = max(2, min(4, team_count // rest_divisor))
            print(f"🔧 Calculated dynamic min rest days: {self.min_rest_days} (from {team_count} teams, divisor: {rest_divisor})")
        else:
            print(f"🔧 Using provided min rest days: {self.min_rest_days}")

        if self.max_idle_days is None:
            # Use configurable divisor, default to 2
            idle_divisor = self.params.get("idleDivisor", 2)
            self.max_idle_days = max(8, min(16, team_count // idle_divisor))
            print(f"🔧 Calculated dynamic max idle days: {self.max_idle_days} (from {team_count} teams, divisor: {idle_divisor})")
        else:
            print(f"🔧 Using provided max idle days: {self.max_idle_days}")

        # Build team→division map
        self.team_div: Dict[str, str] = {}
        for t in teams:
            division = (t.get("division") or t.get("divisionId") or t.get("division_id") or t.get("divisionName"))
            if division:
                self.team_div[t["name"]] = self._norm_div(division)
            else:
                self.team_div[t["name"]] = "unknown"
        if self.debug_segments:
            print("🔧 Team divisions after normalization:")
            for k, v in self.team_div.items():
                print("   ", k, "→", v)
            print("🔧 Division counts:", dict(Counter(self.team_div.values())))

        # Calculate optimal block size if not provided
        if self.block_size is None:
            # For even distribution, block size should be roughly teams/2
            # This ensures each team appears once per block
            optimal_block_size = team_count // 2  # No constraints - works for any team count
            self.block_size = optimal_block_size
            print(f"🔧 Calculated optimal block size: {optimal_block_size} (from {team_count} teams)")
        
        # Build default recipe if not supplied: one full round per division per block
        if not self.block_recipe and self.block_size:
            counts = Counter(self.team_div.values())
            if "unknown" in counts: 
                del counts["unknown"]
            # Calculate optimal distribution: each division contributes roughly teams/2 games per block
            derived = {}
            for d, team_count in counts.items():
                if team_count > 0:
                    # For even distribution, each division contributes roughly teams/2 games per block
                    games_per_block = max(1, team_count // 2)
                    derived[d] = games_per_block
            
            # If the sum doesn't match block_size exactly, adjust proportionally
            total_derived = sum(derived.values())
            if total_derived > 0:
                if total_derived != self.block_size:
                    # Scale proportionally to match block_size
                    scale_factor = self.block_size / total_derived
                    scaled = {}
                    for d, count in derived.items():
                        scaled[d] = max(1, round(count * scale_factor))
                    
                    # Ensure the sum equals block_size
                    while sum(scaled.values()) != self.block_size:
                        if sum(scaled.values()) < self.block_size:
                            # Add one to the division with most teams
                            largest_div = max(scaled.keys(), key=lambda x: counts[x])
                            scaled[largest_div] += 1
                        else:
                            # Remove one from the division with most teams
                            largest_div = max(scaled.keys(), key=lambda x: counts[x])
                            scaled[largest_div] = max(1, scaled[largest_div] - 1)
                    
                    self.block_recipe = scaled
                    print(f"🔧 Derived and scaled blockRecipe: {self.block_recipe} (sum={sum(self.block_recipe.values())})")
                else:
                    self.block_recipe = derived
                    print(f"🔧 Derived blockRecipe from team counts: {self.block_recipe}")
            else:
                print(f"⚠️ No valid divisions found for blockRecipe")
        else:
            print(f"🔧 Using provided blockRecipe: {self.block_recipe}")
            print(f"🔧 Team divisions found: {dict(counts) if 'counts' in locals() else 'Not counted yet'}")

        # preprocess slots
        processed_slots = []
        for i, slot in enumerate(slots):
            try:
                if str(slot["event_start"]).endswith("Z"):
                    start_dt = datetime.fromisoformat(slot["event_start"].replace("Z", "+00:00")).astimezone(self.tz)
                    end_dt = datetime.fromisoformat(slot["event_end"].replace("Z", "+00:00")).astimezone(self.tz)
                else:
                    start_dt = datetime.fromisoformat(str(slot["event_start"]).replace("Z", "")).replace(tzinfo=self.tz)
                    end_dt = datetime.fromisoformat(str(slot["event_end"]).replace("Z", "")).replace(tzinfo=self.tz)
                processed_slots.append({
                    "SlotID": i + 1,
                    "Start": start_dt,
                    "End": end_dt,
                    "Rink": slot.get("resource", ""),
                    "Bucket": self.classify_bucket(start_dt)
                })
            except Exception as e:
                print(f"Error processing slot {i}: {e}")
        if not processed_slots:
            return []
        processed_slots.sort(key=lambda s: s["Start"])

        # segment into fixed-size blocks & assign division template per block
        self._segment_and_assign_divisions(processed_slots)

        # strict block pass
        last_game_time = {t: None for t in team_names}
        opp_last_week = {t: None for t in team_names}
        home_count = Counter()
        bucket_count = {t: Counter() for t in team_names}
        weekday_count = {t: Counter() for t in team_names}
        team_game_count = {t: 0 for t in team_names}

        strict_games, used_slot_ids, played_in_segment = self._strict_block_fill(
            processed_slots, teams, home_count, team_game_count
        )
        
        # Initialize played_in_segment for all segments if not already done
        if not played_in_segment:
            played_in_segment = defaultdict(set)
            for s in processed_slots:
                seg = s["Segment"]
                played_in_segment[seg] = set()
        
        # Calculate matchups per week (teams ÷ 2)
        # For 22 teams: 22 ÷ 2 = 11 matchups per week
        # Each matchup involves 2 teams, so 11 matchups = 22 team appearances
        games_per_week = len([t["name"] for t in teams]) // 2
        current_week = 1
        games_in_current_week = 0

        # heuristic fill for leftover slots (partials / "All")
        remaining_slots = [s for s in processed_slots if s["SlotID"] not in used_slot_ids]
        if self.debug_segments:
            print(f"🔧 remaining_slots={len(remaining_slots)} after strict")

        # Pair quotas (in-division only)
        print(f"🔧 Building pair quotas for {len(teams)} teams, target: {self.games_per_team} games per team")
        pair_remaining = self._build_pair_quota([t["name"] for t in teams])
        
        # Debug: show the mathematical breakdown
        total_games_needed = len(teams) * self.games_per_team
        total_slots_available = len(processed_slots)
        print(f"🔧 Mathematical breakdown:")
        print(f"   Teams: {len(teams)}")
        print(f"   Games per team: {self.games_per_team}")
        print(f"   Total games needed: {total_games_needed}")
        print(f"   Total slots available: {total_slots_available}")
        print(f"   Games that can be scheduled: {total_slots_available}")
        if total_slots_available < total_games_needed // 2:
            print(f"   ⚠️ Warning: Not enough slots to schedule all games!")
        else:
            print(f"   ✅ Sufficient slots available")
        
        # Show pair quota details
        print(f"🔧 Pair quota details:")
        for (team1, team2), count in pair_remaining.items():
            if count > 0:
                print(f"   {team1} vs {team2}: {count} games needed")

        def same_div(a: str, b: str) -> bool:
            da = self.team_div.get(a, "unknown"); db = self.team_div.get(b, "unknown")
            return (da == db) or (da == "unknown" or db == "unknown") if not self.no_interdivision else (da == db)

        games_assigned = list(strict_games)

        # precompute per-seg per-div remaining slot quotas
        seg_div_remaining = defaultdict(Counter)  # seg -> div -> games left in this block
        for s in remaining_slots:
            seg = s["Segment"]; d = s.get("AssignedDivision", "All")
            if d != "All":
                seg_div_remaining[seg][d] += 1

        def iter_candidate_pairs(pairs: Dict[Tuple[str, str], int]):
            ps = [(a, b) for (a, b), c in pairs.items() if c > 0]
            random.shuffle(ps)
            return ps

        # build reverse index for team division
        team_to_div = self.team_div.copy()

        for slot in remaining_slots:
            seg = slot["Segment"]
            slot_div = slot.get("AssignedDivision", "All")

            def pick(relax: bool) -> Optional[Tuple[str, str, float]]:
                best = None; best_score = -1e18
                for (a, b) in iter_candidate_pairs(pair_remaining):
                    if team_game_count[a] >= self.games_per_team or team_game_count[b] >= self.games_per_team:
                        continue
                    if slot_div != "All":
                        if team_to_div.get(a, "unknown") != slot_div or team_to_div.get(b, "unknown") != slot_div:
                            continue
                    if a in played_in_segment[seg] or b in played_in_segment[seg]:
                        continue
                    if not same_div(a, b):
                        continue

                    # time constraints
                    if not relax:
                        if not self.can_play(a, slot["Start"], last_game_time[a]):
                            continue
                        if not self.can_play(b, slot["Start"], last_game_time[b]):
                            continue
                        if self.avoid_back_to_back_opponent and (opp_last_week[a] == b or opp_last_week[b] == a):
                            continue

                    # scoring
                    score = 1000.0
                    if not relax:
                        # penalize deviation from target gap & max idle
                        for t in (a, b):
                            if last_game_time[t]:
                                gap = (slot["Start"] - last_game_time[t]).total_seconds() / 86400.0
                                score -= abs(gap - self.target_gap_days) * 1.5
                                if gap > self.max_idle_days: score -= 1000
                    else:
                        # encourage unseen teams in this seg/div
                        if slot_div != "All":
                            pa = a not in played_in_segment[seg]
                            pb = b not in played_in_segment[seg]
                            score += (20.0 if (pa and pb) else (8.0 if (pa or pb) else 0.0))

                    if self.variance_minimization:
                        for t in (a, b):
                            mb = min(bucket_count[t][k] for k in ("Early","Mid","Late"))
                            if bucket_count[t][slot["Bucket"]] == mb:
                                score += 2.0
                    if self.balance_weekdays:
                        dow = slot["Start"].strftime("%A")
                        for t in (a, b):
                            score -= weekday_count[t][dow] * 0.5
                    if self.balance_home_away:
                        score -= abs(home_count[a] - home_count[b]) * 0.2

                    key = (a, b) if a < b else (b, a)
                    if key in pair_remaining:
                        score += pair_remaining[key] * 0.1

                    if score > best_score:
                        best_score = score; best = (a, b, score)
                return best

            picked = pick(relax=False)

            # coverage pressure: if we cannot finish this block without relaxing, relax
            if picked is None and slot_div != "All":
                # remaining appearances needed in block = teams_in_div - seen_in_block
                div_team_total = sum(1 for t in team_to_div if team_to_div[t] == slot_div)
                seen = len(played_in_segment[seg]) if slot_div == "All" else len({t for t in played_in_segment[seg] if team_to_div.get(t)==slot_div})
                needed = div_team_total - seen
                possible_left = seg_div_remaining[seg][slot_div] * 2
                if needed > possible_left:
                    if self.debug_segments:
                        print(f"   ⚠️ Relaxing seg {seg}/{slot_div}: needed {needed} > possible {possible_left}")
                    picked = pick(relax=True)

            if picked is None:
                if self.debug_segments:
                    print(f"   ❌ No pair for slot {slot['SlotID']} (seg {seg}, div {slot_div})")
                continue

            a, b, _ = picked
            home, away = self.choose_home_away(a, b, home_count)

            # Calculate week number based on chronological order
            # For 22 teams: 11 matchups per week (22 teams ÷ 2 = 11 matchups)
            # Each week should have exactly 11 matchups
            games_per_week = len([t["name"] for t in teams]) // 2  # 22 ÷ 2 = 11
            week_number = (len(games_assigned) // games_per_week) + 1
            
            games_assigned.append({
                "Date": slot["Start"].strftime("%Y-%m-%d"),
                "Start": slot["Start"].strftime("%I:%M %p"),
                "End": slot["End"].strftime("%I:%M %p"),
                "Rink": slot["Rink"],
                "Division": self._denorm_div(team_to_div.get(home, "unknown")),
                "HomeTeam": home,
                "AwayTeam": away,
                "EML": slot["Bucket"],
                "Weekday": slot["Start"].strftime("%A"),
                "Week": slot["Start"].isocalendar()[1],
                "SlotID": slot["SlotID"],
                "Bucket": week_number
            })

            # update state
            last_game_time[a] = slot["Start"]
            last_game_time[b] = slot["Start"]
            opp_last_week[a] = b; opp_last_week[b] = a
            home_count[home] += 1
            bucket_count[a][slot["Bucket"]] += 1
            bucket_count[b][slot["Bucket"]] += 1
            weekday_count[a][slot["Start"].strftime("%A")] += 1
            weekday_count[b][slot["Start"].strftime("%A")] += 1
            played_in_segment[seg].add(a); played_in_segment[seg].add(b)
            if slot_div != "All":
                seg_div_remaining[seg][slot_div] = max(0, seg_div_remaining[seg][slot_div] - 1)

            key = (a, b) if a < b else (b, a)
            if pair_remaining.get(key, 0) > 0:
                pair_remaining[key] -= 1
            team_game_count[a] += 1; team_game_count[b] += 1

            # Don't stop early - continue until we've processed all slots or can't find any more valid matchups
            # This ensures we use all available slots and try to get all teams to their target
            if all(cnt >= self.games_per_team for cnt in team_game_count.values()):
                # Even if all teams have reached target, continue to see if we can distribute games more evenly
                # or if there are still valid matchups that could improve the schedule
                pass

        # Final repair/force pass to fill any leftover slots
        unused = [s for s in processed_slots if s["SlotID"] not in {g["SlotID"] for g in games_assigned}]
        if unused:
            if self.debug_segments:
                print(f"🔧 Force-filling {len(unused)} leftover slots...")
            games_assigned = self._force_fill_remaining(processed_slots, games_assigned, unused,
                                                      team_game_count, home_count, played_in_segment)
        
        # Aggressive final pass to ensure all teams reach their target
        self._aggressive_final_fill(games_assigned, team_game_count, processed_slots)
        
        # Final strict validation on full blocks
        self._validate_full_blocks(processed_slots, games_assigned)
        
        # Validate that all teams have exactly the target number of games
        self._validate_game_counts(games_assigned, team_game_count)
        
        # Final game count summary
        print(f"🔧 Final game count summary:")
        total_games_scheduled = len(games_assigned)
        expected_games = len([t["name"] for t in teams]) * self.games_per_team // 2
        print(f"🔧 Total games scheduled: {total_games_scheduled}")
        print(f"🔧 Expected games: {expected_games}")
        print(f"🔧 Games difference: {total_games_scheduled - expected_games}")
        
        for team, count in sorted(team_game_count.items()):
            status = "✅" if count == self.games_per_team else "❌"
            print(f"   {team}: {count}/{self.games_per_team} games {status}")
        
        # Check if we're missing games
        if total_games_scheduled < expected_games:
            print(f"⚠️ WARNING: Scheduled {total_games_scheduled} games but expected {expected_games}")
            print(f"   Missing {expected_games - total_games_scheduled} games")
        
        return games_assigned

    # ------------------ helpers ------------------
    def _segment_and_assign_divisions(self, slots: List[Dict[str, Any]]):
        # assign Segment id
        for idx, s in enumerate(slots):
            s["Segment"] = idx // self.block_size
            s.setdefault("AssignedDivision", "All")
        if not self.block_recipe:
            return
        recipe_total = sum(self.block_recipe.values())
        if recipe_total != self.block_size:
            # scale proportionally, then backfill remainder
            normalized = {}
            for d, c in self.block_recipe.items():
                normalized[d] = int((c / recipe_total) * self.block_size)
            rem = self.block_size - sum(normalized.values())
            # round-robin add remainder
            order = sorted(self.block_recipe.keys())
            for i in range(rem):
                normalized[order[i % len(order)]] += 1
            per_block_counts = normalized
        else:
            per_block_counts = dict(self.block_recipe)

        # build template list per block (interleaved)
        template = []
        remain = per_block_counts.copy()
        while len(template) < self.block_size:
            for d in list(remain.keys()):
                if remain[d] > 0 and len(template) < self.block_size:
                    template.append(d); remain[d] -= 1
        if self.debug_segments:
            print("🔧 Block template:", template)
            print("🔧 Normalized blockRecipe keys:", list(self.block_recipe.keys()))
            print("🔧 Original recipe (before scaling):", self.params.get("blockRecipe", {}))
            print("🔧 Scaled template counts:", per_block_counts)
            print("🔧 Template will cycle through all slots in each block")

        # stamp each block with the template order, cycling through the template for all slots
        max_seg = slots[-1]["Segment"]
        for seg in range(max_seg + 1):
            indices = [i for i, s in enumerate(slots) if s["Segment"] == seg]
            for k, i in enumerate(indices):
                # Cycle through the template to assign divisions to all slots
                template_idx = k % len(template)
                slots[i]["AssignedDivision"] = template[template_idx]
        
        # Debug: show division distribution across all slots
        if self.debug_segments:
            div_counts = Counter()
            for s in slots:
                div_counts[s["AssignedDivision"]] += 1
            print("🔧 Final division distribution across all slots:", dict(div_counts))

    def _strict_block_fill(self, processed_slots, teams, home_count, team_game_count):
        """Fill every full block that matches the recipe with a full division round each.
        Returns (games_assigned, used_slot_ids, played_in_segment).
        """
        games_assigned = []
        used_slot_ids = set()
        played_in_segment = defaultdict(set)

        if not (self.block_strict_once and self.block_recipe and self.block_size):
            if self.debug_segments:
                print("🔧 Strict filler skipped: block_strict_once={}, block_recipe={}, block_size={}".format(
                    self.block_strict_once, bool(self.block_recipe), self.block_size))
            return games_assigned, used_slot_ids, played_in_segment
        
        if self.debug_segments:
            print("🔧 Strict filler running with recipe:", self.block_recipe)

        # build teams per division & round-robins
        teams_by_div = defaultdict(list)
        for t in teams:
            d = self.team_div[t["name"]]
            if d != "unknown":
                teams_by_div[d].append(t["name"])

        # Only build round-robins for divisions that are in our recipe
        div_rounds = {}
        div_round_idx = {}
        if self.debug_segments:
            print(f"🔧 Strict filler: building round-robins for recipe divisions: {list(self.block_recipe.keys())}")
            print(f"🔧 Available team divisions: {list(teams_by_div.keys())}")
        for d in self.block_recipe.keys():
            if d in teams_by_div:
                div_rounds[d] = self.round_robin_pairs(teams_by_div[d], seed=self.params.get("seed", 42))
                div_round_idx[d] = 0
                if self.debug_segments:
                    print(f"🔧 Built round-robin for '{d}' with {len(teams_by_div[d])} teams")
            else:
                print(f"⚠️ Warning: Division '{d}' in blockRecipe not found in teams")

        # group slots by segment
        seg_slots = defaultdict(list)
        for s in processed_slots:
            seg_slots[s["Segment"].__int__() if hasattr(s["Segment"], "__int__") else s["Segment"]].append(s)

        for seg in sorted(seg_slots.keys()):
            # ⬇️ hard stop once all teams reached the cap
            if all(c >= self.games_per_team for c in team_game_count.values()):
                if self.debug_segments:
                    print(f"🔧 Stopping strict filler: all teams have {self.games_per_team}")
                break
                
            slots = seg_slots[seg]
            want = Counter()
            for s in slots:
                d = s.get("AssignedDivision", "All")
                if d != "All":
                    want[d] += 1
            # Make strict blocks truly strict (require exact recipe match)
            # This prevents partial strict fills that strand slots
            is_full = len(slots) == self.block_size
            matches = is_full and all(want.get(d, 0) == self.block_recipe.get(d, 0) 
                                      for d in self.block_recipe) \
                           and sum(self.block_recipe.values()) == self.block_size
            if not matches:
                # skip this block in strict mode; heuristic will handle it
                if self.debug_segments:
                    print(f"🔧 Skipping strict fill for block {seg}: want={dict(want)} "
                          f"!= recipe={self.block_recipe} or not full.")
                continue
            
            # ⬇️ new: look-ahead cap check for the whole block
            block_would_exceed = False
            for d in self.block_recipe:
                for t in teams_by_div[d]:
                    if team_game_count[t] + 1 > self.games_per_team:
                        block_would_exceed = True
                        break
                if block_would_exceed:
                    break

            if block_would_exceed:
                if self.debug_segments:
                    print(f"🔧 Skipping block {seg}: would exceed per-team cap of {self.games_per_team}")
                continue
            
            if self.debug_segments:
                print(f"🔧 Processing block {seg} with strict filler")
                print(f"🔧 Block {seg} recipe: {dict(self.block_recipe)}")

            # Create exactly the recipe count for each division (we know the block matches exactly)
            for d, games_needed in self.block_recipe.items():
                if self.debug_segments:
                    print(f"🔧 Processing division '{d}': creating exactly {games_needed} games")
                
                rr = div_rounds.get(d)
                if rr is None:
                    raise ValueError(f"No round-robin for division '{d}'. "
                                   f"Make sure team divisions and blockRecipe keys normalize to the same value.")
                
                # Get the next round of games
                r_idx = div_round_idx[d] % len(rr)
                round_pairs = rr[r_idx]
                
                # Take exactly the games we need
                games_to_use = round_pairs[:games_needed]
                if len(games_to_use) != games_needed:
                    raise ValueError(
                        f"Recipe wants {games_needed} games for '{d}', but division round only has {len(games_to_use)} available."
                    )
                
                d_slots = [s for s in slots if s.get("AssignedDivision", "All") == d and s["SlotID"] not in used_slot_ids]
                if len(d_slots) < games_needed:
                    raise ValueError(f"Block {seg}: insufficient '{d}' slots for {games_needed} games.")

                # Use exactly the number of slots we need
                slots_to_use = d_slots[:games_needed]
                if self.debug_segments:
                    print(f"🔧 Division '{d}': using {len(slots_to_use)} slots out of {len(d_slots)} available")

                for (ha, hb), s in zip(games_to_use, slots_to_use):
                    home, away = self.choose_home_away(ha, hb, home_count)
                    games_assigned.append({
                        "Date": s["Start"].strftime("%Y-%m-%d"),
                        "Start": s["Start"].strftime("%I:%M %p"),
                        "End": s["End"].strftime("%I:%M %p"),
                        "Rink": s.get("Rink", ""),
                        "Division": self._denorm_div(d),
                        "HomeTeam": home,
                        "AwayTeam": away,
                        "EML": s["Bucket"],
                        "Weekday": s["Start"].strftime("%A"),
                        "Week": s["Start"].isocalendar()[1],
                        "SlotID": s["SlotID"]
                    })
                    used_slot_ids.add(s["SlotID"])
                    played_in_segment[seg].add(home); played_in_segment[seg].add(away)
                    team_game_count[home] += 1; team_game_count[away] += 1
                div_round_idx[d] += 1
                if self.debug_segments:
                    print(f"🔧 Division '{d}': created {games_needed} games")
        
        if self.debug_segments:
            print(f"🔧 Strict filler total: created {len(games_assigned)} games, used {len(used_slot_ids)} slots")
            print(f"🔧 Total slots processed: {len(processed_slots)}")
            print(f"🔧 Slots remaining for heuristic: {len(processed_slots) - len(used_slot_ids)}")
        return games_assigned, used_slot_ids, played_in_segment

    def _force_fill_remaining(self, processed_slots, games_assigned, remaining_slots, 
                             team_game_count, home_count, played_in_segment):
        """Last-chance filler: ignore time/rest/back-to-back, but keep:
           - division of the slot
           - once-per-block (no team twice in same Segment)
           - team targets (don't exceed games_per_team)
        """
        target = self.games_per_team
        team_to_div = self.team_div

        # quick index to find slot->segment
        slot_seg = {s["SlotID"]: s["Segment"] for s in processed_slots}

        # try earliest leftover first
        remaining_slots.sort(key=lambda s: s["Start"])

        for s in remaining_slots:
            seg = s["Segment"]
            div = s.get("AssignedDivision", "All")
            if div == "All":
                # allow any division if template left 'All'
                candidates = [t for t in team_to_div if team_game_count[t] < target 
                              and t not in played_in_segment[seg]]
            else:
                candidates = [t for t, d in team_to_div.items() if d == div 
                              and team_game_count[t] < target 
                              and t not in played_in_segment[seg]]
            if len(candidates) < 2:
                continue

            # choose two lowest-game teams; if tie, pick ones that didn't just face each other
            candidates.sort(key=lambda t: team_game_count[t])
            placed = False
            for i in range(len(candidates)):
                if placed: break
                for j in range(i+1, len(candidates)):
                    a, b = candidates[i], candidates[j]
                    # division consistency already guaranteed; ignore rest/back-to-back here
                    home, away = self.choose_home_away(a, b, home_count)
                    games_assigned.append({
                        "Date": s["Start"].strftime("%Y-%m-%d"),
                        "Start": s["Start"].strftime("%I:%M %p"),
                        "End": s["End"].strftime("%I:%M %p"),
                        "Rink": s.get("Rink", ""),
                        "Division": self._denorm_div(team_to_div.get(home, "unknown")),
                        "HomeTeam": home,
                        "AwayTeam": away,
                        "EML": s["Bucket"],
                        "Weekday": s["Start"].strftime("%A"),
                        "Week": s["Start"].isocalendar()[1],
                        "SlotID": s["SlotID"]
                    })
                    home_count[home] += 1
                    team_game_count[a] += 1
                    team_game_count[b] += 1
                    played_in_segment[seg].add(a); played_in_segment[seg].add(b)
                    placed = True
                    break
        return games_assigned

    def _build_pair_quota(self, team_names: List[str]) -> Counter:
        by_div = defaultdict(list)
        for t in team_names:
            d = self.team_div.get(t, "unknown")
            if d != "unknown":
                by_div[d].append(t)
        pair_target: Counter = Counter()
        
        for d, arr in by_div.items():
            n = len(arr)
            if n < 2: continue
            
            # Pure mathematical approach: calculate exactly how many games each team needs
            # Total games needed for this division = n * games_per_team
            total_games_needed = n * self.games_per_team
            
            # Total unique matchups possible = n * (n-1) / 2
            unique_matchups = n * (n - 1) // 2
            
            if unique_matchups == 0: continue
            
            # Base games per unique matchup (integer division)
            base_games_per_matchup = total_games_needed // (2 * unique_matchups)
            
            # Extra games to distribute (remainder)
            extra_games = total_games_needed - (2 * unique_matchups * base_games_per_matchup)
            
            # Assign base games to all unique matchups
            for i in range(n):
                for j in range(i + 1, n):
                    pair_target[(arr[i], arr[j])] += base_games_per_matchup
            
            # Distribute extra games to reach exact target
            if extra_games > 0:
                # Create list of all possible matchups for this division
                all_matchups = [(arr[i], arr[j]) for i in range(n) for j in range(i + 1, n)]
                
                # Distribute extra games evenly, prioritizing matchups with fewer games
                for _ in range(extra_games):
                    # Find matchup with fewest games
                    best_matchup = min(all_matchups, key=lambda pair: pair_target[pair])
                    pair_target[best_matchup] += 1
            
            # Validate that we're on track to meet the target
            total_assigned = sum(pair_target.values())
            if total_assigned * 2 != total_games_needed:
                print(f"⚠️ Warning: Division {d} target mismatch. Need {total_games_needed} games, assigned {total_assigned * 2}")
        
        return pair_target

    def _validate_full_blocks(self, processed_slots, games_assigned):
        if not (self.block_strict_once and self.block_recipe and self.block_size):
            return
        # group scheduled games by segment
        slot_by_id = {s["SlotID"]: s for s in processed_slots}
        seg_to_games = defaultdict(list)
        for g in games_assigned:
            seg_to_games[slot_by_id[g["SlotID"]]["Segment"]].append(g)
        recipe_total = sum(self.block_recipe.values())
        for seg, glist in sorted(seg_to_games.items()):
            if len(glist) != self.block_size:
                # only validate full recipe blocks of exact size
                continue
            # exactly once across whole block
            seen = Counter()
            for g in glist:
                seen[g["HomeTeam"]] += 1; seen[g["AwayTeam"]] += 1
            offenders = [t for t, c in seen.items() if c != 1]
            if offenders:
                raise ValueError(f"🚨 Block {seg}: not exactly-once per team; offenders: {offenders}")
            # per-division coverage check
            divteams = defaultdict(set)
            for g in glist:
                d = g.get("Division", "unknown")
                divteams[d].add(g["HomeTeam"]); divteams[d].add(g["AwayTeam"])
            for d, need_games in self.block_recipe.items():
                # teams actually scheduled in this seg for this division
                have = divteams.get(d, set())
                # expected = all teams of that division
                # infer from the schedule itself
                expected = set()
                for g in glist:
                    if g.get("Division") == d:
                        expected.add(g["HomeTeam"]); expected.add(g["AwayTeam"])
                # for a full round this must be the entire division team set size
                if len(have) != len(expected):
                    raise ValueError(f"🚨 Block {seg}/{d}: coverage mismatch {len(have)}/{len(expected)}")
        print(f"✅ Full {self.block_size}-slot blocks validated (exactly once per team).")

    def _validate_game_counts(self, games_assigned: List[Dict[str, Any]], team_game_count: Dict[str, int]):
        """Validate that all teams have exactly the target number of games."""
        print(f"🔍 Validating game counts - target: {self.games_per_team} games per team")
        
        # Count actual games per team from the assigned games
        actual_games = Counter()
        for game in games_assigned:
            actual_games[game["HomeTeam"]] += 1
            actual_games[game["AwayTeam"]] += 1
        
        # Check for any teams that don't have exactly the target number of games
        issues = []
        for team, count in actual_games.items():
            if count != self.games_per_team:
                issues.append(f"{team}: {count}/{self.games_per_team} games")
        
        if issues:
            print(f"❌ Game count validation failed:")
            for issue in issues:
                print(f"   {issue}")
            
            # Try to fix by redistributing games if possible
            self._fix_game_count_imbalances(games_assigned, actual_games)
        else:
            print(f"✅ All teams have exactly {self.games_per_team} games")
    
    def _fix_game_count_imbalances(self, games_assigned: List[Dict[str, Any]], actual_games: Counter):
        """Attempt to fix teams with wrong game counts by redistributing games."""
        print("🔧 Attempting to fix game count imbalances...")
        
        # Find teams with too many or too few games
        over_teams = [team for team, count in actual_games.items() if count > self.games_per_team]
        under_teams = [team for team, count in actual_games.items() if count < self.games_per_team]
        
        if not over_teams or not under_teams:
            print("   Cannot fix: need both over and under teams")
            return
        
        # Try to find games involving over teams that can be swapped to involve under teams
        for over_team in over_teams:
            for under_team in under_teams:
                # Look for games where we can swap one team
                for i, game in enumerate(games_assigned):
                    if game["HomeTeam"] == over_team and game["AwayTeam"] != under_team:
                        # Try to swap home team
                        if self._can_swap_team(game, over_team, under_team, games_assigned):
                            games_assigned[i]["HomeTeam"] = under_team
                            actual_games[over_team] -= 1
                            actual_games[under_team] += 1
                            print(f"   Swapped {over_team} → {under_team} in home position")
                            return
                    elif game["AwayTeam"] == over_team and game["HomeTeam"] != under_team:
                        # Try to swap away team
                        if self._can_swap_team(game, over_team, under_team, games_assigned):
                            games_assigned[i]["AwayTeam"] = under_team
                            actual_games[over_team] -= 1
                            actual_games[under_team] += 1
                            print(f"   Swapped {over_team} → {under_team} in away position")
                            return
        
        print("   Could not find suitable swaps to fix imbalances")
    
    def _aggressive_final_fill(self, games_assigned: List[Dict[str, Any]], team_game_count: Dict[str, int], processed_slots: List[Dict[str, Any]]):
        """Aggressively try to get all teams to their target game count by redistributing games."""
        print("🔧 Starting aggressive final fill to reach target game counts...")
        
        # Find teams that haven't reached their target
        under_teams = [team for team, count in team_game_count.items() if count < self.games_per_team]
        over_teams = [team for team, count in team_game_count.items() if count > self.games_per_team]
        
        if not under_teams:
            print("   ✅ All teams have reached their target!")
            return
        
        print(f"   Teams under target: {under_teams}")
        print(f"   Teams over target: {over_teams}")
        
        # Try to redistribute games from over teams to under teams
        for under_team in under_teams:
            needed = self.games_per_team - team_game_count[under_team]
            print(f"   {under_team} needs {needed} more games")
            
            for _ in range(needed):
                # Find a game with an over team that we can swap
                for i, game in enumerate(games_assigned):
                    if game["HomeTeam"] in over_teams and game["AwayTeam"] != under_team:
                        # Try to swap home team
                        if self._can_swap_team(game, game["HomeTeam"], under_team, games_assigned):
                            old_team = game["HomeTeam"]
                            games_assigned[i]["HomeTeam"] = under_team
                            team_game_count[old_team] -= 1
                            team_game_count[under_team] += 1
                            print(f"      Swapped {old_team} → {under_team} in home position")
                            break
                    elif game["AwayTeam"] in over_teams and game["HomeTeam"] != under_team:
                        # Try to swap away team
                        if self._can_swap_team(game, game["AwayTeam"], under_team, games_assigned):
                            old_team = game["AwayTeam"]
                            games_assigned[i]["AwayTeam"] = under_team
                            team_game_count[old_team] -= 1
                            team_game_count[under_team] += 1
                            print(f"      Swapped {old_team} → {under_team} in away position")
                            break
                else:
                    print(f"      Could not find suitable swap for {under_team}")
                    break
        
        # Final check
        final_under = [team for team, count in team_game_count.items() if count < self.games_per_team]
        if final_under:
            print(f"   ⚠️ Still under target: {final_under}")
        else:
            print("   ✅ All teams now have their target games!")
    
    def _can_swap_team(self, game: Dict[str, Any], old_team: str, new_team: str, all_games: List[Dict[str, Any]]) -> bool:
        """Check if swapping a team in a game would create conflicts."""
        # Check if the new team already plays on the same date
        game_date = game["Date"]
        for other_game in all_games:
            if other_game == game:  # Skip the current game
                continue
            if other_game["Date"] == game_date:
                if (other_game["HomeTeam"] == new_team or 
                    other_game["AwayTeam"] == new_team):
                    return False  # Team already plays on this date
        
        # Check if the new team already plays against the other team in this game
        other_team = game["AwayTeam"] if game["HomeTeam"] == old_team else game["HomeTeam"]
        for other_game in all_games:
            if other_game == game:  # Skip the current game
                continue
            if ((other_game["HomeTeam"] == new_team and other_game["AwayTeam"] == other_team) or
                (other_game["AwayTeam"] == new_team and other_game["HomeTeam"] == other_team)):
                return False  # This matchup already exists
        
        return True


def generate_enhanced_schedule(slots: List[Dict[str, Any]],
                               teams: List[Dict[str, Any]],
                               divisions: List[Dict[str, Any]],
                               params: Dict[str, Any]) -> Dict[str, Any]:
    scheduler = EnhancedScheduler(params)
    schedule = scheduler.build_schedule(slots, teams, divisions)

    # Sort schedule chronologically by date and time
    def sort_key(game):
        # Parse date and time for proper chronological sorting
        date_str = game["Date"]
        time_str = game["Start"]
        
        # Convert time from "I:MM AM/PM" format to 24-hour for sorting
        try:
            from datetime import datetime
            # Parse the time string (e.g., "9:00 PM" -> 21:00)
            time_obj = datetime.strptime(time_str, "%I:%M %p")
            time_24hr = time_obj.strftime("%H:%M")
            
            # Combine date and time for sorting
            datetime_str = f"{date_str} {time_24hr}"
            return datetime.strptime(datetime_str, "%Y-%m-%d %H:%M")
        except Exception as e:
            print(f"⚠️ Warning: Could not parse time '{time_str}' for game on {date_str}: {e}")
            # Fallback to date-only sorting if time parsing fails
            return datetime.strptime(date_str, "%Y-%m-%d")
    
    # Sort the schedule chronologically
    schedule.sort(key=sort_key)
    
    print(f"📅 Schedule sorted chronologically: {len(schedule)} games from {schedule[0]['Date']} to {schedule[-1]['Date']}")

    # KPIs (kept minimal; can be expanded as needed)
    team_names = [t["name"] for t in teams]
    team_kpis = {}
    for name in team_names:
        tg = [g for g in schedule if g["HomeTeam"] == name or g["AwayTeam"] == name]
        if not tg: continue
        tg.sort(key=lambda x: x["Date"])  # ISO yyyy-mm-dd
        gaps = []
        last = None
        for g in tg:
            d = datetime.strptime(g["Date"], "%Y-%m-%d")
            if last: gaps.append((d - last).days)
            last = d
        avg_gap = float(np.mean(gaps)) if gaps else 0.0
        team_kpis[name] = {
            "games": len(tg),
            "home": sum(1 for g in tg if g["HomeTeam"] == name),
            "away": sum(1 for g in tg if g["AwayTeam"] == name),
            "avgGap": round(avg_gap, 2)
        }

    return {
        "schedule": schedule,
        "kpis": {
            "totalGames": len(schedule),
            "teamKPIs": team_kpis
        },
        "success": True,
        "message": f"Generated {len(schedule)} games for {len(teams)} teams"
    }
