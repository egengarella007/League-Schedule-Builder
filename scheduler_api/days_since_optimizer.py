#!/usr/bin/env python3
"""
Days Since Last Played Optimizer
This script optimizes non-late game matchups based on days since last played,
starting from bucket 2 and working through all buckets in groups of 10.
"""

import sys
import json
from datetime import datetime, time
from typing import List, Dict, Tuple, Set
import requests

def _parse_start_to_time(start_str: str) -> time:
    """Parse start time string to time object."""
    try:
        if 'T' in start_str:
            # ISO format: "2025-09-05T21:00:00"
            time_part = start_str.split('T')[1]
            hours, minutes = map(int, time_part.split(':')[:2])
            return time(hours, minutes)
        else:
            # Try to parse as datetime
            dt = datetime.fromisoformat(start_str.replace('Z', '+00:00'))
            return dt.time()
    except Exception as e:
        print(f"[ERROR] Failed to parse time from {start_str}: {e}", file=sys.stderr)
        return time(22, 31)  # Default to late game threshold

def _parse_start_to_date(start_str: str) -> str:
    """Parse start string to date string (YYYY-MM-DD)."""
    try:
        if 'T' in start_str:
            # ISO format: "2025-09-05T21:00:00"
            return start_str.split('T')[0]
        else:
            # Try to parse as datetime
            dt = datetime.fromisoformat(start_str.replace('Z', '+00:00'))
            return dt.strftime('%Y-%m-%d')
    except Exception as e:
        print(f"[ERROR] Failed to parse date from {start_str}: {e}", file=sys.stderr)
        return ""

def _calculate_days_since_last_played(team: str, completed_buckets: List[List[Dict]], current_bucket: List[Dict], bucket_idx: int, previous_bucket: List[Dict] = None) -> int:
    """Calculate how many days ago a team last played."""
    try:
        # Find the most recent game for this team
        last_game_date = None
        
        # Check completed buckets (weeks that have been processed)
        for bucket in reversed(completed_buckets):
            for game in bucket:
                if game.get('home') == team or game.get('away') == team:
                    game_date = _parse_start_to_date(game.get('start', ''))
                    if game_date:
                        last_game_date = game_date
                        break
            if last_game_date:
                break
        
        # Check previous bucket (immediately preceding week)
        if not last_game_date and previous_bucket:
            for game in previous_bucket:
                if game.get('home') == team or game.get('away') == team:
                    game_date = _parse_start_to_date(game.get('start', ''))
                    if game_date:
                        last_game_date = game_date
                        break
        
        # Check current bucket (for teams already placed)
        if not last_game_date:
            for game in current_bucket:
                if game.get('home') == team or game.get('away') == team:
                    game_date = _parse_start_to_date(game.get('start', ''))
                    if game_date:
                        last_game_date = game_date
                        break
        
        if not last_game_date:
            # Team hasn't played yet
            return 999  # High priority for teams that haven't played
        
        # Get the date of the first available game in the current bucket being optimized
        current_bucket_date = None
        if bucket_idx < len(current_bucket):
            # Find the first game with a valid date in this bucket
            for game in current_bucket:
                game_date = _parse_start_to_date(game.get('start', ''))
                if game_date:
                    current_bucket_date = game_date
                    break
        
        if not current_bucket_date:
            # Fallback to current date if we can't get bucket date
            current_bucket_date = datetime.now().strftime('%Y-%m-%d')
        
        # Calculate days since last game
        try:
            last_date = datetime.strptime(last_game_date, '%Y-%m-%d').date()
            bucket_date = datetime.strptime(current_bucket_date, '%Y-%m-%d').date()
            days_diff = (bucket_date - last_date).days
            return days_diff
        except Exception:
            # If date parsing fails, return a default value
            return 7  # Assume 1 week ago
        
    except Exception as e:
        print(f"[ERROR] Error calculating days since last played for {team}: {e}", file=sys.stderr)
        return 7  # Default to 1 week ago

def _would_create_conflict(bucket: List[Dict], target_slot: int, new_home: str, new_away: str, target_date: str, previous_bucket: List[Dict] = None) -> bool:
    """Check if placing new_home vs new_away in target_slot would create same-day conflicts."""
    try:
        # Check if either team already plays on the target date in this bucket
        for i, game in enumerate(bucket):
            if i == target_slot:
                continue  # Skip the target slot
            
            if game.get('home') and game.get('away'):
                game_date = _parse_start_to_date(game.get('start', ''))
                if game_date == target_date:
                    # Same date - check if either team is involved
                    if game['home'] in [new_home, new_away] or game['away'] in [new_home, new_away]:
                        print(f"[CONFLICT] {new_home} or {new_away} already plays on {target_date} in slot {i+1}", file=sys.stderr)
                        return True
        
        # Check previous bucket for same-day conflicts
        if previous_bucket:
            for game in previous_bucket:
                if game.get('home') and game.get('away'):
                    game_date = _parse_start_to_date(game.get('start', ''))
                    if game_date == target_date:
                        # Same date - check if either team is involved
                        if game['home'] in [new_home, new_away] or game['away'] in [new_home, new_away]:
                            print(f"[CONFLICT] {new_home} or {new_away} already plays on {target_date} in previous week", file=sys.stderr)
                            return True
        
        return False
        
    except Exception as e:
        print(f"[ERROR] Error checking for conflicts: {e}", file=sys.stderr)
        return True  # Assume conflict if error

def _can_place_matchup_in_slot(bucket: List[Dict], matchup: Dict, target_slot: int, previous_bucket: List[Dict] = None) -> bool:
    """Check if a matchup can be placed in a target slot without conflicts."""
    try:
        home_team = matchup.get('home')
        away_team = matchup.get('away')
        
        if not home_team or not away_team:
            return False
        
        # Get the target slot's date
        target_date = _parse_start_to_date(bucket[target_slot].get('start', ''))
        if not target_date:
            return False
        
        # Check for conflicts
        if _would_create_conflict(bucket, target_slot, home_team, away_team, target_date, previous_bucket):
            return False
        
        return True
        
    except Exception as e:
        print(f"[ERROR] Error checking if matchup can be placed: {e}", file=sys.stderr)
        return False

def optimize_days_since_last_played(schedule_data: Dict, target_bucket: int = None, late_threshold: time = time(22, 31)) -> Tuple[Dict, List[Dict]]:
    """
    Optimize non-late game matchups based on days since last played.
    Processes ONE bucket at a time (one week at a time).
    """
    try:
        print(f"[DAYS] Starting Days Since Last Played optimization", file=sys.stderr)
        print(f"[DAYS] Late game threshold: {late_threshold}", file=sys.stderr)
        
        # Extract data
        buckets = schedule_data.get('buckets', [])
        if len(buckets) < 2:
            print(f"[ERROR] Need at least 2 buckets, got {len(buckets)}", file=sys.stderr)
            return schedule_data, []
        
        # Determine which bucket to optimize
        if target_bucket is None:
            # Default: start from bucket 2 (index 1)
            bucket_idx = 1
        else:
            # Use specified bucket (convert from 1-based to 0-based)
            bucket_idx = target_bucket - 1
            if bucket_idx < 1 or bucket_idx >= len(buckets):
                print(f"[ERROR] Invalid target bucket {target_bucket}, must be between 2 and {len(buckets)}", file=sys.stderr)
                return schedule_data, []
        
        print(f"[DAYS] Processing bucket {bucket_idx + 1} (week {bucket_idx + 1})", file=sys.stderr)
        
        # Get the specific bucket to optimize
        bucket = buckets[bucket_idx]
        print(f"[DAYS] Bucket {bucket_idx + 1} has {len(bucket)} games", file=sys.stderr)
        
        # Log initial bucket state for debugging
        print(f"[DAYS] Initial bucket {bucket_idx + 1} state:", file=sys.stderr)
        for i, game in enumerate(bucket):
            print(f"[DAYS]   Slot {i+1}: {game.get('home', 'EMPTY')} vs {game.get('away', 'EMPTY')} at {game.get('start', 'NO_TIME')}", file=sys.stderr)
        
        # Get previous bucket for conflict checking
        previous_bucket = buckets[bucket_idx - 1] if bucket_idx > 0 else None
        
        # Find non-late game slots in this bucket
        non_late_slots = []
        for i, game in enumerate(bucket):
            if game.get('home') and game.get('away'):
                # Game already has teams - check if it's a late game
                game_time = _parse_start_to_time(game.get('start', ''))
                print(f"[DAYS] Slot {i+1}: {game.get('home')} vs {game.get('away')} at {game.get('start')} -> time: {game_time} (late threshold: {late_threshold})", file=sys.stderr)
                if game_time < late_threshold:
                    non_late_slots.append(i)
                    print(f"[DAYS]   -> NON-LATE (can be moved)", file=sys.stderr)
                else:
                    print(f"[DAYS]   -> LATE (cannot be moved)", file=sys.stderr)
            else:
                # Empty slot - check if it would be a late game
                game_time = _parse_start_to_time(game.get('start', ''))
                if game_time < late_threshold:
                    non_late_slots.append(i)
        
        print(f"[DAYS] Bucket {bucket_idx + 1}: Found {len(non_late_slots)} non-late game slots", file=sys.stderr)
        print(f"[DAYS] Non-late slots: {[i+1 for i in non_late_slots]}", file=sys.stderr)
        
        if not non_late_slots:
            print(f"[DAYS] Bucket {bucket_idx + 1}: No non-late game slots to optimize", file=sys.stderr)
            return schedule_data, []
        
        # Get all teams that could be placed in non-late slots
        # SIMPLIFIED: Just get all teams that start in non-late slots for now
        available_teams = set()
        for slot_idx in non_late_slots:
            game = bucket[slot_idx]
            if game.get('home') and game.get('away'):
                # This slot has teams - add both teams
                available_teams.add(game['home'])
                available_teams.add(game['away'])
                print(f"[DAYS] Added teams from slot {slot_idx + 1}: {game['home']} and {game['away']}", file=sys.stderr)
        
        print(f"[DAYS] Bucket {bucket_idx + 1}: Found {len(available_teams)} teams that could be optimized", file=sys.stderr)
        print(f"[DAYS] Available teams: {list(available_teams)}", file=sys.stderr)
        
        if not available_teams:
            print(f"[DAYS] Bucket {bucket_idx + 1}: No teams available for optimization", file=sys.stderr)
            return schedule_data, []
        
        # Calculate days since last played for each team
        team_days_since = {}
        for team in available_teams:
            days = _calculate_days_since_last_played(team, buckets[:bucket_idx], bucket, bucket_idx, previous_bucket)
            team_days_since[team] = days
            print(f"[DAYS] {team}: {days} days since last played", file=sys.stderr)
        
        # Sort teams by priority (longest days first = highest priority)
        teams_by_priority = sorted(available_teams, key=lambda t: team_days_since[t], reverse=True)
        print(f"[DAYS] Teams by priority (longest days first): {teams_by_priority[:5]}...", file=sys.stderr)
        
        # Process teams by priority - ONE BUCKET AT A TIME
        processed_teams = set()
        changes_made = []
        
        # Keep placing matchups until all teams are placed or no more slots available
        while available_teams and non_late_slots:
            # Find the team with LONGEST days since last played
            if not available_teams:
                break
                
            # Get the highest priority team
            highest_priority_team = max(available_teams, key=lambda t: team_days_since[t])
            print(f"[DAYS] Processing {highest_priority_team} ({team_days_since[highest_priority_team]} days since last played) - HIGHEST PRIORITY", file=sys.stderr)
            
            # Find the matchup this team belongs to
            team_matchup = None
            for game in bucket:
                if highest_priority_team in (game.get('home'), game.get('away')):
                    # Check if this is a non-late game slot
                    game_time = _parse_start_to_time(game.get('start', ''))
                    if game_time < late_threshold:
                        team_matchup = game
                        break
            
            if not team_matchup:
                print(f"[DAYS] Warning: No non-late game matchup found for {highest_priority_team}, removing from search", file=sys.stderr)
                available_teams.remove(highest_priority_team)
                continue
            
            # Get the opponent
            opponent = team_matchup.get('away') if team_matchup.get('home') == highest_priority_team else team_matchup.get('home')
            if not opponent:
                print(f"[DAYS] Warning: No opponent found for {highest_priority_team}", file=sys.stderr)
                available_teams.remove(highest_priority_team)
                continue
            
            if opponent not in available_teams:
                print(f"[DAYS] Opponent {opponent} not available, removing {highest_priority_team} from search", file=sys.stderr)
                available_teams.remove(highest_priority_team)
                continue
            
            print(f"[DAYS] Found matchup: {highest_priority_team} vs {opponent}", file=sys.stderr)
            
            # Find the EARLIEST available non-late slot for this matchup
            matchup_placed = False
            for slot_idx in non_late_slots[:]:  # Copy list to allow modification
                print(f"[DAYS] Trying slot {slot_idx + 1} for {highest_priority_team} vs {opponent}", file=sys.stderr)
                
                # Check if BOTH teams in the matchup can be placed in this slot without conflicts
                if _can_place_matchup_in_slot(bucket, team_matchup, slot_idx, previous_bucket):
                    print(f"[DAYS] SUCCESS: {highest_priority_team} vs {opponent} can be placed in slot {slot_idx + 1}", file=sys.stderr)
                    
                    # Record the change before making it
                    old_home = bucket[slot_idx].get('home', '')
                    old_away = bucket[slot_idx].get('away', '')
                    
                    # SWAP the matchups to avoid losing games
                    # Find where the current matchup is located
                    orig_idx = None
                    for i, game in enumerate(bucket):
                        if (game.get('home') == highest_priority_team and game.get('away') == opponent) or \
                           (game.get('home') == opponent and game.get('away') == highest_priority_team):
                            orig_idx = i
                            break
                    
                    if orig_idx is not None and orig_idx != slot_idx:
                        # Swap the matchups
                        bucket[orig_idx], bucket[slot_idx] = bucket[slot_idx], bucket[orig_idx]
                        print(f"[DAYS] SWAPPED: {highest_priority_team} vs {opponent} moved from slot {orig_idx + 1} to slot {slot_idx + 1}", file=sys.stderr)
                    else:
                        # Place the matchup in the slot
                        bucket[slot_idx] = {
                            **bucket[slot_idx],
                            'home': highest_priority_team,
                            'away': opponent,
                            'div': team_matchup.get('div', 'unknown')
                        }
                        print(f"[DAYS] PLACED: {highest_priority_team} vs {opponent} in slot {slot_idx + 1}", file=sys.stderr)
                    
                    # Record the change
                    change_record = {
                        'bucket': bucket_idx + 1,
                        'slot': slot_idx + 1,
                        'team1': highest_priority_team,
                        'team2': opponent,
                        'days_since': team_days_since[highest_priority_team],
                        'old_home': old_home,
                        'old_away': old_away,
                        'new_home': highest_priority_team,
                        'new_away': opponent,
                        'type': 'days_optimization'
                    }
                    changes_made.append(change_record)
                    
                    # Remove BOTH teams from the search (they're now placed)
                    available_teams.remove(highest_priority_team)
                    available_teams.remove(opponent)
                    
                    # Remove this slot from available slots
                    non_late_slots.remove(slot_idx)
                    
                    print(f"[DAYS] Removed {highest_priority_team} and {opponent} from search", file=sys.stderr)
                    print(f"[DAYS] Removed slot {slot_idx + 1} from available slots", file=sys.stderr)
                    print(f"[DAYS] Remaining teams: {len(available_teams)}, Available slots: {len(non_late_slots)}", file=sys.stderr)
                    
                    matchup_placed = True
                    # DON'T break here - continue processing more matchups!
                    # This is the key fix - we want to optimize ALL matchups, not just one
                    # Remove the break to process ALL matchups aggressively
                else:
                    print(f"[DAYS] CONFLICT: Cannot place {highest_priority_team} vs {opponent} in slot {slot_idx + 1} (same-day conflict)", file=sys.stderr)
                    # Continue to next slot (don't break - try next available slot)
            
            if not matchup_placed:
                print(f"[DAYS] FAILED: Could not place {highest_priority_team} vs {opponent} in any available slot (all have conflicts)", file=sys.stderr)
                # Remove this team from search since we can't place them
                available_teams.remove(highest_priority_team)
                print(f"[DAYS] Removed {highest_priority_team} from search (unplaceable)", file=sys.stderr)
        
        print(f"[DAYS] Bucket {bucket_idx + 1} optimization complete", file=sys.stderr)
        print(f"[DAYS] Final results: {len(available_teams)} teams remaining unplaced", file=sys.stderr)
        print(f"[DAYS] Available slots remaining: {len(non_late_slots)}", file=sys.stderr)
        print(f"[DAYS] Total changes made: {len(changes_made)}", file=sys.stderr)
        
        # Log final bucket state for debugging
        print(f"[DAYS] Final bucket {bucket_idx + 1} state:", file=sys.stderr)
        for i, game in enumerate(bucket):
            print(f"[DAYS]   Slot {i+1}: {game.get('home', 'EMPTY')} vs {game.get('away', 'EMPTY')} at {game.get('start', 'NO_TIME')}", file=sys.stderr)
        
        return schedule_data, changes_made
        
    except Exception as e:
        print(f"[ERROR] Error in days optimization: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)
        return schedule_data, []

def main():
    """Main function to run the days since last played optimization."""
    try:
        # Read input from stdin
        input_data = sys.stdin.read()
        if not input_data:
            print("[ERROR] No input data provided", file=sys.stderr)
            sys.exit(1)
        
        # Parse the input
        try:
            data = json.loads(input_data)
        except json.JSONDecodeError as e:
            print(f"[ERROR] Failed to parse JSON input: {e}", file=sys.stderr)
            sys.exit(1)
        
        # Extract parameters
        schedule_data = data.get('schedule_data', {})
        late_threshold_str = data.get('late_threshold', '22:31')
        
        # Parse late threshold
        try:
            late_hours, late_minutes = map(int, late_threshold_str.split(':'))
            late_threshold = time(late_hours, late_minutes)
        except Exception as e:
            print(f"[ERROR] Failed to parse late threshold {late_threshold_str}: {e}", file=sys.stderr)
            late_threshold = time(22, 31)  # Default
        
        print(f"[DAYS] Starting optimization with late threshold: {late_threshold}", file=sys.stderr)
        
        # Run the optimization
        optimized_schedule, changes = optimize_days_since_last_played(schedule_data, late_threshold=late_threshold)
        
        # Prepare output
        output = {
            'success': True,
            'optimized_schedule': optimized_schedule,
            'changes_made': changes,
            'total_changes': len(changes)
        }
        
        # Output to stdout (this will be captured by the API)
        print(json.dumps(output))
        
    except Exception as e:
        print(f"[ERROR] Unexpected error in main: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)
        
        error_output = {
            'success': False,
            'error': str(e),
            'changes_made': [],
            'total_changes': 0
        }
        print(json.dumps(error_output))
        sys.exit(1)

if __name__ == "__main__":
    main()
