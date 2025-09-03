"""
Matchup generation for round-robin scheduling.
"""

import random
from typing import List, Dict, Optional
from .models import Matchup
from .config import SchedulerConfig


def generate_round_robin(teams: List[str], double_round: bool = True) -> List[Matchup]:
    """
    Generate round-robin matchups using the circle method.
    
    Args:
        teams: List of team names
        double_round: If True, generate double round-robin (each team plays each other twice)
    
    Returns:
        List[Matchup]: List of matchups
    """
    if len(teams) < 2:
        return []
    
    # Ensure even number of teams (add bye if odd)
    if len(teams) % 2 == 1:
        teams = teams + ["BYE"]
    
    n_teams = len(teams)
    n_rounds = n_teams - 1
    
    matchups = []
    week = 1
    
    # Generate single round-robin
    for round_num in range(n_rounds):
        for i in range(n_teams // 2):
            team1_idx = i
            team2_idx = n_teams - 1 - i
            
            # Skip bye games
            if teams[team1_idx] != "BYE" and teams[team2_idx] != "BYE":
                matchup = Matchup(
                    home_team=teams[team1_idx],
                    away_team=teams[team2_idx],
                    division="Unknown",  # Will be set later
                    week_target=week,
                    order_in_week=i + 1
                )
                matchups.append(matchup)
        
        # Rotate teams (circle method)
        teams = [teams[0]] + [teams[-1]] + teams[1:-1]
        week += 1
    
    # Generate double round-robin if requested
    if double_round:
        reverse_matchups = []
        for matchup in matchups:
            reverse_matchup = Matchup(
                home_team=matchup.away_team,
                away_team=matchup.home_team,
                division=matchup.division,
                week_target=matchup.week_target + n_rounds,
                order_in_week=matchup.order_in_week
            )
            reverse_matchups.append(reverse_matchup)
        matchups.extend(reverse_matchups)
    
    return matchups


def assign_divisions_to_matchups(matchups: List[Matchup], config: SchedulerConfig) -> List[Matchup]:
    """
    Assign division information to matchups based on team divisions.
    
    Args:
        matchups: List of matchups
        config: Scheduler configuration
    
    Returns:
        List[Matchup]: Matchups with division information
    """
    team_divisions = {}
    
    # Build team to division mapping
    for division in config.divisions:
        for sub_div in division.sub_divisions:
            for team in sub_div.teams:
                team_divisions[team] = division.name
    
    # Assign divisions to matchups
    for matchup in matchups:
        home_division = team_divisions.get(matchup.home_team, "Unknown")
        away_division = team_divisions.get(matchup.away_team, "Unknown")
        
        # Use home team's division, or create combined division name
        if home_division == away_division:
            matchup.division = home_division
        else:
            matchup.division = f"{home_division}-{away_division}"
    
    return matchups


def generate_matchups_by_division(config: SchedulerConfig, double_round: bool = True) -> List[Matchup]:
    """
    Generate matchups within each division separately.
    
    Args:
        config: Scheduler configuration
        double_round: If True, generate double round-robin
    
    Returns:
        List[Matchup]: List of all matchups
    """
    all_matchups = []
    week_offset = 0
    
    for division in config.divisions:
        for sub_div in division.sub_divisions:
            # Generate matchups for this sub-division
            sub_matchups = generate_round_robin(sub_div.teams, double_round)
            
            # Assign division and adjust week numbers
            for matchup in sub_matchups:
                matchup.division = division.name
                matchup.week_target += week_offset
            
            all_matchups.extend(sub_matchups)
            
            # Calculate weeks needed for this sub-division
            n_teams = len(sub_div.teams)
            if n_teams % 2 == 1:  # Add bye
                n_teams += 1
            weeks_needed = (n_teams - 1) * (2 if double_round else 1)
            week_offset += weeks_needed
    
    return all_matchups


def generate_cross_division_matchups(config: SchedulerConfig, games_per_pair: int = 1) -> List[Matchup]:
    """
    Generate cross-division matchups.
    
    Args:
        config: Scheduler configuration
        games_per_pair: Number of games per team pair
    
    Returns:
        List[Matchup]: List of cross-division matchups
    """
    cross_matchups = []
    week = 1
    
    # Get all teams by division
    division_teams = {}
    for division in config.divisions:
        teams = []
        for sub_div in division.sub_divisions:
            teams.extend(sub_div.teams)
        division_teams[division.name] = teams
    
    # Generate matchups between divisions
    divisions = list(division_teams.keys())
    for i, div1 in enumerate(divisions):
        for div2 in divisions[i+1:]:
            teams1 = division_teams[div1]
            teams2 = division_teams[div2]
            
            # Create all possible pairs
            for team1 in teams1:
                for team2 in teams2:
                    for game_num in range(games_per_pair):
                        # Alternate home/away for multiple games
                        if game_num % 2 == 0:
                            home_team, away_team = team1, team2
                        else:
                            home_team, away_team = team2, team1
                        
                        matchup = Matchup(
                            home_team=home_team,
                            away_team=away_team,
                            division=f"{div1}-{div2}",
                            week_target=week,
                            order_in_week=1
                        )
                        cross_matchups.append(matchup)
                        week += 1
    
    return cross_matchups


def build_matchups(config: SchedulerConfig, 
                  matchup_file: Optional[str] = None,
                  double_round: bool = True,
                  include_cross_division: bool = False,
                  cross_division_games: int = 1) -> List[Matchup]:
    """
    Build matchups from configuration or file.
    
    Args:
        config: Scheduler configuration
        matchup_file: Optional path to matchup Excel file
        double_round: If True, generate double round-robin
        include_cross_division: If True, include cross-division games
        cross_division_games: Number of cross-division games per team pair
    
    Returns:
        List[Matchup]: List of all matchups
    """
    if matchup_file:
        # Load from file
        from .ingest import load_matchups_from_excel
        matchups = load_matchups_from_excel(matchup_file, config)
        matchups = assign_divisions_to_matchups(matchups, config)
    else:
        # Generate from configuration
        matchups = generate_matchups_by_division(config, double_round)
        
        # Add cross-division games if requested
        if include_cross_division:
            cross_matchups = generate_cross_division_matchups(config, cross_division_games)
            matchups.extend(cross_matchups)
    
    # Sort by week and order
    matchups.sort(key=lambda x: (x.week_target, x.order_in_week))
    
    return matchups


def get_matchup_summary(matchups: List[Matchup]) -> Dict:
    """
    Get summary statistics for matchups.
    
    Args:
        matchups: List of matchups
    
    Returns:
        Dict: Summary statistics
    """
    if not matchups:
        return {}
    
    # Count by division
    division_counts = {}
    team_game_counts = {}
    
    for matchup in matchups:
        # Division counts
        division_counts[matchup.division] = division_counts.get(matchup.division, 0) + 1
        
        # Team game counts
        for team in [matchup.home_team, matchup.away_team]:
            team_game_counts[team] = team_game_counts.get(team, 0) + 1
    
    summary = {
        'total_matchups': len(matchups),
        'divisions': division_counts,
        'teams': len(team_game_counts),
        'weeks': max(m.week_target for m in matchups) if matchups else 0,
        'avg_games_per_team': sum(team_game_counts.values()) / len(team_game_counts) if team_game_counts else 0
    }
    
    return summary
