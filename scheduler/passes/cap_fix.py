"""
Cap fix pass to ensure no team exceeds maximum gap between games.
"""

from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta
from ..models import Schedule, ScheduledGame, SwapLog
from ..config import SchedulerConfig


def cap_fix(schedule: Schedule, config: SchedulerConfig) -> Schedule:
    """
    Fix violations of maximum gap constraint by swapping games.
    
    Args:
        schedule: Current schedule
        config: Scheduler configuration
    
    Returns:
        Schedule: Updated schedule with cap violations fixed
    """
    print("Running cap fix pass...")
    
    # Find teams with gap violations
    violations = _find_gap_violations(schedule, config)
    
    if not violations:
        print("No gap violations found")
        return schedule
    
    print(f"Found {len(violations)} gap violations")
    
    # Try to fix each violation
    fixed_count = 0
    for team, violation_info in violations.items():
        if _fix_team_gap_violation(schedule, team, violation_info, config):
            fixed_count += 1
    
    print(f"Fixed {fixed_count} gap violations")
    
    return schedule


def _find_gap_violations(schedule: Schedule, config: SchedulerConfig) -> Dict[str, Dict]:
    """
    Find teams with gap violations.
    
    Returns:
        Dict mapping team name to violation info
    """
    violations = {}
    
    for team_name, team in schedule.teams.items():
        team_games = schedule.get_team_schedule(team_name)
        team_games.sort(key=lambda x: x.scheduled_date)
        
        # Check gaps between consecutive games
        for i in range(len(team_games) - 1):
            game1 = team_games[i]
            game2 = team_games[i + 1]
            
            gap_days = (game2.scheduled_date.date() - game1.scheduled_date.date()).days
            
            if gap_days > config.max_gap_days:
                violations[team_name] = {
                    'team': team_name,
                    'game1': game1,
                    'game2': game2,
                    'gap_days': gap_days,
                    'max_gap': config.max_gap_days
                }
                break  # Only report first violation per team
    
    return violations


def _fix_team_gap_violation(schedule: Schedule, team: str, violation_info: Dict, 
                          config: SchedulerConfig) -> bool:
    """
    Try to fix a gap violation for a specific team.
    
    Returns:
        bool: True if violation was fixed
    """
    game1 = violation_info['game1']
    game2 = violation_info['game2']
    
    # Find potential swaps that could reduce the gap
    potential_swaps = _find_potential_swaps(schedule, team, game1, game2, config)
    
    if not potential_swaps:
        return False
    
    # Try the best swap
    best_swap = min(potential_swaps, key=lambda x: x['improvement'])
    
    if best_swap['improvement'] > 0:
        _execute_swap(schedule, best_swap['game1'], best_swap['game2'])
        return True
    
    return False


def _find_potential_swaps(schedule: Schedule, team: str, game1: ScheduledGame, 
                         game2: ScheduledGame, config: SchedulerConfig) -> List[Dict]:
    """
    Find potential swaps that could reduce the gap for a team.
    
    Returns:
        List of potential swap configurations
    """
    swaps = []
    
    # Get all games between game1 and game2
    all_games = schedule.games
    all_games.sort(key=lambda x: x.scheduled_date)
    
    game1_idx = all_games.index(game1)
    game2_idx = all_games.index(game2)
    
    # Look for games in the gap period that could be swapped
    for i in range(game1_idx + 1, game2_idx):
        candidate_game = all_games[i]
        
        # Skip if candidate involves the same team
        if team in candidate_game.matchup.teams:
            continue
        
        # Check if swapping game1 with candidate would help
        swap1_improvement = _calculate_swap_improvement(
            schedule, game1, candidate_game, team, config
        )
        
        if swap1_improvement > 0:
            swaps.append({
                'game1': game1,
                'game2': candidate_game,
                'improvement': swap1_improvement,
                'type': 'swap1'
            })
        
        # Check if swapping game2 with candidate would help
        swap2_improvement = _calculate_swap_improvement(
            schedule, game2, candidate_game, team, config
        )
        
        if swap2_improvement > 0:
            swaps.append({
                'game1': game2,
                'game2': candidate_game,
                'improvement': swap2_improvement,
                'type': 'swap2'
            })
    
    return swaps


def _calculate_swap_improvement(schedule: Schedule, game1: ScheduledGame, 
                              game2: ScheduledGame, target_team: str,
                              config: SchedulerConfig) -> float:
    """
    Calculate improvement from swapping two games for a target team.
    
    Returns:
        float: Improvement score (positive = better)
    """
    # Get teams involved in both games
    teams1 = game1.matchup.teams
    teams2 = game2.matchup.teams
    
    # Check if swap would create new violations
    if not _is_swap_valid(schedule, game1, game2, config):
        return -1.0
    
    # Calculate current gaps for target team
    current_gaps = _get_team_gaps(schedule, target_team)
    
    # Simulate swap
    temp_schedule = _simulate_swap(schedule, game1, game2)
    new_gaps = _get_team_gaps(temp_schedule, target_team)
    
    # Calculate improvement
    improvement = 0.0
    
    # Penalty for exceeding max gap
    for gap in new_gaps:
        if gap > config.max_gap_days:
            improvement -= (gap - config.max_gap_days) * 10  # Heavy penalty
    
    # Bonus for reducing large gaps
    for i, (old_gap, new_gap) in enumerate(zip(current_gaps, new_gaps)):
        if new_gap < old_gap and old_gap > config.target_gap_days:
            improvement += (old_gap - new_gap)
    
    return improvement


def _is_swap_valid(schedule: Schedule, game1: ScheduledGame, game2: ScheduledGame,
                  config: SchedulerConfig) -> bool:
    """Check if swapping two games would create constraint violations."""
    teams1 = game1.matchup.teams
    teams2 = game2.matchup.teams
    
    # Check rest day constraints
    for team in teams1 + teams2:
        team_obj = schedule.teams[team]
        
        # Calculate rest days for both possible positions
        rest1 = team_obj.get_rest_days(game1.scheduled_date)
        rest2 = team_obj.get_rest_days(game2.scheduled_date)
        
        if rest1 < config.rest_min_days or rest2 < config.rest_min_days:
            return False
    
    return True


def _get_team_gaps(schedule: Schedule, team: str) -> List[int]:
    """Get gaps between consecutive games for a team."""
    team_games = schedule.get_team_schedule(team)
    team_games.sort(key=lambda x: x.scheduled_date)
    
    gaps = []
    for i in range(len(team_games) - 1):
        gap = (team_games[i + 1].scheduled_date.date() - 
               team_games[i].scheduled_date.date()).days
        gaps.append(gap)
    
    return gaps


def _simulate_swap(schedule: Schedule, game1: ScheduledGame, game2: ScheduledGame) -> Schedule:
    """Create a copy of schedule with two games swapped."""
    import copy
    
    # Deep copy the schedule
    new_schedule = copy.deepcopy(schedule)
    
    # Find the games in the new schedule
    for game in new_schedule.games:
        if game.game_id == game1.game_id:
            new_game1 = game
        elif game.game_id == game2.game_id:
            new_game2 = game
    
    # Swap the scheduled dates
    new_game1.scheduled_date, new_game2.scheduled_date = (
        new_game2.scheduled_date, new_game1.scheduled_date
    )
    
    return new_schedule


def _execute_swap(schedule: Schedule, game1: ScheduledGame, game2: ScheduledGame):
    """Execute a swap between two games."""
    # Swap the scheduled dates
    game1.scheduled_date, game2.scheduled_date = (
        game2.scheduled_date, game1.scheduled_date
    )
    
    # Update team states
    _update_team_states_after_swap(schedule, game1, game2)


def _update_team_states_after_swap(schedule: Schedule, game1: ScheduledGame, game2: ScheduledGame):
    """Update team states after a swap."""
    # Reset team states
    for team_name in schedule.teams:
        schedule.teams[team_name].last_played = None
        schedule.teams[team_name].eml_counts = {k: 0 for k in schedule.teams[team_name].eml_counts}
        schedule.teams[team_name].home_count = 0
        schedule.teams[team_name].away_count = 0
        schedule.teams[team_name].games_played = 0
    
    # Rebuild team states in chronological order
    sorted_games = sorted(schedule.games, key=lambda x: x.scheduled_date)
    
    for game in sorted_games:
        home_team = schedule.teams[game.matchup.home_team]
        away_team = schedule.teams[game.matchup.away_team]
        
        home_team.update_after_game(game.scheduled_date, True, game.slot.eml_category)
        away_team.update_after_game(game.scheduled_date, False, game.slot.eml_category)
