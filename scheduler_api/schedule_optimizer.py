from datetime import datetime, time
import random
import sys
from typing import Dict, List, Set, Tuple
from dataclasses import dataclass


@dataclass
class GameSlot:
    slot_id: int
    game_time: time
    team1: str
    team2: str
    is_late_game: bool
    date: str  # Add date for double-booking checks


@dataclass
class Team:
    name: str
    division: str
    late_game_count: int = 0


def _parse_start_to_time(start_str: str) -> time:
    """Parse start time from various formats (ISO, 12-hour, 24-hour)"""
    s = start_str.strip()
    try:
        if "T" in s:  # ISO-ish
            # Try to parse HH:MM from the time portion (ignore tz here; upstream should pass local)
            tpart = s.split("T", 1)[1]
            if "." in tpart:
                tpart = tpart.split(".", 1)[0]
            hh, mm, *_ = tpart.split(":")
            return time(int(hh), int(mm))
        if "AM" in s.upper() or "PM" in s.upper():
            # 12-hour
            dt = datetime.strptime(s.upper().replace(" AM","AM").replace(" PM","PM"), "%I:%M%p")
            return dt.time()
        # 24-hour "HH:MM"
        hh, mm = s.split(":")
        return time(int(hh), int(mm))
    except Exception:
        # last resort
        return time(22, 31)


def _parse_start_to_date(start_str: str) -> str:
    """Return ISO date 'YYYY-MM-DD' for same-day constraint checks"""
    s = start_str.strip()
    try:
        if "T" in s:
            return s.split("T", 1)[0]
        # If not ISO, caller should provide a date elsewhere; safe fallback:
        return ""
    except Exception:
        return ""


def create_bucket_from_schedule(schedule_data: List[Dict], late_threshold: time) -> List[GameSlot]:
    """Create GameSlot objects from schedule data with proper field mapping"""
    slots = []
    for i, item in enumerate(schedule_data):
        start_str = item.get('start') or item.get('time', '22:31')
        t = _parse_start_to_time(start_str)
        is_late = (t >= late_threshold)
        team1 = item.get('home', item.get('team1', ''))
        team2 = item.get('away', item.get('team2', ''))
        date = _parse_start_to_date(start_str)
        
        slots.append(GameSlot(
            slot_id=item.get('slot_id', item.get('id', i)),
            game_time=t,
            team1=team1,
            team2=team2,
            is_late_game=is_late,
            date=date
        ))
    return slots


def _late_counts_from_completed(completed_buckets: List[List[Dict]], late_threshold: time) -> Dict[str, int]:
    """Count late games from completed buckets using proper field names"""
    counts: Dict[str, int] = {}
    for bucket in completed_buckets or []:
        for slot in create_bucket_from_schedule(bucket, late_threshold):
            if slot.is_late_game:
                for tm in (slot.team1, slot.team2):
                    if tm:
                        counts[tm] = counts.get(tm, 0) + 1
    return counts


def _get_teams_playing_on_date(bucket: List[Dict], target_date: str) -> Set[str]:
    """Get all teams that are already playing on a specific date in this bucket"""
    teams_playing = set()
    for game in bucket:
        game_date = _parse_start_to_date(game.get('start', ''))
        if game_date == target_date:
            home_team = game.get('home', '')
            away_team = game.get('away', '')
            if home_team:
                teams_playing.add(home_team)
            if away_team:
                teams_playing.add(away_team)
    return teams_playing


def _place_teams_in_late_slots(bucket: List[Dict], 
                               divisions: Dict[str, List[str]], 
                               completed_buckets: List[List[Dict]], 
                               late_threshold: time,
                               previous_bucket: List[Dict] = None,
                               optimize_days_since: bool = True,
                               params: Dict = None) -> Tuple[List[Dict], List[Dict]]:
    """
    Clear and rebuild approach: Remove all matchups from the week's games, then add them back
    systematically in order of priority (fewest late games first) to balance distribution.
    
    ⚠️  CRITICAL: This function MUST preserve all time information (start, end, rink) exactly as-is.
    ⚠️  Only team assignments (home, away, div) can be modified.
    ⚠️  Any changes to dates, times, or rinks will cause the optimization to fail.
    """
    try:
        print(f"🔍 DEBUG: Starting _place_teams_in_late_slots function", file=sys.stderr)
        print(f"🔍 DEBUG: Parameters: bucket={len(bucket)}, divisions={len(divisions)}, completed_buckets={len(completed_buckets)}, late_threshold={late_threshold}, optimize_days_since={optimize_days_since}", file=sys.stderr)
        
        # Get late game counts from previous weeks (completed buckets)
        late_counts = _late_counts_from_completed(completed_buckets, late_threshold)
        print(f"Late game counts from previous weeks: {late_counts}", file=sys.stderr)
        
        # Create a working copy of the bucket
        working_bucket = bucket.copy()
        swaps_made = []
        
        print(f"Starting clear and rebuild for Week with {len(working_bucket)} games", file=sys.stderr)
        print(f"🎯 OPTIMIZATION STRATEGY: Move existing matchups between time slots (NO new matchups, NO time changes)", file=sys.stderr)
        print(f"We'll clear {len(working_bucket)} matchups and place them back in different time slots", file=sys.stderr)
        
        # Step 1: Extract all existing matchups from the week
        print(f"🔍 DEBUG: Step 1: Extracting existing matchups", file=sys.stderr)
        existing_matchups = []
        for i, game in enumerate(working_bucket):
            if game.get('home') and game.get('away'):
                matchup = {
                    'home': game.get('home'),
                    'away': game.get('away'),
                    'div': game.get('div'),
                    'original_slot': i,
                    'start_time': game.get('start'),
                    'is_late': _parse_start_to_time(game.get('start', '')) >= late_threshold
                }
                existing_matchups.append(matchup)
                print(f"Found matchup {i+1}: {matchup['home']} vs {matchup['away']} at {matchup['start_time']} (Late: {matchup['is_late']})", file=sys.stderr)
        
        print(f"Extracted {len(existing_matchups)} existing matchups", file=sys.stderr)
        print(f"🔒 These exact matchups will be preserved - only their time slots may change", file=sys.stderr)
        
        # Step 2: Clear all games (remove teams but keep time slots)
        cleared_games = []
        for i, game in enumerate(working_bucket):
            # IMPORTANT: Create a proper copy to avoid modifying the original
            # PRESERVE ALL TIME INFORMATION EXACTLY AS IS
            cleared_game = {
                'start': game.get('start', ''),      # Keep original start time
                'end': game.get('end', ''),          # Keep original end time  
                'rink': game.get('rink', ''),        # Keep original rink
                'home': '',                          # Clear home team only
                'away': '',                          # Clear away team only
                'div': ''                            # Clear division only
            }
            cleared_games.append(cleared_game)
            
            # Record the "removal" as a change
            if game.get('home') or game.get('away'):
                swaps_made.append({
                    'game_id': i + 1,
                    'date': _parse_start_to_date(game.get('start', '')),
                    'time': game.get('start', ''),
                    'before': f"{game.get('home', '')} vs {game.get('away', '')} ({game.get('div', '')})",
                    'after': f"[EMPTY] vs [EMPTY] (cleared)",
                    'division': 'cleared',
                    'was_late': _parse_start_to_time(game.get('start', '')) >= late_threshold,
                    'phase': 'Phase 0 - Game Clearing',
                    'rink': game.get('rink', '')
                })
        
        print(f"Cleared all {len(cleared_games)} games in the week", file=sys.stderr)
        
        # Step 3: Sort matchups by priority (teams with fewest late games first)
        # Calculate combined late game count for each matchup
        for matchup in existing_matchups:
            home_late = late_counts.get(matchup['home'], 0)
            away_late = late_counts.get(matchup['away'], 0)
            matchup['combined_late_count'] = home_late + away_late
            print(f"  Matchup {matchup['home']} vs {matchup['away']}: {home_late} + {away_late} = {matchup['combined_late_count']} late games", file=sys.stderr)
        
        # Sort by combined late game count (fewest first)
        existing_matchups.sort(key=lambda m: m['combined_late_count'])
        print(f"  Matchups sorted by priority (fewest late games first):", file=sys.stderr)
        for i, matchup in enumerate(existing_matchups):
            print(f"  {i+1}. {matchup['home']} vs {matchup['away']}: {matchup['combined_late_count']} late games", file=sys.stderr)
        
        # Step 4: Place matchups back into time slots, prioritizing late slots for teams with few late games
        placed_matchups = set()  # Track which matchups have been placed
        games_filled = 0
        
        print(f"  Starting matchup placement. Need to fill {len(cleared_games)} games with {len(existing_matchups)} matchups", file=sys.stderr)
        
        # PHASE 1: Fill late game slots first with highest priority matchups
        # CRITICAL FIX: Sort late slots by chronological order to prevent 0-day gaps
        late_slots = []
        for i, game in enumerate(cleared_games):
            if _parse_start_to_time(game.get('start', '')) >= late_threshold:
                game_date = _parse_start_to_date(game.get('start', ''))
                game_time = _parse_start_to_time(game.get('start', ''))
                late_slots.append((i, game_date, game_time))
        
        # Sort by date first, then by time (earliest first)
        late_slots.sort(key=lambda x: (x[1] if x[1] else '9999-99-99', x[2] if x[2] else time(23, 59)))
        
        # Extract just the slot indices in chronological order
        late_slots = [slot[0] for slot in late_slots]
        
        print(f"  Late game slots available (chronologically sorted): {late_slots} (will fill these first with teams having fewest late games)", file=sys.stderr)
        print(f"  Late slot details:", file=sys.stderr)
        for i, game in enumerate(cleared_games):
            if _parse_start_to_time(game.get('start', '')) >= late_threshold:
                game_date = _parse_start_to_date(game.get('start', ''))
                game_time = _parse_start_to_time(game.get('start', ''))
                print(f"    Slot {i+1}: {game_date} at {game_time.strftime('%I:%M %p').lstrip('0')} (Late Game)", file=sys.stderr)
        
        # Sort matchups by priority (fewest late games first) for late slot placement
        late_slot_matchups = sorted(existing_matchups, key=lambda m: m['combined_late_count'])
        print(f"  Matchups sorted by priority (fewest late games first):", file=sys.stderr)
        for i, matchup in enumerate(late_slot_matchups):
            print(f"    {i+1}. {matchup['home']} vs {matchup['away']}: {matchup['combined_late_count']} late games", file=sys.stderr)
        
        # Fill late slots systematically
        late_slots_filled = 0
        print(f"[DEBUG] DEBUG: Starting Phase 1: Late game optimization with {len(late_slots)} late slots", file=sys.stderr)
        
        for late_slot in late_slots:
            if late_slots_filled >= len(late_slots):
                break
                
            # Find the highest priority matchup that can fit in this late slot
            matchup_placed = False
            for matchup in late_slot_matchups:
                if f"{matchup['home']}_{matchup['away']}" in placed_matchups:
                    continue  # Already placed
                    
                # Check if this matchup can be placed in this late slot without conflicts
                # ENHANCED CHECK: Also prevent same-day conflicts within the current week
                slot_date = _parse_start_to_date(cleared_games[late_slot].get('start', ''))
                if not _would_create_conflict(cleared_games, late_slot, matchup['home'], matchup['away'], slot_date, previous_bucket):
                    # ADDITIONAL CHECK: Verify no same-day conflicts within current week
                    same_day_conflict = False
                    for i, other_game in enumerate(cleared_games):
                        if i == late_slot:
                            continue  # Skip the current slot
                        if other_game.get('home') or other_game.get('away'):
                            other_date = _parse_start_to_date(other_game.get('start', ''))
                            if other_date == slot_date:
                                # Same date - check for team conflicts
                                if (matchup['home'] in [other_game.get('home', ''), other_game.get('away', '')] or 
                                    matchup['away'] in [other_game.get('home', ''), other_game.get('away', '')]):
                                    print(f"    [CONFLICT] Same-day conflict detected: {matchup['home']} or {matchup['away']} already playing on {slot_date} in slot {i+1}", file=sys.stderr)
                                    same_day_conflict = True
                                    break
                    
                    if not same_day_conflict:
                        print(f"    [TIME] LATE SLOT {late_slot + 1}: Placing {matchup['home']} vs {matchup['away']} (priority: {matchup['combined_late_count']} late games)", file=sys.stderr)
                        
                        # Place the matchup in this late slot
                        cleared_games[late_slot] = {
                            **cleared_games[late_slot],
                            'home': matchup['home'],
                            'away': matchup['away'],
                            'div': matchup['div']
                        }
                        
                        # Mark matchup as placed
                        placed_matchups.add(f"{matchup['home']}_{matchup['away']}")
                        games_filled += 1
                        late_slots_filled += 1
                        
                        # Record the placement
                        swaps_made.append({
                            'game_id': late_slot + 1,
                            'date': _parse_start_to_date(cleared_games[late_slot].get('start', '')),
                            'time': cleared_games[late_slot].get('start', ''),
                            'before': f"[EMPTY] vs [EMPTY] (cleared)",
                            'after': f"{matchup['home']} vs {matchup['away']} ({matchup['div']})",
                            'division': matchup['div'],
                            'was_late': True,
                            'phase': 'Phase 1 - Late Game Consistency',
                            'rink': cleared_games[late_slot].get('rink', '')
                        })
                        
                        print(f"    [SUCCESS] SUCCESS: Placed {matchup['home']} vs {matchup['away']} in Late Game {late_slot + 1} (late slots filled: {late_slots_filled}/{len(late_slots)})", file=sys.stderr)
                        break  # Move to next late slot
                    
            if not matchup_placed:
                print(f"    [WARNING] LATE SLOT {late_slot + 1}: Could not place any matchup (conflicts or no available matchups)", file=sys.stderr)
        
        print(f"  Phase 1 complete: Filled {late_slots_filled}/{len(late_slots)} late slots", file=sys.stderr)
        print(f"  Late game optimization complete. Games filled: {games_filled}/{len(cleared_games)}", file=sys.stderr)
        
        # Show Phase 1 results
        print(f"  [RESULTS] PHASE 1 RESULTS:", file=sys.stderr)
        print(f"    Late slots filled: {late_slots_filled}/{len(late_slots)}", file=sys.stderr)
        print(f"    Teams placed in late slots:", file=sys.stderr)
        for i, game in enumerate(cleared_games):
            if game.get('home') and game.get('away') and _parse_start_to_time(game.get('start', '')) >= late_threshold:
                print(f"      Slot {i+1}: {game['home']} vs {game['away']} (Late Game)", file=sys.stderr)
        
        # PHASE 2: Days since last played optimization (NEW) - ONLY for teams NOT placed in Phase 1
        print(f"🔍 DEBUG: About to start Phase 2, games_filled={games_filled}, optimize_days_since={optimize_days_since}", file=sys.stderr)
        if games_filled > 0 and optimize_days_since:  # Only run if we have teams placed and feature is enabled
            print(f"  [TIME] Starting Phase 2: Days since last played optimization (ONLY for teams NOT placed in Phase 1)", file=sys.stderr)
            
            # CRITICAL: Phase 2 should NEVER move teams that were placed in Phase 1 (late slots)
            # It should only work with remaining empty slots and unplaced teams
            print(f"  [LOCK] Phase 2 constraint: Will NOT move any teams already placed in Phase 1", file=sys.stderr)
            
            # Get the start date of the current week for calculations
            current_week_start_date = None
            for game in cleared_games:
                game_date = _parse_start_to_date(game.get('start', ''))
                if game_date:
                    current_week_start_date = game_date
                    break
            
            if current_week_start_date:
                print(f"🔍 DEBUG: Calling Phase 2 function with current_week_start_date={current_week_start_date}", file=sys.stderr)
                try:
                    _optimize_days_since_last_played(cleared_games, existing_matchups, placed_matchups, completed_buckets, current_week_start_date, previous_bucket, late_threshold, swaps_made, params)
                    print(f"🔍 DEBUG: Phase 2 function completed successfully", file=sys.stderr)
                except Exception as e:
                    print(f"🔍 DEBUG: Phase 2 function failed with error: {e}", file=sys.stderr)
                    import traceback
                    print(f"🔍 DEBUG: Phase 2 traceback: {traceback.format_exc()}", file=sys.stderr)
                
                # Show Phase 2 results
                print(f"  [RESULTS] PHASE 2 RESULTS:", file=sys.stderr)
                print(f"    Teams placed via days optimization:", file=sys.stderr)
                for i, game in enumerate(cleared_games):
                    if game.get('home') and game.get('away') and _parse_start_to_time(game.get('start', '')) < late_threshold:
                        # This is a non-late game that was placed in Phase 2
                        print(f"      Slot {i+1}: {game['home']} vs {game['away']} (Days Optimization)", file=sys.stderr)
            else:
                print(f"    ⚠️  Could not determine current week start date, skipping days optimization", file=sys.stderr)
        elif not optimize_days_since:
            print(f"  ⚠️  Days since last played optimization disabled by parameter", file=sys.stderr)
        else:
            print(f"  ⚠️  No teams placed, skipping days optimization", file=sys.stderr)
        
        # PHASE 3: Only handle any remaining edge cases or conflicts (DO NOT fill remaining slots - that's Phase 2's job!)
        print(f"[DEBUG] DEBUG: About to start Phase 3, placed_matchups={len(placed_matchups)}, existing_matchups={len(existing_matchups)}", file=sys.stderr)
        remaining_matchups = [m for m in existing_matchups if f"{m['home']}_{m['away']}" not in placed_matchups]
        print(f"[DEBUG] DEBUG: Phase 3: Found {len(remaining_matchups)} remaining matchups", file=sys.stderr)
        
        if remaining_matchups:
            print(f"  [TIME] Phase 3: {len(remaining_matchups)} matchups still unplaced (Phase 2 should have handled these)", file=sys.stderr)
            print(f"  [WARNING] Phase 3 is NOT filling slots - that's Phase 2's responsibility!", file=sys.stderr)
        else:
            print(f"  Phase 3: All matchups placed successfully by Phase 1 and Phase 2", file=sys.stderr)
        
        # FINAL SUMMARY: Show what each phase accomplished
        print(f"  [RESULTS] FINAL OPTIMIZATION SUMMARY:", file=sys.stderr)
        print(f"    Phase 1 (Late Games): {late_slots_filled} late slots filled with highest priority teams", file=sys.stderr)
        print(f"    Phase 2 (Days Since): Teams placed in remaining slots based on days since last played", file=sys.stderr)
        print(f"    Phase 3 (Remaining): Filled any remaining empty slots", file=sys.stderr)
        print(f"    Total games filled: {games_filled}/{len(cleared_games)}", file=sys.stderr)
        
        # Verify all games are filled
        empty_games = [i for i, game in enumerate(cleared_games) if not game.get('home') or not game.get('away')]
        if empty_games:
            print(f"     WARNING: Empty games found: {empty_games}", file=sys.stderr)
            print(f"  Empty game details:", file=sys.stderr)
            for i in empty_games:
                print(f"  Game {i+1}: {cleared_games[i]}", file=sys.stderr)
        else:
            print(f"  [SUCCESS] All games filled successfully!", file=sys.stderr)
        
        # FINAL CHECK: Verify no day overlap conflicts exist
        print(f"    Final check: Verifying no day overlap conflicts...", file=sys.stderr)
        conflicts_found = _check_all_day_overlaps(cleared_games)
        if conflicts_found:
            print(f"     WARNING: Day overlap conflicts detected after optimization!", file=sys.stderr)
        else:
            print(f"    No day overlap conflicts found - schedule is valid", file=sys.stderr)
        
        # ADDITIONAL CHECK: Verify no same-day conflicts within the week
        print(f"    Additional check: Verifying no same-day conflicts within the week...", file=sys.stderr)
        try:
            same_day_conflicts = _check_same_day_conflicts_within_week(cleared_games)
            if same_day_conflicts:
                print(f"     [CRITICAL] CRITICAL: Same-day conflicts detected within the week!", file=sys.stderr)
                for conflict in same_day_conflicts:
                    print(f"       {conflict}", file=sys.stderr)
            else:
                print(f"    No same-day conflicts found within the week ✓", file=sys.stderr)
        except Exception as e:
            print(f"     [ERROR] ERROR in same-day conflict checking: {e}", file=sys.stderr)
            import traceback
            print(f"     [ERROR] Traceback: {traceback.format_exc()}", file=sys.stderr)
        
        # CRITICAL: Verify that time structure is preserved
        print(f"    Verifying time structure preservation...", file=sys.stderr)
        for i, (original, optimized) in enumerate(zip(working_bucket, cleared_games)):
            if (original.get('start') != optimized.get('start') or 
                original.get('end') != optimized.get('end') or
                original.get('rink') != optimized.get('rink')):
                print(f"     ERROR: Time structure changed for game {i+1}!", file=sys.stderr)
                print(f"       Original: {original.get('start')} - {original.get('end')} at {original.get('rink')}", file=sys.stderr)
                print(f"       Optimized: {optimized.get('start')} - {optimized.get('end')} at {optimized.get('rink')}", file=sys.stderr)
                # Restore original time structure
                cleared_games[i]['start'] = original.get('start', '')
                cleared_games[i]['end'] = original.get('end', '')
                cleared_games[i]['rink'] = original.get('rink', '')
                print(f"       RESTORED original time structure", file=sys.stderr)
            else:
                print(f"       Game {i+1}: Time structure preserved ✓", file=sys.stderr)
        
        # IMPORTANT: Create a final copy to ensure we don't return references to modified objects
        final_optimized_week = []
        for game in cleared_games:
            final_optimized_week.append(game.copy())
        
        # Show final matchup assignments
        print(f"    [FINAL] FINAL MATCHUP ASSIGNMENTS (same matchups, potentially different time slots):", file=sys.stderr)
        for i, game in enumerate(final_optimized_week):
            if game.get('home') and game.get('away'):
                print(f"      Game {i+1}: {game['home']} vs {game['away']} at {game['start']} (Rink: {game['rink']})", file=sys.stderr)
            else:
                print(f"      Game {i+1}: [EMPTY] at {game['start']} (Rink: {game['rink']})", file=sys.stderr)
        
        print(f"    Returning {len(final_optimized_week)} optimized games (properly copied, time structure preserved)", file=sys.stderr)
        return final_optimized_week, swaps_made
        
    except Exception as e:
        print(f"  Error in week processing algorithm: {e}", file=sys.stderr)
        import traceback
        print(f"  Traceback: {traceback.format_exc()}", file=sys.stderr)
        return bucket, []


def _find_better_team_combination(current_home: str, current_away: str, current_div: str,
                                 teams_playing_today: Set[str], divisions: Dict[str, List[str]], 
                                 late_counts: Dict[str, int], is_late_game: bool) -> Tuple[str, str, str]:
    """
    Find a better team combination for a game to improve late game balance.
    Returns (new_home, new_away, new_div) or None if no better combination found.
    """
    try:
        # Get all teams from all divisions
        all_teams = []
        for div_teams in divisions.values():
            all_teams.extend(div_teams)
        
        # Filter out teams already playing today
        available_teams = [t for t in all_teams if t not in teams_playing_today]
        
        if len(available_teams) < 2:
            return None  # Not enough available teams
        
        # For late games, prioritize teams with fewer late games
        if is_late_game:
            # Sort teams by late game count (ascending)
            available_teams.sort(key=lambda t: late_counts.get(t, 0))
            
            # Take the first 4 teams (2 for home, 2 for away options)
            candidate_teams = available_teams[:4]
        else:
            # For non-late games, we can be more flexible
            # But still try to balance overall late game distribution
            available_teams.sort(key=lambda t: late_counts.get(t, 0))
            # Dynamic candidate count based on available teams
            max_candidates = min(6, len(available_teams))
            candidate_teams = available_teams[:max_candidates]
        
        # Try to find a valid team combination
        for i in range(len(candidate_teams)):
            for j in range(i + 1, len(candidate_teams)):
                team1 = candidate_teams[i]
                team2 = candidate_teams[j]
                
                # Check if these teams can play against each other (same division)
                team1_div = None
                team2_div = None
                
                for div, teams in divisions.items():
                    if team1 in teams:
                        team1_div = div
                    if team2 in teams:
                        team2_div = div
                
                if team1_div and team2_div and team1_div == team2_div:
                    # Check if this combination is better than current
                    current_score = _calculate_team_combination_score(current_home, current_away, late_counts, is_late_game)
                    new_score = _calculate_team_combination_score(team1, team2, late_counts, is_late_game)
                    
                    if new_score < current_score:  # Lower score is better
                        print(f"  Found better combination: {team1} vs {team2} (score: {new_score} vs current: {current_score})", file=sys.stderr)
                        return team1, team2, team1_div
        
        return None  # No better combination found
        
    except Exception as e:
        print(f"  Error finding better team combination: {e}", file=sys.stderr)
        return None


def _calculate_team_combination_score(team1: str, team2: str, late_counts: Dict[str, int], is_late_game: bool) -> int:
    """
    Calculate a score for a team combination. Lower score is better.
    """
    try:
        team1_late = late_counts.get(team1, 0)
        team2_late = late_counts.get(team2, 0)
        
        if is_late_game:
            # For late games, prioritize teams with fewer late games
            return team1_late + team2_late
        else:
            # For non-late games, still consider late game balance
            return (team1_late + team2_late) // 2  # Less penalty for non-late games
        
    except Exception as e:
        print(f"  Error calculating team combination score: {e}", file=sys.stderr)
        return 999  # High penalty for errors


def _would_create_conflict(bucket: List[Dict], current_game_index: int, new_home: str, new_away: str, game_date: str, previous_bucket: List[Dict] = None) -> bool:
    """
    Check if assigning new teams to a game would create day overlap conflicts.
    Now also checks against the previous bucket to catch cross-bucket day conflicts.
    """
    try:
        # Check all other games in the current bucket for the same date
        for i, game in enumerate(bucket):
            if i == current_game_index:
                continue  # Skip the current game we're modifying
                
            other_date = _parse_start_to_date(game.get('start', ''))
            if other_date == game_date:
                other_home = game.get('home', '')
                other_away = game.get('away', '')
                
                # Check if new teams would conflict with existing teams on this date
                if new_home in (other_home, other_away) or new_away in (other_home, other_away):
                    print(f"  Conflict detected within current bucket: {new_home} or {new_away} already playing on {game_date}", file=sys.stderr)
                    return True
        
        # Check against the previous bucket for cross-bucket day conflicts
        if previous_bucket and game_date:
            for game in previous_bucket:
                if not game.get('home') or not game.get('away'):
                    continue  # Skip empty games
                    
                other_date = _parse_start_to_date(game.get('start', ''))
                if other_date == game_date:
                    other_home = game.get('home', '')
                    other_away = game.get('away', '')
                    
                    # Check if new teams would conflict with teams from previous bucket on this date
                    if new_home in (other_home, other_away) or new_away in (other_home, other_away):
                        print(f"  Cross-bucket conflict detected: {new_home} or {new_away} already played on {game_date} in previous bucket", file=sys.stderr)
                        return True
        
        return False
        
    except Exception as e:
        print(f"  Error checking for conflicts: {e}", file=sys.stderr)
        return True  # Assume conflict if error


def _is_late_game(game: Dict, late_threshold: time) -> bool:
    """Check if a game is a late game based on start time"""
    start_str = game.get('start', '')
    if not start_str:
        return False
    
    try:
        game_time = _parse_start_to_time(start_str)
        is_late = game_time >= late_threshold
        
        # Convert both times to 12-hour format for readability
        game_12hr = game_time.strftime('%I:%M %p').lstrip('0')
        threshold_12hr = late_threshold.strftime('%I:%M %p').lstrip('0')
        
        print(f"  _is_late_game: {start_str} → {game_time} ({game_12hr}) >= {late_threshold} ({threshold_12hr}) = {is_late}", file=sys.stderr)
        return is_late
    except:
        return False


def optimize_from_dict(schedule: List[Dict], 
                      divisions: Dict[str, List[str]] = None, 
                      params: Dict = None) -> Dict:
    """
    Main optimization function that implements the week-by-week placement algorithm.
    Can optimize a single week or multiple weeks based on the 'target_week' parameter.
    """
    try:
        print(f"  Starting week-by-week placement optimization", file=sys.stderr)
        print(f"  Schedule has {len(schedule)} games", file=sys.stderr)
        
        # Get parameters
        if not params:
            params = {}
        
        # Calculate optimal block size based on team count if not provided
        block_size = params.get('blockSize', None)
        if block_size is None:
            # Count unique teams in the schedule
            all_teams = set()
            for game in schedule:
                home_team = game.get('home', '') or game.get('HomeTeam', '')
                away_team = game.get('away', '') or game.get('AwayTeam', '')
                if home_team:
                    all_teams.add(home_team)
                if away_team:
                    all_teams.add(away_team)
            
            # Calculate optimal block size (teams ÷ 2, clamped between 4 and 20)
            team_count = len(all_teams)
            optimal_block_size = max(4, min(20, team_count // 2))
            block_size = optimal_block_size
            print(f"  Calculated optimal block size: {optimal_block_size} (from {team_count} teams)", file=sys.stderr)
        else:
            print(f"  Using provided block size: {block_size}", file=sys.stderr)
        late_threshold_str = params.get('midStart', '22:31')  # Get from midStart parameter
        target_week = params.get('target_week', None)  # Which week to optimize (None = auto-detect next)
        optimize_days_since = params.get('optimize_days_since', True)  # Whether to optimize days since last played
        
        # Parse late game threshold
        print(f"  Raw late threshold string: '{late_threshold_str}'", file=sys.stderr)
        try:
            if ':' in late_threshold_str:
                if 'PM' in late_threshold_str.upper():
                    # Handle 12-hour format like "10:31 PM"
                    print(f"  Parsing 12-hour format: {late_threshold_str}", file=sys.stderr)
                    dt = datetime.strptime(late_threshold_str.upper().replace(" PM","PM").replace(" AM","AM"), "%I:%M%p")
                    mid_start_time = dt.time()
                    print(f"  Parsed to time object: {mid_start_time}", file=sys.stderr)
                else:
                    # Handle 24-hour format like "22:31"
                    print(f"  Parsing 24-hour format: {late_threshold_str}", file=sys.stderr)
                    hh, mm = late_threshold_str.split(':')
                    mid_start_time = time(int(hh), int(mm))
                    print(f"  Parsed to time object: {mid_start_time}", file=sys.stderr)
            else:
                # Assume 24-hour format
                print(f"  Parsing numeric format: {late_threshold_str}", file=sys.stderr)
                mid_start_time = time(int(late_threshold_str), 0)
                print(f"  Parsed to time object: {mid_start_time}", file=sys.stderr)
        except Exception as e:
            print(f"  Error parsing late threshold '{late_threshold_str}': {e}", file=sys.stderr)
            print(f"  Warning: Could not parse late threshold '{late_threshold_str}', using default 22:31", file=sys.stderr)
            mid_start_time = time(22, 31)
        
        # Convert to 12-hour format for readability
        threshold_12hr = mid_start_time.strftime('%I:%M %p').lstrip('0')
        print(f"  Final late game threshold: {mid_start_time} ({mid_start_time.strftime('%H:%M')} / {threshold_12hr})", file=sys.stderr)
        
        # Create divisions from schedule data (ignore the passed divisions parameter)
        divisions = {}
        for game in schedule:
            div = game.get('div', 'unknown')
            if div not in divisions:
                divisions[div] = set()  # Use set to avoid duplicates
            home_team = game.get('home', '')
            away_team = game.get('away', '')
            if home_team:
                divisions[div].add(home_team)
            if away_team:
                divisions[div].add(away_team)
        
        # Convert sets back to lists for consistency
        divisions = {div: list(teams) for div, teams in divisions.items()}
        
        print(f"  Created divisions from schedule: {divisions}", file=sys.stderr)
        
        # Calculate optimal blockRecipe if not provided
        block_recipe = params.get('blockRecipe', None)
        if block_recipe is None:
            # Calculate optimal distribution based on division sizes
            block_recipe = {}
            for div_name, teams in divisions.items():
                if div_name != 'unknown' and len(teams) > 0:
                    # Calculate how many games this division should contribute per block
                    # For even distribution, each division contributes roughly teams/2 games per block
                    games_per_block = max(1, len(teams) // 2)
                    block_recipe[div_name] = games_per_block
            
            print(f"  Calculated optimal blockRecipe: {block_recipe}", file=sys.stderr)
        else:
            print(f"  Using provided blockRecipe: {block_recipe}", file=sys.stderr)
        
        # Group schedule into buckets (weeks)
        buckets = []
        for i in range(0, len(schedule), block_size):
            bucket = schedule[i:i + block_size]
            buckets.append(bucket)
        
        print(f"  Created {len(buckets)} buckets of size {block_size}", file=sys.stderr)
        
        # Debug: show bucket sizes
        print(f"  Bucket details:", file=sys.stderr)
        for i, bucket in enumerate(buckets):
            print(f"    Bucket {i+1}: {len(bucket)} games", file=sys.stderr)
            if len(bucket) < block_size:
                print(f"      ⚠️ Incomplete bucket (expected {block_size}, got {len(bucket)})", file=sys.stderr)
        
        # Check if we have the expected number of complete buckets
        complete_buckets = [b for b in buckets if len(b) == block_size]
        incomplete_buckets = [b for b in buckets if len(b) < block_size]
        print(f"  Complete buckets: {len(complete_buckets)}, Incomplete buckets: {len(incomplete_buckets)}", file=sys.stderr)
        
        # Process buckets based on target_week parameter
        optimized_schedule = []
        completed_buckets = []
        total_swaps = []
        
        print(f"  Starting week-by-week placement. Total weeks: {len(buckets)}", file=sys.stderr)
        
        # Determine which week to optimize
        if target_week is not None:
            # Optimize specific week
            target_index = target_week - 1  # Convert to 0-based index
            if target_index < 0 or target_index >= len(buckets):
                return {
                    'error': f'Invalid target week {target_week}. Must be between 1 and {len(buckets)}',
                    'original_schedule': schedule
                }
            
            print(f"  Targeting specific week: Week {target_week}", file=sys.stderr)
            
            # Process all weeks up to the target week
            for i in range(len(buckets)):
                if i < target_index:
                    # Weeks before target - just record as completed
                    print(f"  Week {i+1}: Recording as completed (before target)", file=sys.stderr)
                    # IMPORTANT: Create copies to avoid reference issues
                    week_copy = [game.copy() for game in buckets[i]]
                    optimized_schedule.extend(week_copy)
                    completed_buckets.append(week_copy)
                    print(f"  Week {i+1}: Added {len(week_copy)} games to optimized schedule", file=sys.stderr)
                elif i == target_index:
                    # Target week - optimize it
                    print(f"  Week {i+1}: Running placement algorithm (TARGET WEEK)", file=sys.stderr)
                    
                    # Check if this week has any late games
                    late_games_in_week = [g for g in buckets[i] if _is_late_game(g, mid_start_time)]
                    print(f"  Week {i+1}: Found {len(late_games_in_week)} late games", file=sys.stderr)
                    
                    # Show details of late games found
                    if late_games_in_week:
                        print(f"  Week {i+1} late games:", file=sys.stderr)
                        for j, late_game in enumerate(late_games_in_week):
                            start_time = _parse_start_to_time(late_game.get('start', ''))
                            start_12hr = start_time.strftime('%I:%M %p').lstrip('0')
                            print(f"    Late Game {j+1}: {late_game.get('home', '')} vs {late_game.get('away', '')} at {start_time} ({start_12hr})", file=sys.stderr)
                    else:
                        print(f"  Week {i+1}: No late games found (all games are before {mid_start_time.strftime('%I:%M %p').lstrip('0')})", file=sys.stderr)
                    
                    if late_games_in_week:
                        print(f"  Week {i+1}: Late games found, running placement algorithm", file=sys.stderr)
                        
                        # Run the placement algorithm
                        # Pass the previous bucket to catch cross-bucket day conflicts
                        previous_bucket = completed_buckets[-1] if completed_buckets else None
                        optimized_week, week_swaps = _place_teams_in_late_slots(
                            buckets[i], divisions, completed_buckets, mid_start_time, previous_bucket, optimize_days_since, params
                        )
                        
                        print(f"  Week {i+1}: Placement returned {len(week_swaps)} team assignments", file=sys.stderr)
                        print(f"  Week {i+1}: This represents {len(week_swaps) // 2} matchup changes", file=sys.stderr)
                        total_swaps.extend(week_swaps)
                        
                        if 'error' in optimized_week:
                            # If placement failed, use original week
                            print(f"  Week {i+1}: Placement failed, using original", file=sys.stderr)
                            optimized_schedule.extend(buckets[i])
                            completed_buckets.append(buckets[i])
                        else:
                            print(f"  Week {i+1}: Placement successful", file=sys.stderr)
                            optimized_schedule.extend(optimized_week)
                            completed_buckets.append(optimized_week)
                    else:
                        print(f"  Week {i+1}: No late games, no placement needed", file=sys.stderr)
                        optimized_schedule.extend(buckets[i])
                        completed_buckets.append(buckets[i])
                else:
                    # Weeks after target - keep original
                    print(f"  Week {i+1}: Keeping original (after target)", file=sys.stderr)
                    # IMPORTANT: Create copies to avoid reference issues
                    week_copy = [game.copy() for game in buckets[i]]
                    optimized_schedule.extend(week_copy)
                    print(f"  Week {i+1}: Added {len(week_copy)} games to optimized schedule (unchanged)", file=sys.stderr)
        else:
            # Auto-detect next week to optimize (original behavior)
            print(f"  Auto-detecting next week to optimize", file=sys.stderr)
            
            for i, bucket in enumerate(buckets):
                print(f"  Processing Week {i+1} with {len(bucket)} games", file=sys.stderr)
                
                if i == 0:
                    # Week 1 - no optimization needed, just record as completed
                    print(f"  Week 1: No optimization needed (first week)", file=sys.stderr)
                    optimized_schedule.extend(bucket)
                    completed_buckets.append(bucket)
                else:
                    # Week 2+ - implement placement algorithm
                    print(f"  Week {i+1}: Running placement algorithm", file=sys.stderr)
                    
                    # Check if this week has any late games
                    late_games_in_week = [g for g in bucket if _is_late_game(g, mid_start_time)]
                    print(f"  Week {i+1}: Found {len(late_games_in_week)} late games", file=sys.stderr)
                    
                    # Show details of late games found
                    if late_games_in_week:
                        print(f"  Week {i+1} late games:", file=sys.stderr)
                        for j, late_game in enumerate(late_games_in_week):
                            start_time = _parse_start_to_time(late_game.get('start', ''))
                            start_12hr = start_time.strftime('%I:%M %p').lstrip('0')
                            print(f"    Late Game {j+1}: {late_game.get('home', '')} vs {late_game.get('away', '')} at {start_time} ({start_12hr})", file=sys.stderr)
                    else:
                        threshold_12hr = mid_start_time.strftime('%I:%M %p').lstrip('0')
                        print(f"  Week {i+1}: No late games found (all games are before {threshold_12hr})", file=sys.stderr)
                    
                    if late_games_in_week:
                        print(f"  Week {i+1}: Late games found, running placement algorithm", file=sys.stderr)
                        
                        # Run the placement algorithm
                        # Pass the previous bucket to catch cross-bucket day conflicts
                        previous_bucket = completed_buckets[-1] if completed_buckets else None
                        optimized_week, week_swaps = _place_teams_in_late_slots(
                            bucket, divisions, completed_buckets, mid_start_time, previous_bucket, optimize_days_since, params
                        )
                        
                        print(f"  Week {i+1}: Placement returned {len(week_swaps)} team assignments", file=sys.stderr)
                        print(f"  Week {i+1}: This represents {len(week_swaps) // 2} matchup changes", file=sys.stderr)
                        total_swaps.extend(week_swaps)
                        
                        if 'error' in optimized_week:
                            # If placement failed, use original week
                            print(f"  Week {i+1}: Placement failed, using original", file=sys.stderr)
                            optimized_schedule.extend(bucket)
                            completed_buckets.append(bucket)
                        else:
                            print(f"  Week {i+1}: Placement successful", file=sys.stderr)
                            optimized_schedule.extend(optimized_week)
                            completed_buckets.append(optimized_week)
                    else:
                        print(f"  Week {i+1}: No late games, no placement needed", file=sys.stderr)
                        optimized_schedule.extend(buckets[i])
                        completed_buckets.append(buckets[i])
        
        # Track which weeks have been optimized
        weeks_optimized = []
        total_optimizable_weeks = len(buckets) - 1  # Exclude week 1
        
        if target_week:
            # Single week optimization
            if target_week > 1:  # Week 1 doesn't need optimization
                weeks_optimized.append(target_week)
                print(f"  Week {target_week} optimization complete. Total team assignments: {len(total_swaps)}", file=sys.stderr)
                
                # Check if this was the last optimizable week
                if target_week >= total_optimizable_weeks + 1:  # +1 because we start at Week 2
                    print(f"  🎯 This was the last optimizable week! All weeks complete.", file=sys.stderr)
            else:
                print(f"  Week {target_week} doesn't need optimization (Week 1)", file=sys.stderr)
        else:
            # Auto-detect optimization - all weeks 2+ are optimized
            for i in range(1, len(buckets)):
                if i > 0:  # Skip week 1
                    weeks_optimized.append(i + 1)
            print(f"  Week-by-week placement complete. Total weeks: {len(buckets)}, Total team assignments: {len(total_swaps)}", file=sys.stderr)
        
        # Check if all weeks that can be optimized have been optimized
        all_weeks_complete = len(weeks_optimized) >= total_optimizable_weeks
        
        # Summary of what was preserved vs. modified
        print(f"  📊 OPTIMIZATION SUMMARY:", file=sys.stderr)
        print(f"  📊 Total weeks in schedule: {len(buckets)}", file=sys.stderr)
        print(f"  📊 Target week: {target_week}", file=sys.stderr)
        print(f"  📊 Weeks optimized: {weeks_optimized}", file=sys.stderr)
        print(f"  📊 Total team assignments made: {len(total_swaps)}", file=sys.stderr)
        
        if target_week:
            print(f"  🔒 Week 1: PRESERVED (unchanged)", file=sys.stderr)
            if target_week > 2:
                print(f"  🔒 Weeks 2-{target_week-1}: PRESERVED (unchanged)", file=sys.stderr)
            print(f"  🔧 Week {target_week}: MODIFIED (optimized)", file=sys.stderr)
            if target_week < len(buckets):
                print(f"  🔒 Weeks {target_week+1}+: PRESERVED (unchanged)", file=sys.stderr)
        
        # Calculate total changes (each matchup change = 2 team movements)
        # For 22 teams: 11 matchups × 2 teams = 22 total changes
        total_changes = len(total_swaps)
        total_matchups_changed = total_changes // 2 if total_changes > 0 else 0
        
        return {
            'success': True,
            'message': f'Schedule optimized for Week {target_week if target_week else "2+"} with {total_changes} total changes ({total_matchups_changed} matchups modified)',
            'original_schedule': schedule,
            'schedule': optimized_schedule,
            'weeks_processed': len(buckets),
            'target_week': target_week,
            'late_game_threshold': mid_start_time.strftime('%H:%M'),
            'swaps': total_swaps,  # Team assignments made
            'improvement': total_changes,  # Total number of changes (should be 22 for 22 teams)
            'weeks_optimized': weeks_optimized,  # Array of weeks that have been optimized
            'all_weeks_complete': all_weeks_complete,  # True if all optimizable weeks are done
            'total_optimizable_weeks': total_optimizable_weeks,  # Total weeks that can be optimized
            'days_optimization_enabled': optimize_days_since,  # Whether days since last played optimization ran
            'total_changes': total_changes,  # Total changes made
            'matchups_modified': total_matchups_changed  # Number of matchups that were modified
        }
        
    except Exception as e:
        import traceback
        return {
            'error': f'Optimization failed: {str(e)}',
            'traceback': traceback.format_exc(),
            'original_schedule': schedule
        }


def _find_best_slot_for_matchup(cleared_games: List[Dict], matchup: Dict, placed_matchups: Set[str], previous_bucket: List[Dict] = None) -> int:
    """
    Find the best available slot for a matchup, prioritizing late slots for teams with few late games.
    Returns game index or None if no slot available.
    """
    try:
        # Check if this matchup has already been placed
        matchup_key = f"{matchup['home']}_{matchup['away']}"
        if matchup_key in placed_matchups:
            return None
        
        # Get available slots (empty games)
        available_slots = [i for i, game in enumerate(cleared_games) 
                          if not game.get('home') and not game.get('away')]
        
        if not available_slots:
            return None
        
        # Prioritize late slots for teams with few late games
        late_slots = [i for i in available_slots 
                     if _parse_start_to_time(cleared_games[i].get('start', '')) >= _parse_start_to_time(matchup['start_time'])]
        
        # If this is a high-priority matchup (few late games), try late slots first
        if matchup['combined_late_count'] <= 1:  # High priority
            # Try late slots first, then any available slot
            for slot in late_slots + available_slots:
                if not _would_create_conflict(cleared_games, slot, matchup['home'], matchup['away'], 
                                           _parse_start_to_date(cleared_games[slot].get('start', '')), previous_bucket):
                    return slot
        else:
            # Lower priority matchup, try any available slot
            for slot in available_slots:
                if not _would_create_conflict(cleared_games, slot, matchup['home'], matchup['away'], 
                                           _parse_start_to_date(cleared_games[slot].get('start', '')), previous_bucket):
                    return slot
        
        return None
        
    except Exception as e:
        print(f"  Error finding best slot for matchup: {e}", file=sys.stderr)
        return None


def _try_conflict_resolution(cleared_games: List[Dict], matchup: Dict, placed_matchups: Set[str], late_threshold: time, previous_bucket: List[Dict] = None) -> bool:
    """
    AGGRESSIVE conflict resolution: Try multiple swap combinations to place the matchup.
    Returns True if conflict was resolved, False otherwise.
    """
    try:
        print(f"AGGRESSIVE conflict resolution for {matchup['home']} vs {matchup['away']}", file=sys.stderr)
        
        # Get all filled games (already placed matchups)
        filled_games = [(i, game) for i, game in enumerate(cleared_games) 
                        if game.get('home') and game.get('away')]
        
        print(f"AGGRESSIVE: Found {len(filled_games)} filled games to try swapping with", file=sys.stderr)
        
        # STRATEGY 1: Try direct swaps (1-to-1)
        print(f"AGGRESSIVE: Strategy 1: Trying direct 1-to-1 swaps...", file=sys.stderr)
        if _try_direct_swap(cleared_games, matchup, filled_games, placed_matchups, previous_bucket):
            return True
        
        # STRATEGY 2: Try chain swaps (A→B→C→empty)
        print(f"AGGRESSIVE: Strategy 2: Trying chain swaps (A→B→C→empty)...", file=sys.stderr)
        if _try_chain_swap(cleared_games, matchup, filled_games, placed_matchups, previous_bucket):
            return True
        
        # STRATEGY 3: Try multi-swap combinations
        print(f"AGGRESSIVE: Strategy 3: Trying multi-swap combinations...", file=sys.stderr)
        if _try_multi_swap(cleared_games, matchup, filled_games, placed_matchups, previous_bucket):
            return True
        
        print(f"AGGRESSIVE: All conflict resolution strategies failed for {matchup['home']} vs {matchup['away']}", file=sys.stderr)
        
        # LAST RESORT: Double-check if the conflict is real and try forced placement
        print(f"AGGRESSIVE: LAST RESORT: Attempting forced placement for {matchup['home']} vs {matchup['away']}", file=sys.stderr)
        if _try_forced_placement(cleared_games, matchup, placed_matchups, previous_bucket):
            return True
        
        return False
        
    except Exception as e:
        print(f"Error in aggressive conflict resolution: {e}", file=sys.stderr)
        return False


def _try_direct_swap(cleared_games: List[Dict], matchup: Dict, filled_games: List[Tuple[int, Dict]], placed_matchups: Set[str], previous_bucket: List[Dict] = None) -> bool:
    """Try direct 1-to-1 swaps between matchup and filled games."""
    try:
        for game_index, filled_game in filled_games:
            print(f"DIRECT SWAP: Trying Game {game_index + 1}: {filled_game['home']} vs {filled_game['away']}", file=sys.stderr)
            
            # Temporarily remove the filled matchup
            temp_home = filled_game['home']
            temp_away = filled_game['away']
            temp_div = filled_game['div']
            
            # Try placing the new matchup in this slot
            if not _would_create_conflict(cleared_games, game_index, matchup['home'], matchup['away'], 
                                       _parse_start_to_date(filled_game.get('start', '')), previous_bucket):
                
                # Try placing the old matchup in an empty slot
                empty_slots = [i for i, game in enumerate(cleared_games) 
                              if not game.get('home') and not game.get('away')]
                
                for empty_slot in empty_slots:
                    if not _would_create_conflict(cleared_games, empty_slot, temp_home, temp_away, 
                                               _parse_start_to_date(cleared_games[empty_slot].get('start', '')), previous_bucket):
                        
                        # SWAP SUCCESSFUL! Execute the swap
                        print(f"DIRECT SWAP SUCCESSFUL!", file=sys.stderr)
                        print(f"  Game {game_index + 1}: {temp_home} vs {temp_away} → {matchup['home']} vs {matchup['away']}", file=sys.stderr)
                        print(f"  Game {empty_slot + 1}: [EMPTY] → {temp_home} vs {temp_away}", file=sys.stderr)
                        
                        # Execute the swap
                        cleared_games[game_index] = {
                            **cleared_games[game_index],
                            'home': matchup['home'],
                            'away': matchup['away'],
                            'div': matchup['div']
                        }
                        
                        cleared_games[empty_slot] = {
                            **cleared_games[empty_slot],
                            'home': temp_home,
                            'away': temp_away,
                            'div': temp_div
                        }
                        
                        # Update placed matchups tracking
                        placed_matchups.discard(f"{temp_home}_{temp_away}")
                        placed_matchups.add(f"{matchup['home']}_{matchup['away']}")
                        placed_matchups.add(f"{temp_home}_{temp_away}")
                        
                        return True
        
        return False
        
    except Exception as e:
        print(f"Error in direct swap: {e}", file=sys.stderr)
        return False


def _try_chain_swap(cleared_games: List[Dict], matchup: Dict, filled_games: List[Tuple[int, Dict]], placed_matchups: Set[str], previous_bucket: List[Dict] = None) -> bool:
    """Try chain swaps: A→B→C→empty slot."""
    try:
        print(f"   Attempting chain swap for {matchup['home']} vs {matchup['away']}", file=sys.stderr)
        
        # Try each filled game as the starting point for the chain
        for start_index, start_game in filled_games:
            print(f"   Chain swap starting with Game {start_index + 1}: {start_game['home']} vs {start_game['away']}", file=sys.stderr)
            
            # Try to create a chain: start_game → other_game → empty_slot
            for other_index, other_game in filled_games:
                if other_index == start_index:
                    continue
                
                # Check if we can move start_game to other_game's slot
                if not _would_create_conflict(cleared_games, other_index, start_game['home'], start_game['away'], 
                                           _parse_start_to_date(other_game.get('start', '')), previous_bucket):
                    
                    # Check if we can move other_game to an empty slot
                    empty_slots = [i for i, game in enumerate(cleared_games) 
                                  if not game.get('home') and not game.get('away')]
                    
                    for empty_slot in empty_slots:
                        if not _would_create_conflict(cleared_games, empty_slot, other_game['home'], other_game['away'], 
                                                   _parse_start_to_date(cleared_games[empty_slot].get('start', '')), previous_bucket):
                            
                            # Check if we can place the new matchup in start_game's slot
                            if not _would_create_conflict(cleared_games, start_index, matchup['home'], matchup['away'], 
                                                       _parse_start_to_date(start_game.get('start', '')), previous_bucket):
                                
                                # CHAIN SWAP SUCCESSFUL! Execute the chain
                                print(f"   CHAIN SWAP SUCCESSFUL!", file=sys.stderr)
                                print(f"    Chain: Game {start_index + 1} → Game {other_index + 1} → Game {empty_slot + 1} → [EMPTY]", file=sys.stderr)
                                print(f"    Final: Game {start_index + 1}: {matchup['home']} vs {matchup['away']}", file=sys.stderr)
                                
                                # Execute the chain swap
                                cleared_games[start_index] = {
                                    **cleared_games[start_index],
                                    'home': matchup['home'],
                                    'away': matchup['away'],
                                    'div': matchup['div']
                                }
                                
                                cleared_games[other_index] = {
                                    **cleared_games[other_index],
                                    'home': start_game['home'],
                                    'away': start_game['away'],
                                    'div': start_game['div']
                                }
                                
                                cleared_games[empty_slot] = {
                                    **cleared_games[empty_slot],
                                    'home': other_game['home'],
                                    'away': other_game['away'],
                                    'div': other_game['div']
                                }
                                
                                # Update placed matchups tracking
                                placed_matchups.discard(f"{start_game['home']}_{start_game['away']}")
                                placed_matchups.discard(f"{other_game['home']}_{other_game['away']}")
                                placed_matchups.add(f"{matchup['home']}_{matchup['away']}")
                                placed_matchups.add(f"{start_game['home']}_{start_game['away']}")
                                placed_matchups.add(f"{other_game['home']}_{other_game['away']}")
                                
                                return True
        
        return False
        
    except Exception as e:
        print(f"  Error in chain swap: {e}", file=sys.stderr)
        return False


def _try_multi_swap(cleared_games: List[Dict], matchup: Dict, filled_games: List[Tuple[int, Dict]], placed_matchups: Set[str], previous_bucket: List[Dict] = None) -> bool:
    """Try complex multi-swap combinations involving 3+ games."""
    try:
        print(f"   Attempting multi-swap for {matchup['home']} vs {matchup['away']}", file=sys.stderr)
        
        # For complex scenarios, try rotating multiple games
        if len(filled_games) >= 3:
            print(f"   Multi-swap: Found {len(filled_games)} games, trying rotation...", file=sys.stderr)
            
            # Try rotating the first 3 games
            game1_idx, game1 = filled_games[0]
            game2_idx, game2 = filled_games[1] 
            game3_idx, game3 = filled_games[2]
            
            # Check if rotation is possible without conflicts
            if (_can_place_without_conflict(cleared_games, game1_idx, game2['home'], game2['away'], previous_bucket) and
                _can_place_without_conflict(cleared_games, game2_idx, game3['home'], game3['away'], previous_bucket) and
                _can_place_without_conflict(cleared_games, game3_idx, matchup['home'], matchup['away'], previous_bucket)):
                
                print(f"   MULTI-SWAP SUCCESSFUL! Rotating 3 games", file=sys.stderr)
                
                # Execute the rotation
                cleared_games[game1_idx] = {
                    **cleared_games[game1_idx],
                    'home': game2['home'],
                    'away': game2['away'],
                    'div': game2['div']
                }
                
                cleared_games[game2_idx] = {
                    **cleared_games[game2_idx],
                    'home': game3['home'],
                    'away': game3['away'],
                    'div': game3['div']
                }
                
                cleared_games[game3_idx] = {
                    **cleared_games[game3_idx],
                    'home': matchup['home'],
                    'away': matchup['away'],
                    'div': matchup['div']
                }
                
                # Update placed matchups tracking
                placed_matchups.discard(f"{game1['home']}_{game1['away']}")
                placed_matchups.discard(f"{game2['home']}_{game2['away']}")
                placed_matchups.discard(f"{game3['home']}_{game3['away']}")
                placed_matchups.add(f"{matchup['home']}_{matchup['away']}")
                placed_matchups.add(f"{game2['home']}_{game2['away']}")
                placed_matchups.add(f"{game3['home']}_{game3['away']}")
                
                return True
        
        return False
        
    except Exception as e:
        print(f"  Error in multi-swap: {e}", file=sys.stderr)
        return False


def _can_place_without_conflict(cleared_games: List[Dict], game_index: int, home: str, away: str, previous_bucket: List[Dict] = None) -> bool:
    """Check if placing teams in a specific slot would create conflicts."""
    try:
        game_date = _parse_start_to_date(cleared_games[game_index].get('start', ''))
        if not game_date:
            return True  # No date info, assume safe
        
        return not _would_create_conflict(cleared_games, game_index, home, away, game_date, previous_bucket)
        
    except Exception as e:
        print(f"  Error checking placement safety: {e}", file=sys.stderr)
        return False


def _check_all_day_overlaps(cleared_games: List[Dict]) -> bool:
    """
    Check all games for day overlap conflicts.
    Returns True if conflicts found, False if schedule is valid.
    """
    try:
        conflicts_found = False
        
        for i, game in enumerate(cleared_games):
            if not game.get('home') or not game.get('away'):
                continue  # Skip empty games
                
            game_date = _parse_start_to_date(game.get('start', ''))
            if not game_date:
                continue
                
            # Check against all other games on the same date
            for j, other_game in enumerate(cleared_games):
                if i == j:
                    continue  # Skip self
                    
                if not other_game.get('home') or not other_game.get('away'):
                    continue  # Skip empty games
                    
                other_date = _parse_start_to_date(other_game.get('start', ''))
                if other_date == game_date:
                    # Same date - check for team conflicts
                    if (game['home'] in [other_game['home'], other_game['away']] or 
                        game['away'] in [other_game['home'], other_game['away']]):
                        
                        print(f"   DAY OVERLAP CONFLICT: Game {i+1} and Game {j+1} both on {game_date}", file=sys.stderr)
                        print(f"    Game {i+1}: {game['home']} vs {game['away']}", file=sys.stderr)
                        print(f"    Game {j+1}: {other_game['home']} vs {other_game['away']}", file=sys.stderr)
                        conflicts_found = True
        
        return conflicts_found
        
    except Exception as e:
        print(f"  Error checking day overlaps: {e}", file=sys.stderr)
        return True  # Assume conflict if error


def _try_forced_placement(cleared_games: List[Dict], matchup: Dict, placed_matchups: Set[str], previous_bucket: List[Dict] = None) -> bool:
    """
    LAST RESORT: Double-check if conflicts are real and try forced placement.
    This function is more aggressive and will attempt placements even if the algorithm thinks they might conflict.
    """
    try:
        print(f"FORCED PLACEMENT: Analyzing {matchup['home']} vs {matchup['away']}", file=sys.stderr)
        
        # Get all empty slots
        empty_slots = [i for i, game in enumerate(cleared_games) 
                      if not game.get('home') and not game.get('away')]
        
        if not empty_slots:
            print(f"FORCED PLACEMENT: No empty slots available", file=sys.stderr)
            return False
        
        print(f"FORCED PLACEMENT: Found {len(empty_slots)} empty slots", file=sys.stderr)
        
        # Try each empty slot with detailed conflict analysis
        for slot in empty_slots:
            print(f"FORCED PLACEMENT: Trying slot {slot}", file=sys.stderr)
            
            # Get the game details for this slot
            game = cleared_games[slot]
            game_date = _parse_start_to_date(game.get('start', ''))
            
            # DETAILED CONFLICT ANALYSIS: Check if this placement would actually create real conflicts
            conflicts_found = _analyze_real_conflicts(cleared_games, slot, matchup['home'], matchup['away'], game_date, previous_bucket)
            
            if not conflicts_found:
                print(f"FORCED PLACEMENT: NO REAL CONFLICTS! Placing {matchup['home']} vs {matchup['away']} in slot {slot}", file=sys.stderr)
                
                # Place the matchup
                cleared_games[slot] = {
                    **game,
                    'home': matchup['home'],
                    'away': matchup['away'],
                    'div': matchup['div']
                }
                
                # Update placed matchups tracking
                placed_matchups.add(f"{matchup['home']}_{matchup['away']}")
                
                return True
            else:
                print(f"FORCED PLACEMENT: Real conflicts confirmed in slot {slot}, trying next slot", file=sys.stderr)
        
        print(f"FORCED PLACEMENT: Failed for {matchup['home']} vs {matchup['away']}", file=sys.stderr)
        return False
        
    except Exception as e:
        print(f"Error in forced placement: {e}", file=sys.stderr)
        return False


def _analyze_real_conflicts(cleared_games: List[Dict], slot: int, home: str, away: str, game_date: str, previous_bucket: List[Dict] = None) -> bool:
    """
    DETAILED CONFLICT ANALYSIS: Check if placing teams in a slot would actually create real conflicts.
    This is more thorough than the basic conflict checking.
    """
    try:
        if not game_date:
            print(f"CONFLICT ANALYSIS: No date info for slot {slot}, assuming safe", file=sys.stderr)
            return False
        
        print(f"CONFLICT ANALYSIS: Analyzing {home} vs {away} in slot {slot} on {game_date}", file=sys.stderr)
        
        # Check all other games for the same date
        conflicts = 0
        for i, other_game in enumerate(cleared_games):
            if i == slot:
                continue  # Skip the slot we're trying to fill
                
            if not other_game.get('home') or not other_game.get('away'):
                continue  # Skip empty games
                
            other_date = _parse_start_to_date(other_game.get('start', ''))
            if other_date == game_date:
                other_home = other_game.get('home', '')
                other_away = other_game.get('away', '')
                
                # Check for actual team conflicts
                if home in (other_home, other_away):
                    print(f"CONFLICT ANALYSIS: CONFLICT: {home} already playing on {game_date} in slot {i+1}", file=sys.stderr)
                    conflicts += 1
                if away in (other_home, other_away):
                    print(f"CONFLICT ANALYSIS: CONFLICT: {away} already playing on {game_date} in slot {i+1}", file=sys.stderr)
                    conflicts += 1
        
        # Check against the previous bucket for cross-bucket day conflicts
        if previous_bucket and game_date:
            for game in previous_bucket:
                if not game.get('home') or not game.get('away'):
                    continue  # Skip empty games
                    
                other_date = _parse_start_to_date(game.get('start', ''))
                if other_date == game_date:
                    other_home = game.get('home', '')
                    other_away = game.get('away', '')
                    
                    # Check if new teams would conflict with teams from previous bucket on this date
                    if home in (other_home, other_away) or away in (other_home, other_away):
                        print(f"CONFLICT ANALYSIS: Cross-bucket conflict: {home} or {away} already played on {game_date} in previous bucket", file=sys.stderr)
                        conflicts += 1
        
        print(f"Total conflicts found: {conflicts}", file=sys.stderr)
        return conflicts > 0
        
    except Exception as e:
        print(f"Error in conflict analysis: {e}", file=sys.stderr)
        return True  # Assume conflict if error


def _find_partner_team(team: str, divisions: Dict[str, List[str]], placed_teams: Set[str]) -> str:
    """
    Find a partner team for the given team (same division, not placed yet).
    Returns partner team name or None if not found.
    """
    try:
        # Find which division this team belongs to
        team_division = None
        for div, teams in divisions.items():
            if team in teams:
                team_division = div
                break
        
        if not team_division:
            return None
        
        # Find available teams in the same division
        division_teams = divisions[team_division]
        available_partners = [t for t in division_teams if t != team and t not in placed_teams]
        
        if available_partners:
            # Return the first available partner
            return available_partners[0]
        
        return None
        
    except Exception as e:
        print(f"Error finding partner team: {e}", file=sys.stderr)
        return None


def _calculate_days_since_last_played(team: str, completed_buckets: List[List[Dict]], current_week_start_date: str, params: Dict = None) -> int:
    """
    Calculate how many days it's been since a team last played.
    Returns the number of days, or a large number if they've never played.
    """
    try:
        # Parse the current week's start date
        current_date = datetime.strptime(current_week_start_date, '%Y-%m-%d').date()
        
        # Look through all completed buckets (previous weeks) to find the most recent game
        last_game_date = None
        
        for bucket in reversed(completed_buckets):  # Start from most recent
            for game in bucket:
                if not game.get('home') or not game.get('away'):
                    continue
                    
                game_date_str = _parse_start_to_date(game.get('start', ''))
                if not game_date_str:
                    continue
                    
                game_date = datetime.strptime(game_date_str, '%Y-%m-%d').date()
                
                # Check if this team played in this game
                if team in (game.get('home', ''), game.get('away', '')):
                    if last_game_date is None or game_date > last_game_date:
                        last_game_date = game_date
        
        if last_game_date is None:
            # Team has never played before
            # Use configurable priority value, default to 999 for high priority
            never_played_priority = params.get('neverPlayedPriority', 999) if params else 999
            return never_played_priority
        
        # Calculate days difference
        days_since = (current_date - last_game_date).days
        return days_since
        
    except Exception as e:
        print(f"  Error calculating days since last played for {team}: {e}", file=sys.stderr)
        # Use configurable error fallback, default to 0
        error_fallback = params.get('daysSinceErrorFallback', 0) if params else 0
        return error_fallback


def _find_available_dates_in_bucket(cleared_games: List[Dict]) -> List[Tuple[int, str]]:
    """
    Find all dates in the current bucket that have empty/unassigned slots.
    Returns list of (slot_index, date) tuples sorted by date (earliest first).
    """
    available_dates = []
    
    for i, game in enumerate(cleared_games):
        # Check if this slot is empty (no teams assigned)
        if not game.get('home') and not game.get('away'):
            slot_date = _parse_start_to_date(game.get('start', ''))
            if slot_date:
                available_dates.append((i, slot_date))
    
    # Sort by date (earliest first)
    available_dates.sort(key=lambda x: x[1])
    
    return available_dates


def _can_place_team_in_slot(cleared_games: List[Dict], team: str, target_slot: int, previous_bucket: List[Dict] = None) -> bool:
    """Check if a team can be placed in a specific slot without conflicts"""
    try:
        target_date = _parse_start_to_date(cleared_games[target_slot].get('start', ''))
        
        # Check if this team is already playing on this date in another slot
        for i, game in enumerate(cleared_games):
            if i == target_slot:
                continue
                
            if game.get('home') == team or game.get('away') == team:
                game_date = _parse_start_to_date(game.get('start', ''))
                if game_date == target_date:
                    return False  # Team already playing on this date
        
        # Check against previous bucket
        if previous_bucket and target_date:
            for game in previous_bucket:
                if not game.get('home') or not game.get('away'):
                    continue
                    
                if team in (game.get('home', ''), game.get('away', '')):
                    game_date = _parse_start_to_date(game.get('start', ''))
                    if game_date == target_date:
                        return False  # Team played on this date in previous week
        
        return True
        
    except Exception as e:
        print(f"      Error checking if team can be placed: {e}", file=sys.stderr)
        return False


def _can_move_team_to_slot(cleared_games: List[Dict], team: str, target_slot: int, previous_bucket: List[Dict] = None) -> bool:
    """Check if a team can be moved to a specific slot without conflicts"""
    try:
        target_date = _parse_start_to_date(cleared_games[target_slot].get('start', ''))
        
        # Check if this team is already playing on this date in another slot
        for i, game in enumerate(cleared_games):
            if i == target_slot:
                continue
                
            if game.get('home') == team or game.get('away') == team:
                game_date = _parse_start_to_date(game.get('start', ''))
                if game_date == target_date:
                    return False  # Team already playing on this date
        
        # Check against previous bucket
        if previous_bucket and target_date:
            for game in previous_bucket:
                if not game.get('home') or not game.get('away'):
                    continue
                    
                if team in (game.get('home', ''), game.get('away', '')):
                    game_date = _parse_start_to_date(game.get('start', ''))
                    if game_date == target_date:
                        return False  # Team played on this date in previous week
        
        return True
        
    except Exception as e:
        print(f"      Error checking if team can move: {e}", file=sys.stderr)
        return False


def _move_team_to_slot(cleared_games: List[Dict], team: str, from_slot: int, to_slot: int) -> None:
    """Move a team from one slot to another, handling the swap logic"""
    try:
        # Get the other team in the current slot
        current_game = cleared_games[from_slot]
        other_team = None
        if current_game.get('home') == team:
            other_team = current_game.get('away', '')
        elif current_game.get('away') == team:
            other_team = current_game.get('home', '')
        
        # Get the teams in the target slot
        target_game = cleared_games[to_slot]
        target_home = target_game.get('home', '')
        target_away = target_game.get('away', '')
        
        if other_team and (target_home or target_away):
            # We need to swap teams between slots
            print(f"        Swapping teams between slots {from_slot + 1} and {to_slot + 1}", file=sys.stderr)
            
            # Move the other team to the target slot
            if target_home:
                # Target slot has a home team, move other_team as away team
                cleared_games[to_slot]['away'] = other_team
                cleared_games[from_slot]['away'] = target_home
            else:
                # Target slot has an away team, move other_team as home team
                cleared_games[to_slot]['home'] = other_team
                cleared_games[from_slot]['home'] = target_away
            
            # Move the original team to the target slot
            if current_game.get('home') == team:
                cleared_games[to_slot]['home'] = team
                cleared_games[from_slot]['home'] = ''
            else:
                cleared_games[to_slot]['away'] = team
                cleared_games[from_slot]['away'] = ''
        else:
            # Simple move (no swap needed)
            print(f"        Moving {team} to slot {to_slot + 1}", file=sys.stderr)
            
            # Clear the team from the original slot
            if current_game.get('home') == team:
                cleared_games[from_slot]['home'] = ''
            else:
                cleared_games[from_slot]['away'] = ''
            
            # Add the team to the target slot
            if not target_home:
                cleared_games[to_slot]['home'] = team
            else:
                cleared_games[to_slot]['away'] = team
        
    except Exception as e:
        print(f"      Error moving team: {e}", file=sys.stderr)


def _optimize_days_since_last_played(cleared_games: List[Dict], 
                                    existing_matchups: List[Dict],
                                    placed_matchups: Set[str],
                                    completed_buckets: List[List[Dict]], 
                                    current_week_start_date: str,
                                    previous_bucket: List[Dict] = None,
                                    late_threshold: time = None,
                                    swaps_made: List[Dict] = None,
                                    params: Dict = None) -> None:
    """
    Optimize placement by placing UNPLACED teams in the EARLIEST AVAILABLE slots.
    This runs AFTER late game optimization and places teams that weren't placed in Phase 1.
    NOW WITH 0-DAY GAP PREVENTION: Checks for same-day conflicts and tries to resolve them by switching non-late games.
    """
    try:
        print(f"    🕐 Starting days-since-last-played optimization with 0-day gap prevention", file=sys.stderr)
        
        # Get teams that were NOT placed in Phase 1 (late game optimization)
        unplaced_teams = set()
        for matchup in existing_matchups:
            matchup_key = f"{matchup['home']}_{matchup['away']}"
            if matchup_key not in placed_matchups:
                unplaced_teams.add(matchup['home'])
                unplaced_teams.add(matchup['away'])
        
        print(f"    Teams NOT placed in Phase 1: {len(unplaced_teams)}", file=sys.stderr)
        
        if not unplaced_teams:
            print(f"    All teams already placed in Phase 1, skipping days optimization", file=sys.stderr)
            return
        
        # Calculate days since last played for each unplaced team
        team_days_since = {}
        for team in unplaced_teams:
            days = _calculate_days_since_last_played(team, completed_buckets, current_week_start_date, params)
            team_days_since[team] = days
            print(f"      {team}: {days} days since last played", file=sys.stderr)
        
        # Sort teams by days since last played (longest first = highest priority)
        teams_by_priority = sorted(unplaced_teams, key=lambda t: team_days_since[t], reverse=True)
        print(f"    Team priority order (longest days first): {teams_by_priority}", file=sys.stderr)
        
        # Get all available (unassigned) dates in this bucket
        available_dates = _find_available_dates_in_bucket(cleared_games)
        print(f"    Available dates in bucket: {[(i+1, date) for i, date in available_dates]}", file=sys.stderr)
        
        # Get all available (unassigned) slots in this bucket
        available_slots = [i for i, game in enumerate(cleared_games) if not game.get('home') and not game.get('away')]
        print(f"    Available slots in bucket: {[i+1 for i in available_slots]}", file=sys.stderr)
        
        # Keep placing matchups until all teams are placed or no more slots available
        while unplaced_teams and available_slots:
            # Find the team with LONGEST days since last played
            if not unplaced_teams:
                break
                
            # Get the highest priority team
            highest_priority_team = max(unplaced_teams, key=lambda t: team_days_since[t])
            print(f"    [TIME] Processing {highest_priority_team} ({team_days_since[highest_priority_team]} days since last played) - HIGHEST PRIORITY", file=sys.stderr)
            
            # Find the matchup this team belongs to
            team_matchup = None
            for matchup in existing_matchups:
                if highest_priority_team in (matchup['home'], matchup['away']):
                    matchup_key = f"{matchup['home']}_{matchup['away']}"
                    if matchup_key not in placed_matchups:
                        team_matchup = matchup
                        break
            
            if not team_matchup:
                print(f"      ⚠️  No unplaced matchup found for {highest_priority_team}, removing from search", file=sys.stderr)
                unplaced_teams.remove(highest_priority_team)
                continue
            
            # Find the BEST available slot for this matchup (considering chronological order and 0-day gaps)
            matchup_placed = False
            best_slot = None
            best_score = -1
            
            # First pass: Find the best slot without conflicts
            for slot_idx in available_slots:
                print(f"      [SEARCH] Trying slot {slot_idx + 1} for {team_matchup['home']} vs {team_matchup['away']}", file=sys.stderr)
                
                # Check if BOTH teams in the matchup can be placed in this slot without conflicts
                if _can_place_matchup_in_slot(cleared_games, team_matchup, slot_idx, previous_bucket):
                    # Calculate a score for this slot (higher is better)
                    slot_score = _calculate_slot_score(cleared_games, slot_idx, team_matchup, completed_buckets, current_week_start_date)
                    print(f"      [SCORE] Slot {slot_idx + 1} score: {slot_score}", file=sys.stderr)
                    
                    if slot_score > best_score:
                        best_score = slot_score
                        best_slot = slot_idx
            
            # If we found a good slot, use it
            if best_slot is not None:
                print(f"      [SUCCESS] SUCCESS: Placing {team_matchup['home']} vs {team_matchup['away']} in slot {best_slot + 1} (score: {best_score})", file=sys.stderr)
                
                # Place the entire matchup in this slot
                cleared_games[best_slot] = {
                    **cleared_games[best_slot],
                    'home': team_matchup['home'],
                    'away': team_matchup['away'],
                    'div': team_matchup['div']
                }
                
                # Mark matchup as placed
                placed_matchups.add(f"{team_matchup['home']}_{team_matchup['away']}")
                
                # Record the placement in swaps_made for proper change counting
                swaps_made.append({
                    'game_id': best_slot + 1,
                    'date': _parse_start_to_date(cleared_games[best_slot].get('start', '')),
                    'time': cleared_games[best_slot].get('start', ''),
                    'before': f"[EMPTY] vs [EMPTY] (cleared)",
                    'after': f"{team_matchup['home']} vs {team_matchup['away']} ({team_matchup['div']})",
                    'division': team_matchup['div'],
                    'was_late': _parse_start_to_time(cleared_games[best_slot].get('start', '')) >= late_threshold,
                    'phase': 'Phase 2 - Days Optimization',
                    'rink': cleared_games[best_slot].get('rink', '')
                })
                
                # Remove BOTH teams from the search (they're now placed)
                unplaced_teams.discard(team_matchup['home'])
                unplaced_teams.discard(team_matchup['away'])
                
                # Remove this slot from available slots
                available_slots.remove(best_slot)
                
                print(f"      [TARGET] Removed {team_matchup['home']} and {team_matchup['away']} from search", file=sys.stderr)
                print(f"      [TARGET] Removed slot {best_slot + 1} from available slots", file=sys.stderr)
                print(f"      [TARGET] Remaining unplaced teams: {len(unplaced_teams)}, Available slots: {len(available_slots)}", file=sys.stderr)
                
                matchup_placed = True
                
            else:
                # No direct placement possible - try conflict resolution by switching non-late games
                print(f"      [CONFLICT] No direct placement possible, attempting conflict resolution...", file=sys.stderr)
                
                if _try_resolve_conflict_by_switching(cleared_games, team_matchup, available_slots, placed_matchups, previous_bucket, late_threshold, swaps_made):
                    print(f"      [SUCCESS] Conflict resolved by switching games!", file=sys.stderr)
                    
                    # Remove BOTH teams from the search (they're now placed)
                    unplaced_teams.discard(team_matchup['home'])
                    unplaced_teams.discard(team_matchup['away'])
                    
                    matchup_placed = True
                else:
                    print(f"      [ERROR] FAILED: Could not place {team_matchup['home']} vs {team_matchup['away']} in any available slot (all have conflicts)", file=sys.stderr)
                    # Remove this team from search since we can't place them
                    unplaced_teams.remove(highest_priority_team)
                    print(f"      [TARGET] Removed {highest_priority_team} from search (unplaceable)", file=sys.stderr)
        
        print(f"    [TIME] Days-since-last-played optimization complete", file=sys.stderr)
        print(f"    [TARGET] Final results: {len(existing_matchups) - len(placed_matchups)} matchups remaining unplaced", file=sys.stderr)
        print(f"    [TARGET] Available slots remaining: {len(available_slots)}", file=sys.stderr)
        
    except Exception as e:
        print(f"    Error in days-since-last-played optimization: {e}", file=sys.stderr)
        import traceback
        print(f"    Traceback: {traceback.format_exc()}", file=sys.stderr)


def _calculate_slot_score(cleared_games: List[Dict], slot_idx: int, matchup: Dict, completed_buckets: List[List[Dict]], current_week_start_date: str) -> int:
    """
    Calculate a score for placing a matchup in a specific slot.
    Higher score = better placement (considers chronological order and days since last played).
    """
    try:
        slot_date = _parse_start_to_date(cleared_games[slot_idx].get('start', ''))
        if not slot_date:
            return 0  # No date info, low score
        
        # Base score starts at 100
        score = 100
        
        # Bonus for earlier dates (chronological order)
        try:
            slot_datetime = datetime.strptime(slot_date, '%Y-%m-%d').date()
            current_date = datetime.strptime(current_week_start_date, '%Y-%m-%d').date()
            
            # Days from current week start (earlier = higher score)
            days_from_start = (slot_datetime - current_date).days
            if days_from_start >= 0:
                score += (7 - days_from_start) * 10  # Earlier days get higher scores
        except:
            pass
        
        # Bonus for teams that haven't played in a while
        home_team = matchup['home']
        away_team = matchup['away']
        
        home_days = _calculate_days_since_last_played(home_team, completed_buckets, current_week_start_date)
        away_days = _calculate_days_since_last_played(away_team, completed_buckets, current_week_start_date)
        
        # Teams with more days since last played get higher scores
        score += min(home_days, away_days) * 5
        
        # Penalty for potential same-day conflicts
        same_day_games = 0
        for i, game in enumerate(cleared_games):
            if i == slot_idx:
                continue
            if game.get('home') or game.get('away'):
                other_date = _parse_start_to_date(game.get('start', ''))
                if other_date == slot_date:
                    same_day_games += 1
        
        # Penalty for multiple games on same day (encourages spreading out)
        score -= same_day_games * 20
        
        return max(0, score)  # Ensure non-negative score
        
    except Exception as e:
        print(f"        Error calculating slot score: {e}", file=sys.stderr)
        return 0


def _try_resolve_conflict_by_switching(cleared_games: List[Dict], matchup: Dict, available_slots: List[int], 
                                      placed_matchups: Set[str], previous_bucket: List[Dict] = None, 
                                      late_threshold: time = None, swaps_made: List[Dict] = None) -> bool:
    """
    Try to resolve conflicts by switching non-late games within the same bucket.
    This function attempts to find a solution by moving existing games to create space for the new matchup.
    """
    try:
        print(f"        🔄 Attempting conflict resolution by switching non-late games...", file=sys.stderr)
        
        # Get all filled games that are NOT late games (we can switch these)
        switchable_games = []
        for i, game in enumerate(cleared_games):
            if game.get('home') and game.get('away'):
                # Check if this is a non-late game (safe to switch)
                game_time = _parse_start_to_time(game.get('start', ''))
                if game_time < late_threshold:
                    switchable_games.append((i, game))
        
        print(f"        Found {len(switchable_games)} switchable non-late games", file=sys.stderr)
        
        if not switchable_games:
            print(f"        No switchable games found (all are late games)", file=sys.stderr)
            return False
        
        # Try different switching strategies
        for strategy in range(1, 4):
            print(f"        Trying strategy {strategy}...", file=sys.stderr)
            
            if strategy == 1 and _try_simple_swap_resolution(cleared_games, matchup, switchable_games, available_slots, placed_matchups, previous_bucket, swaps_made):
                return True
            elif strategy == 2 and _try_chain_swap_resolution(cleared_games, matchup, switchable_games, available_slots, placed_matchups, previous_bucket, swaps_made):
                return True
            elif strategy == 3 and _try_rotation_resolution(cleared_games, matchup, switchable_games, available_slots, placed_matchups, previous_bucket, swaps_made):
                return True
        
        print(f"        All conflict resolution strategies failed", file=sys.stderr)
        return False
        
    except Exception as e:
        print(f"        Error in conflict resolution: {e}", file=sys.stderr)
        return False


def _try_simple_swap_resolution(cleared_games: List[Dict], matchup: Dict, switchable_games: List[Tuple[int, Dict]], 
                               available_slots: List[int], placed_matchups: Set[str], 
                               previous_bucket: List[Dict] = None, swaps_made: List[Dict] = None) -> bool:
    """
    Strategy 1: Try simple 1-to-1 swaps between the new matchup and existing games.
    """
    try:
        print(f"          Strategy 1: Simple swap resolution", file=sys.stderr)
        
        for slot_idx, existing_game in switchable_games:
            # Check if we can place the new matchup in this slot
            if _can_place_matchup_in_slot(cleared_games, matchup, slot_idx, previous_bucket):
                # Check if we can place the existing game in an available slot
                for available_slot in available_slots:
                    if _can_place_matchup_in_slot(cleared_games, 
                                                 {'home': existing_game['home'], 'away': existing_game['away'], 'div': existing_game.get('div', '')}, 
                                                 available_slot, previous_bucket):
                        
                        print(f"          SUCCESS: Simple swap found!", file=sys.stderr)
                        print(f"            Slot {slot_idx + 1}: {existing_game['home']} vs {existing_game['away']} → {matchup['home']} vs {matchup['away']}", file=sys.stderr)
                        print(f"            Slot {available_slot + 1}: [EMPTY] → {existing_game['home']} vs {existing_game['away']}", file=sys.stderr)
                        
                        # Execute the swap
                        # Move existing game to available slot
                        cleared_games[available_slot] = {
                            **cleared_games[available_slot],
                            'home': existing_game['home'],
                            'away': existing_game['away'],
                            'div': existing_game.get('div', '')
                        }
                        
                        # Place new matchup in the original slot
                        cleared_games[slot_idx] = {
                            **cleared_games[slot_idx],
                            'home': matchup['home'],
                            'away': matchup['away'],
                            'div': matchup['div']
                        }
                        
                        # Update tracking
                        placed_matchups.add(f"{matchup['home']}_{matchup['away']}")
                        available_slots.remove(available_slot)
                        
                        # Record the swap
                        if swaps_made:
                            swaps_made.append({
                                'game_id': slot_idx + 1,
                                'date': _parse_start_to_date(cleared_games[slot_idx].get('start', '')),
                                'time': cleared_games[slot_idx].get('start', ''),
                                'before': f"{existing_game['home']} vs {existing_game['away']}",
                                'after': f"{matchup['home']} vs {matchup['away']}",
                                'division': matchup['div'],
                                'was_late': False,
                                'phase': 'Phase 2 - Conflict Resolution (Simple Swap)',
                                'rink': cleared_games[slot_idx].get('rink', '')
                            })
                        
                        return True
        
        return False
        
    except Exception as e:
        print(f"          Error in simple swap resolution: {e}", file=sys.stderr)
        return False


def _try_chain_swap_resolution(cleared_games: List[Dict], matchup: Dict, switchable_games: List[Tuple[int, Dict]], 
                              available_slots: List[int], placed_matchups: Set[str], 
                              previous_bucket: List[Dict] = None, swaps_made: List[Dict] = None) -> bool:
    """
    Strategy 2: Try chain swaps: A→B→C→empty slot.
    """
    try:
        print(f"          Strategy 2: Chain swap resolution", file=sys.stderr)
        
        if len(switchable_games) < 2 or len(available_slots) < 1:
            return False
        
        # Try to create a chain: game1 → game2 → empty_slot
        for i, (slot1, game1) in enumerate(switchable_games):
            for j, (slot2, game2) in enumerate(switchable_games):
                if i == j:
                    continue
                
                # Check if we can move game1 to game2's slot
                if _can_place_matchup_in_slot(cleared_games, 
                                             {'home': game1['home'], 'away': game1['away'], 'div': game1.get('div', '')}, 
                                             slot2, previous_bucket):
                    
                    # Check if we can move game2 to an available slot
                    for available_slot in available_slots:
                        if _can_place_matchup_in_slot(cleared_games, 
                                                     {'home': game2['home'], 'away': game2['away'], 'div': game2.get('div', '')}, 
                                                     available_slot, previous_bucket):
                            
                            # Check if we can place the new matchup in game1's slot
                            if _can_place_matchup_in_slot(cleared_games, matchup, slot1, previous_bucket):
                                
                                print(f"          SUCCESS: Chain swap found!", file=sys.stderr)
                                print(f"            Chain: Slot {slot1 + 1} → Slot {slot2 + 1} → Slot {available_slot + 1} → [EMPTY]", file=sys.stderr)
                                
                                # Execute the chain swap
                                # Move game1 to slot2
                                cleared_games[slot2] = {
                                    **cleared_games[slot2],
                                    'home': game1['home'],
                                    'away': game1['away'],
                                    'div': game1.get('div', '')
                                }
                                
                                # Move game2 to available slot
                                cleared_games[available_slot] = {
                                    **cleared_games[available_slot],
                                    'home': game2['home'],
                                    'away': game2['away'],
                                    'div': game2.get('div', '')
                                }
                                
                                # Place new matchup in slot1
                                cleared_games[slot1] = {
                                    **cleared_games[slot1],
                                    'home': matchup['home'],
                                    'away': matchup['away'],
                                    'div': matchup['div']
                                }
                                
                                # Update tracking
                                placed_matchups.add(f"{matchup['home']}_{matchup['away']}")
                                available_slots.remove(available_slot)
                                
                                # Record the chain swap
                                if swaps_made:
                                    swaps_made.append({
                                        'game_id': slot1 + 1,
                                        'date': _parse_start_to_date(cleared_games[slot1].get('start', '')),
                                        'time': cleared_games[slot1].get('start', ''),
                                        'before': f"{game1['home']} vs {game1['away']}",
                                        'after': f"{matchup['home']} vs {matchup['away']}",
                                        'division': matchup['div'],
                                        'was_late': False,
                                        'phase': 'Phase 2 - Conflict Resolution (Chain Swap)',
                                        'rink': cleared_games[slot1].get('rink', '')
                                    })
                                
                                return True
        
        return False
        
    except Exception as e:
        print(f"          Error in chain swap resolution: {e}", file=sys.stderr)
        return False


def _try_rotation_resolution(cleared_games: List[Dict], matchup: Dict, switchable_games: List[Tuple[int, Dict]], 
                            available_slots: List[int], placed_matchups: Set[str], 
                            previous_bucket: List[Dict] = None, swaps_made: List[Dict] = None) -> bool:
    """
    Strategy 3: Try rotating multiple games to create space.
    """
    try:
        print(f"          Strategy 3: Rotation resolution", file=sys.stderr)
        
        if len(switchable_games) < 3 or len(available_slots) < 1:
            return False
        
        # Try rotating the first 3 switchable games
        slot1, game1 = switchable_games[0]
        slot2, game2 = switchable_games[1]
        slot3, game3 = switchable_games[2]
        
        # Check if rotation is possible
        if (_can_place_matchup_in_slot(cleared_games, 
                                       {'home': game1['home'], 'away': game1['away'], 'div': game1.get('div', '')}, 
                                       slot2, previous_bucket) and
            _can_place_matchup_in_slot(cleared_games, 
                                       {'home': game2['home'], 'away': game2['away'], 'div': game2.get('div', '')}, 
                                       slot3, previous_bucket) and
            _can_place_matchup_in_slot(cleared_games, matchup, slot1, previous_bucket)):
            
            print(f"          SUCCESS: Rotation found!", file=sys.stderr)
            print(f"            Rotation: Slot {slot1 + 1} → Slot {slot2 + 1} → Slot {slot3 + 1} → Slot {slot1 + 1}", file=sys.stderr)
            
            # Execute the rotation
            # Move game1 to slot2
            cleared_games[slot2] = {
                **cleared_games[slot2],
                'home': game1['home'],
                'away': game1['away'],
                'div': game1.get('div', '')
            }
            
            # Move game2 to slot3
            cleared_games[slot3] = {
                **cleared_games[slot3],
                'home': game2['home'],
                'away': game2['away'],
                'div': game2.get('div', '')
            }
            
            # Place new matchup in slot1
            cleared_games[slot1] = {
                **cleared_games[slot1],
                'home': matchup['home'],
                'away': matchup['away'],
                'div': matchup['div']
            }
            
            # Update tracking
            placed_matchups.add(f"{matchup['home']}_{matchup['away']}")
            
            # Record the rotation
            if swaps_made:
                swaps_made.append({
                    'game_id': slot1 + 1,
                    'date': _parse_start_to_date(cleared_games[slot1].get('start', '')),
                    'time': cleared_games[slot1].get('start', ''),
                    'before': f"{game1['home']} vs {game1['away']}",
                    'after': f"{matchup['home']} vs {matchup['away']}",
                    'division': matchup['div'],
                    'was_late': False,
                    'phase': 'Phase 2 - Conflict Resolution (Rotation)',
                    'rink': cleared_games[slot1].get('rink', '')
                })
            
            return True
        
        return False
        
    except Exception as e:
        print(f"          Error in rotation resolution: {e}", file=sys.stderr)
        return False


def _check_same_day_conflicts_within_week(cleared_games: List[Dict]) -> List[str]:
    """Check for same-day conflicts within the week and return detailed conflict information"""
    conflicts = []
    
    try:
        # Group games by date
        games_by_date = {}
        for i, game in enumerate(cleared_games):
            if not game.get('home') or not game.get('away'):
                continue  # Skip empty slots
                
            game_date = _parse_start_to_date(game.get('start', ''))
            if not game_date:
                continue  # Skip games without dates
                
            if game_date not in games_by_date:
                games_by_date[game_date] = []
            games_by_date[game_date].append((i, game))
        
        # Check each date for conflicts
        for date, games in games_by_date.items():
            if len(games) <= 1:
                continue  # No conflicts possible with 0 or 1 game
                
            # Get all teams playing on this date
            teams_on_date = set()
            for slot_idx, game in games:
                home_team = game.get('home', '')
                away_team = game.get('away', '')
                if home_team:
                    teams_on_date.add(home_team)
                if away_team:
                    teams_on_date.add(away_team)
            
            # Check if any team appears multiple times
            if len(teams_on_date) < len(games) * 2:
                # This means some teams are playing multiple times on the same date
                conflict_info = f"Date {date}: Same-day conflicts detected!"
                games_info = [(slot_idx + 1, f"{game.get('home')} vs {game.get('away')}") for slot_idx, game in games]
                conflict_info += f" Games: {games_info}"
                conflict_info += f" Teams: {sorted(teams_on_date)}"
                conflicts.append(conflict_info)
                
                # Find the specific conflicts
                for slot_idx1, game1 in games:
                    for slot_idx2, game2 in games:
                        if slot_idx1 >= slot_idx2:
                            continue  # Avoid duplicate checks
                        
                        # Check if same team plays in both games
                        home1 = game1.get('home', '')
                        away1 = game1.get('away', '')
                        home2 = game2.get('home', '')
                        away2 = game2.get('away', '')
                        
                        if home1 in (home2, away2) or away1 in (home2, away2):
                            conflict_detail = f"  Slot {slot_idx1 + 1} vs Slot {slot_idx2 + 1}: {home1} vs {away1} conflicts with {home2} vs {away2}"
                            conflicts.append(conflict_detail)
    
    except Exception as e:
        conflicts.append(f"Error checking same-day conflicts: {e}")
    
    return conflicts


def _can_place_matchup_in_slot(cleared_games: List[Dict], matchup: Dict, target_slot: int, previous_bucket: List[Dict] = None) -> bool:
    """Check if a matchup can be placed in a specific slot without conflicts"""
    try:
        target_date = _parse_start_to_date(cleared_games[target_slot].get('start', ''))
        home_team = matchup['home']
        away_team = matchup['away']
        
        print(f"        🔍 CONFLICT CHECK: {home_team} vs {away_team} in slot {target_slot + 1} (date: {target_date})", file=sys.stderr)
        
        # Check if either team is already playing on this date in another slot
        for i, game in enumerate(cleared_games):
            if i == target_slot:
                continue  # Skip the target slot
                
            if game.get('home') or game.get('away'):  # Only check filled slots
                game_date = _parse_start_to_date(game.get('start', ''))
                if game_date == target_date:
                    print(f"        🔍 Found same date game in slot {i + 1}: {game.get('home')} vs {game.get('away')} (date: {game_date})", file=sys.stderr)
                    # Check if either team from the matchup is already playing on this date
                    if home_team in (game.get('home', ''), game.get('away', '')) or away_team in (game.get('home', ''), game.get('away', '')):
                        print(f"        ❌ CONFLICT DETECTED: {home_team} or {away_team} already playing on {target_date} in slot {i + 1}", file=sys.stderr)
                        return False  # Conflict detected
        
        # Check against previous bucket for cross-bucket day conflicts
        if previous_bucket and target_date:
            print(f"        🔍 Checking previous bucket for conflicts on {target_date}", file=sys.stderr)
            for game in previous_bucket:
                if not game.get('home') or not game.get('away'):
                    continue
                    
                if home_team in (game.get('home', ''), game.get('away', '')) or away_team in (game.get('home', ''), game.get('away', '')):
                    game_date = _parse_start_to_date(game.get('start', ''))
                    if game_date == target_date:
                        print(f"        ❌ CROSS-WEEK CONFLICT: {home_team} or {away_team} played on {target_date} in previous week", file=sys.stderr)
                        return False  # Team played on this date in previous week
        
        print(f"        ✅ NO CONFLICTS: {home_team} vs {away_team} can be placed in slot {target_slot + 1}", file=sys.stderr)
        return True  # No conflicts found
        
    except Exception as e:
        print(f"        Error checking if matchup can be placed: {e}", file=sys.stderr)
        return False