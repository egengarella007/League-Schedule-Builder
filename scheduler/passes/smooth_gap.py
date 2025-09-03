"""
Gap smoothing pass to improve the distribution of gaps between games.
"""

from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta
from ..models import Schedule, ScheduledGame, SwapLog
from ..config import SchedulerConfig


def smooth_gaps(schedule: Schedule, config: SchedulerConfig) -> Schedule:
    """
    Smooth gaps between games to approach target gap days.
    
    Args:
        schedule: Current schedule
        config: Scheduler configuration
    
    Returns:
        Schedule: Updated schedule with smoothed gaps
    """
    print("Running gap smoothing pass...")
    
    # Calculate current gap distribution
    gap_stats = _calculate_gap_statistics(schedule)
    print(f"Current gap stats: avg={gap_stats['avg_gap']:.1f}, std={gap_stats['std_gap']:.1f}")
    
    # Find teams with poor gap distributions
    teams_to_improve = _find_teams_with_poor_gaps(schedule, config)
    
    if not teams_to_improve:
        print("No teams need gap smoothing")
        return schedule
    
    print(f"Found {len(teams_to_improve)} teams needing gap smoothing")
    
    # Try to improve gaps for each team
    improvements_made = 0
    max_iterations = 10  # Prevent infinite loops
    
    for iteration in range(max_iterations):
        iteration_improvements = 0
        
        for team_name in teams_to_improve:
            if _improve_team_gaps(schedule, team_name, config):
                iteration_improvements += 1
        
        if iteration_improvements == 0:
            break
        
        improvements_made += iteration_improvements
        print(f"Iteration {iteration + 1}: Made {iteration_improvements} improvements")
    
    print(f"Total improvements made: {improvements_made}")
    
    return schedule


def _calculate_gap_statistics(schedule: Schedule) -> Dict:
    """Calculate statistics about gaps in the schedule."""
    all_gaps = []
    
    for team_name in schedule.teams:
        team_gaps = _get_team_gaps(schedule, team_name)
        all_gaps.extend(team_gaps)
    
    if not all_gaps:
        return {'avg_gap': 0, 'std_gap': 0, 'min_gap': 0, 'max_gap': 0}
    
    import statistics
    
    return {
        'avg_gap': statistics.mean(all_gaps),
        'std_gap': statistics.stdev(all_gaps) if len(all_gaps) > 1 else 0,
        'min_gap': min(all_gaps),
        'max_gap': max(all_gaps)
    }


def _find_teams_with_poor_gaps(schedule: Schedule, config: SchedulerConfig) -> List[str]:
    """Find teams with gaps that deviate significantly from target."""
    teams_to_improve = []
    
    for team_name in schedule.teams:
        team_gaps = _get_team_gaps(schedule, team_name)
        
        if not team_gaps:
            continue
        
        # Calculate how far gaps are from target
        gap_deviations = [abs(gap - config.target_gap_days) for gap in team_gaps]
        avg_deviation = sum(gap_deviations) / len(gap_deviations)
        
        # If average deviation is significant, mark for improvement
        if avg_deviation > 2.0:  # More than 2 days from target on average
            teams_to_improve.append(team_name)
    
    return teams_to_improve


def _improve_team_gaps(schedule: Schedule, team_name: str, config: SchedulerConfig) -> bool:
    """
    Try to improve gaps for a specific team.
    
    Returns:
        bool: True if improvement was made
    """
    team_games = schedule.get_team_schedule(team_name)
    team_games.sort(key=lambda x: x.scheduled_date)
    
    if len(team_games) < 2:
        return False
    
    # Find the worst gap (furthest from target)
    worst_gap_idx = None
    worst_deviation = 0
    
    for i in range(len(team_games) - 1):
        gap = (team_games[i + 1].scheduled_date.date() - 
               team_games[i].scheduled_date.date()).days
        deviation = abs(gap - config.target_gap_days)
        
        if deviation > worst_deviation:
            worst_deviation = deviation
            worst_gap_idx = i
    
    if worst_gap_idx is None:
        return False
    
    # Try to improve this gap by swapping games
    game1 = team_games[worst_gap_idx]
    game2 = team_games[worst_gap_idx + 1]
    
    return _try_improve_gap_with_swap(schedule, team_name, game1, game2, config)


def _try_improve_gap_with_swap(schedule: Schedule, team_name: str, game1: ScheduledGame,
                              game2: ScheduledGame, config: SchedulerConfig) -> bool:
    """
    Try to improve a gap by swapping games.
    
    Returns:
        bool: True if improvement was made
    """
    # Find potential swap candidates
    candidates = _find_swap_candidates(schedule, team_name, game1, game2, config)
    
    if not candidates:
        return False
    
    # Find the best swap
    best_candidate = None
    best_improvement = 0
    
    for candidate in candidates:
        improvement = _calculate_gap_improvement(
            schedule, team_name, game1, game2, candidate, config
        )
        
        if improvement > best_improvement:
            best_improvement = improvement
            best_candidate = candidate
    
    if best_candidate and best_improvement > 0:
        # Execute the swap
        _execute_swap(schedule, best_candidate['game'], best_candidate['target_game'])
        return True
    
    return False


def _find_swap_candidates(schedule: Schedule, team_name: str, game1: ScheduledGame,
                         game2: ScheduledGame, config: SchedulerConfig) -> List[Dict]:
    """
    Find potential swap candidates to improve gaps.
    
    Returns:
        List of candidate swap configurations
    """
    candidates = []
    
    # Look for games that could be swapped with game1 or game2
    for game in schedule.games:
        # Skip if game involves the target team
        if team_name in game.matchup.teams:
            continue
        
        # Skip if game is one of the games we're trying to improve
        if game.game_id in [game1.game_id, game2.game_id]:
            continue
        
        # Check if swapping with game1 would help
        if _is_valid_swap_candidate(schedule, game1, game, config):
            candidates.append({
                'game': game1,
                'target_game': game,
                'type': 'swap1'
            })
        
        # Check if swapping with game2 would help
        if _is_valid_swap_candidate(schedule, game2, game, config):
            candidates.append({
                'game': game2,
                'target_game': game,
                'type': 'swap2'
            })
    
    return candidates


def _is_valid_swap_candidate(schedule: Schedule, game1: ScheduledGame, game2: ScheduledGame,
                           config: SchedulerConfig) -> bool:
    """Check if two games can be swapped without violating constraints."""
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


def _calculate_gap_improvement(schedule: Schedule, team_name: str, game1: ScheduledGame,
                             game2: ScheduledGame, candidate: Dict, config: SchedulerConfig) -> float:
    """
    Calculate improvement from a potential swap.
    
    Returns:
        float: Improvement score (positive = better)
    """
    # Get current gaps for the team
    current_gaps = _get_team_gaps(schedule, team_name)
    
    # Simulate the swap
    temp_schedule = _simulate_swap(schedule, candidate['game'], candidate['target_game'])
    new_gaps = _get_team_gaps(temp_schedule, team_name)
    
    # Calculate improvement
    improvement = 0.0
    
    # Penalty for gaps that exceed max_gap_days
    for gap in new_gaps:
        if gap > config.max_gap_days:
            improvement -= (gap - config.max_gap_days) * 5
    
    # Bonus for gaps closer to target
    for old_gap, new_gap in zip(current_gaps, new_gaps):
        old_deviation = abs(old_gap - config.target_gap_days)
        new_deviation = abs(new_gap - config.target_gap_days)
        
        if new_deviation < old_deviation:
            improvement += (old_deviation - new_deviation)
    
    return improvement


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
