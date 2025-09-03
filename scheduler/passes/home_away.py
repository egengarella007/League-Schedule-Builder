"""
Home/away balance pass to ensure teams have balanced home and away games.
"""

from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta
from ..models import Schedule, ScheduledGame, SwapLog
from ..config import SchedulerConfig


def balance_home_away(schedule: Schedule, config: SchedulerConfig) -> Schedule:
    """
    Balance home and away games for teams.
    
    Args:
        schedule: Current schedule
        config: Scheduler configuration
    
    Returns:
        Schedule: Updated schedule with balanced home/away games
    """
    if config.home_away_band == 0:
        print("Home/away balancing disabled")
        return schedule
    
    print("Running home/away balance pass...")
    
    # Calculate current home/away distribution
    ha_stats = _calculate_home_away_statistics(schedule)
    print(f"Current home/away distribution: {ha_stats}")
    
    # Find teams with poor home/away balance
    teams_to_improve = _find_teams_with_poor_balance(schedule, config)
    
    if not teams_to_improve:
        print("No teams need home/away balancing")
        return schedule
    
    print(f"Found {len(teams_to_improve)} teams needing home/away balancing")
    
    # Try to improve balance for each team
    improvements_made = 0
    max_iterations = 5  # Prevent infinite loops
    
    for iteration in range(max_iterations):
        iteration_improvements = 0
        
        for team_name in teams_to_improve:
            if _improve_team_balance(schedule, team_name, config):
                iteration_improvements += 1
        
        if iteration_improvements == 0:
            break
        
        improvements_made += iteration_improvements
        print(f"Iteration {iteration + 1}: Made {iteration_improvements} improvements")
    
    print(f"Total home/away improvements made: {improvements_made}")
    
    return schedule


def _calculate_home_away_statistics(schedule: Schedule) -> Dict[str, Dict]:
    """Calculate home/away distribution statistics."""
    stats = {}
    
    for team_name, team in schedule.teams.items():
        stats[team_name] = {
            'home': team.home_count,
            'away': team.away_count,
            'balance': team.get_home_away_balance()
        }
    
    return stats


def _find_teams_with_poor_balance(schedule: Schedule, config: SchedulerConfig) -> List[str]:
    """Find teams with poor home/away balance."""
    teams_to_improve = []
    
    for team_name, team in schedule.teams.items():
        balance = abs(team.get_home_away_balance())
        
        if balance > config.home_away_band:
            teams_to_improve.append(team_name)
    
    return teams_to_improve


def _improve_team_balance(schedule: Schedule, team_name: str, config: SchedulerConfig) -> bool:
    """
    Try to improve home/away balance for a specific team.
    
    Returns:
        bool: True if improvement was made
    """
    team = schedule.teams[team_name]
    balance = team.get_home_away_balance()
    
    if abs(balance) <= config.home_away_band:
        return False
    
    # Determine if team needs more home or away games
    needs_home = balance < 0  # Negative balance means more away games
    needs_away = balance > 0  # Positive balance means more home games
    
    team_games = schedule.get_team_schedule(team_name)
    
    if needs_home:
        # Look for away games that could be swapped to home
        return _try_swap_to_home(schedule, team_name, team_games, config)
    elif needs_away:
        # Look for home games that could be swapped to away
        return _try_swap_to_away(schedule, team_name, team_games, config)
    
    return False


def _try_swap_to_home(schedule: Schedule, team_name: str, team_games: List[ScheduledGame],
                     config: SchedulerConfig) -> bool:
    """
    Try to swap an away game to home for better balance.
    
    Returns:
        bool: True if swap was made
    """
    # Find away games for this team
    away_games = [game for game in team_games 
                  if game.matchup.away_team == team_name]
    
    for away_game in away_games:
        # Look for compatible home games to swap with
        compatible_games = _find_compatible_home_games(schedule, away_game, config)
        
        for compatible_game in compatible_games:
            if _can_swap_home_away(schedule, away_game, compatible_game, config):
                # Execute the swap
                _execute_home_away_swap(schedule, away_game, compatible_game)
                return True
    
    return False


def _try_swap_to_away(schedule: Schedule, team_name: str, team_games: List[ScheduledGame],
                     config: SchedulerConfig) -> bool:
    """
    Try to swap a home game to away for better balance.
    
    Returns:
        bool: True if swap was made
    """
    # Find home games for this team
    home_games = [game for game in team_games 
                  if game.matchup.home_team == team_name]
    
    for home_game in home_games:
        # Look for compatible away games to swap with
        compatible_games = _find_compatible_away_games(schedule, home_game, config)
        
        for compatible_game in compatible_games:
            if _can_swap_home_away(schedule, home_game, compatible_game, config):
                # Execute the swap
                _execute_home_away_swap(schedule, home_game, compatible_game)
                return True
    
    return False


def _find_compatible_home_games(schedule: Schedule, away_game: ScheduledGame,
                               config: SchedulerConfig) -> List[ScheduledGame]:
    """Find home games that could be swapped with an away game."""
    compatible = []
    
    for game in schedule.games:
        # Skip if this is the same game
        if game.game_id == away_game.game_id:
            continue
        
        # Skip if this is also an away game
        if game.matchup.away_team == away_game.matchup.away_team:
            continue
        
        # Check if games have compatible teams
        if _are_teams_compatible(away_game, game):
            compatible.append(game)
    
    return compatible


def _find_compatible_away_games(schedule: Schedule, home_game: ScheduledGame,
                               config: SchedulerConfig) -> List[ScheduledGame]:
    """Find away games that could be swapped with a home game."""
    compatible = []
    
    for game in schedule.games:
        # Skip if this is the same game
        if game.game_id == home_game.game_id:
            continue
        
        # Skip if this is also a home game
        if game.matchup.home_team == home_game.matchup.home_team:
            continue
        
        # Check if games have compatible teams
        if _are_teams_compatible(home_game, game):
            compatible.append(game)
    
    return compatible


def _are_teams_compatible(game1: ScheduledGame, game2: ScheduledGame) -> bool:
    """Check if two games have compatible teams for swapping."""
    teams1 = set(game1.matchup.teams)
    teams2 = set(game2.matchup.teams)
    
    # Teams should be disjoint
    return teams1.isdisjoint(teams2)


def _can_swap_home_away(schedule: Schedule, game1: ScheduledGame, game2: ScheduledGame,
                       config: SchedulerConfig) -> bool:
    """Check if two games can be swapped for home/away balancing."""
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
    temp_schedule = _simulate_home_away_swap(schedule, game1, game2)
    
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


def _simulate_home_away_swap(schedule: Schedule, game1: ScheduledGame, game2: ScheduledGame) -> Schedule:
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


def _execute_home_away_swap(schedule: Schedule, game1: ScheduledGame, game2: ScheduledGame):
    """Execute a home/away swap between two games."""
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
