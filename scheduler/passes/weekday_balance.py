"""
Weekday balance pass to distribute games evenly across weekdays.
"""

from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta
from ..models import Schedule, ScheduledGame, SwapLog, Weekday
from ..config import SchedulerConfig


def balance_weekdays(schedule: Schedule, config: SchedulerConfig) -> Schedule:
    """
    Balance games across weekdays by swapping games with same time slots.
    
    Args:
        schedule: Current schedule
        config: Scheduler configuration
    
    Returns:
        Schedule: Updated schedule with balanced weekdays
    """
    print("Running weekday balance pass...")
    
    # Calculate current weekday distribution
    weekday_stats = _calculate_weekday_statistics(schedule)
    print(f"Current weekday distribution: {weekday_stats}")
    
    # Find teams with poor weekday distribution
    teams_to_improve = _find_teams_with_poor_weekdays(schedule, config)
    
    if not teams_to_improve:
        print("No teams need weekday balancing")
        return schedule
    
    print(f"Found {len(teams_to_improve)} teams needing weekday balancing")
    
    # Try to improve weekday distribution for each team
    improvements_made = 0
    max_iterations = 5  # Prevent infinite loops
    
    for iteration in range(max_iterations):
        iteration_improvements = 0
        
        for team_name in teams_to_improve:
            if _improve_team_weekdays(schedule, team_name, config):
                iteration_improvements += 1
        
        if iteration_improvements == 0:
            break
        
        improvements_made += iteration_improvements
        print(f"Iteration {iteration + 1}: Made {iteration_improvements} improvements")
    
    print(f"Total weekday improvements made: {improvements_made}")
    
    return schedule


def _calculate_weekday_statistics(schedule: Schedule) -> Dict[str, int]:
    """Calculate weekday distribution statistics."""
    weekday_counts = {weekday.value: 0 for weekday in Weekday}
    
    for game in schedule.games:
        weekday = game.slot.weekday.value
        weekday_counts[weekday] += 1
    
    return weekday_counts


def _find_teams_with_poor_weekdays(schedule: Schedule, config: SchedulerConfig) -> List[str]:
    """Find teams with poor weekday distribution."""
    teams_to_improve = []
    
    for team_name in schedule.teams:
        team_weekdays = _get_team_weekdays(schedule, team_name)
        
        if not team_weekdays:
            continue
        
        # Count games per weekday
        weekday_counts = {}
        for weekday in team_weekdays:
            weekday_counts[weekday] = weekday_counts.get(weekday, 0) + 1
        
        # Check for heavy and light weekdays
        heavy_weekdays = [day for day, count in weekday_counts.items() 
                         if count >= config.weekday_heavy_threshold]
        light_weekdays = [day for day, count in weekday_counts.items() 
                         if count <= config.weekday_light_threshold]
        
        if heavy_weekdays and light_weekdays:
            teams_to_improve.append(team_name)
    
    return teams_to_improve


def _get_team_weekdays(schedule: Schedule, team_name: str) -> List[str]:
    """Get weekdays of games for a team."""
    team_games = schedule.get_team_schedule(team_name)
    return [game.slot.weekday.value for game in team_games]


def _improve_team_weekdays(schedule: Schedule, team_name: str, config: SchedulerConfig) -> bool:
    """
    Try to improve weekday distribution for a specific team.
    
    Returns:
        bool: True if improvement was made
    """
    team_games = schedule.get_team_schedule(team_name)
    
    if len(team_games) < 2:
        return False
    
    # Find heavy and light weekdays for this team
    weekday_counts = {}
    for game in team_games:
        weekday = game.slot.weekday.value
        weekday_counts[weekday] = weekday_counts.get(weekday, 0) + 1
    
    heavy_weekdays = [day for day, count in weekday_counts.items() 
                     if count >= config.weekday_heavy_threshold]
    light_weekdays = [day for day, count in weekday_counts.items() 
                     if count <= config.weekday_light_threshold]
    
    if not heavy_weekdays or not light_weekdays:
        return False
    
    # Try to swap games between heavy and light weekdays
    return _try_swap_weekday_games(schedule, team_name, heavy_weekdays, light_weekdays, config)


def _try_swap_weekday_games(schedule: Schedule, team_name: str, heavy_weekdays: List[str],
                           light_weekdays: List[str], config: SchedulerConfig) -> bool:
    """
    Try to swap games between heavy and light weekdays.
    
    Returns:
        bool: True if swap was made
    """
    team_games = schedule.get_team_schedule(team_name)
    
    # Find games on heavy weekdays
    heavy_games = [game for game in team_games 
                  if game.slot.weekday.value in heavy_weekdays]
    
    # Find games on light weekdays
    light_games = [game for game in team_games 
                  if game.slot.weekday.value in light_weekdays]
    
    # Try to find compatible swaps
    for heavy_game in heavy_games:
        for light_game in light_games:
            if _can_swap_weekday_games(schedule, heavy_game, light_game, config):
                # Execute the swap
                _execute_weekday_swap(schedule, heavy_game, light_game)
                return True
    
    return False


def _can_swap_weekday_games(schedule: Schedule, game1: ScheduledGame, game2: ScheduledGame,
                          config: SchedulerConfig) -> bool:
    """
    Check if two games can be swapped for weekday balancing.
    
    Only allows swaps if games have the same time slot.
    """
    # Check if games have the same time slot
    if (game1.slot.start_time.time() != game2.slot.start_time.time() or
        game1.slot.end_time.time() != game2.slot.end_time.time()):
        return False
    
    # Check if swap would violate rest day constraints
    teams1 = game1.matchup.teams
    teams2 = game2.matchup.teams
    
    for team in teams1 + teams2:
        team_obj = schedule.teams[team]
        
        # Calculate rest days for both possible positions
        rest1 = team_obj.get_rest_days(game1.scheduled_date)
        rest2 = team_obj.get_rest_days(game2.scheduled_date)
        
        if rest1 < config.rest_min_days or rest2 < config.rest_min_days:
            return False
    
    # Check if swap would create scheduling conflicts
    if _would_create_conflict(schedule, game1, game2):
        return False
    
    return True


def _would_create_conflict(schedule: Schedule, game1: ScheduledGame, game2: ScheduledGame) -> bool:
    """Check if swapping two games would create scheduling conflicts."""
    # Simulate the swap
    temp_schedule = _simulate_weekday_swap(schedule, game1, game2)
    
    # Check for conflicts in the simulated schedule
    games_by_date = {}
    for game in temp_schedule.games:
        date = game.scheduled_date.date()
        if date not in games_by_date:
            games_by_date[date] = []
        games_by_date[date].append(game)
    
    for date, games in games_by_date.items():
        teams_on_date = set()
        for game in games:
            for team in game.matchup.teams:
                if team in teams_on_date:
                    return True  # Conflict found
                teams_on_date.add(team)
    
    return False


def _simulate_weekday_swap(schedule: Schedule, game1: ScheduledGame, game2: ScheduledGame) -> Schedule:
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


def _execute_weekday_swap(schedule: Schedule, game1: ScheduledGame, game2: ScheduledGame):
    """Execute a weekday swap between two games."""
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
