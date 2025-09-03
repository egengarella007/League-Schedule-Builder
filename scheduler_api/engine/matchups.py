from typing import List, Dict, Any
from collections import defaultdict
import pandas as pd
from .models import Matchup

def generate_matchups(divisions: pd.DataFrame, teams: pd.DataFrame, params: Dict[str, Any]) -> List[Matchup]:
    """Generate matchups based on parameters"""
    matchups = []
    teams_list = teams.to_dict('records')
    
    # Group teams by division
    teams_by_division = defaultdict(list)
    for team in teams_list:
        teams_by_division[team['division_id']].append(team)
    
    print(f"Generating matchups for {len(teams)} teams across {len(divisions)} divisions")
    
    # Create intra-division round-robin matchups
    for division_id, division_teams in teams_by_division.items():
        if len(division_teams) < 2:
            continue
            
        print(f"Division {division_id}: {len(division_teams)} teams")
        
        # Create round-robin matchups (each team plays every other team)
        for i in range(len(division_teams)):
            for j in range(i + 1, len(division_teams)):  # Start from i+1 to avoid self-matchups
                # Add both home and away games
                matchups.append(Matchup(
                    home_team_id=division_teams[i]['id'],
                    away_team_id=division_teams[j]['id'],
                    division_id=division_id
                ))
                matchups.append(Matchup(
                    home_team_id=division_teams[j]['id'],
                    away_team_id=division_teams[i]['id'],
                    division_id=division_id
                ))
    
    # Add cross-division matchups if enabled
    if params.get('subDivisionCrossover', False):
        print("Adding cross-division matchups")
        division_ids = list(teams_by_division.keys())
        for i, div1_id in enumerate(division_ids):
            for div2_id in division_ids[i+1:]:
                for team1 in teams_by_division[div1_id]:
                    for team2 in teams_by_division[div2_id]:
                        matchups.append(Matchup(
                            home_team_id=team1['id'],
                            away_team_id=team2['id'],
                            division_id=div1_id
                        ))
                        matchups.append(Matchup(
                            home_team_id=team2['id'],
                            away_team_id=team1['id'],
                            division_id=div2_id
                        ))
    
    print(f"Generated {len(matchups)} total matchups")
    return matchups

def fit_games_per_team(matchups: List[Matchup], teams: pd.DataFrame, games_per_team: int) -> List[Matchup]:
    """Fit matchups to target games per team"""
    from collections import defaultdict
    
    print(f"Fitting {len(matchups)} matchups to {games_per_team} games per team")
    
    # Second pass: filter matchups to meet target
    filtered_matchups = []
    temp_games_count = defaultdict(int)  # Track games as we add them
    
    for matchup in matchups:
        home_games = temp_games_count[matchup.home_team_id]
        away_games = temp_games_count[matchup.away_team_id]
        
        # Check if adding this matchup would exceed the limit
        if home_games < games_per_team and away_games < games_per_team:
            filtered_matchups.append(matchup)
            temp_games_count[matchup.home_team_id] += 1
            temp_games_count[matchup.away_team_id] += 1
    
    print(f"Filtered to {len(filtered_matchups)} matchups")
    
    # Log final team game counts
    for team_id, count in temp_games_count.items():
        if count > 0:
            team_name = teams[teams['id'] == team_id]['name'].iloc[0] if len(teams) > 0 else f"Team {team_id}"
            print(f"  {team_name}: {count} games")
    
    return filtered_matchups
