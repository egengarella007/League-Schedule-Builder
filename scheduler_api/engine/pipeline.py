from typing import List, Dict, Any
import pandas as pd
from datetime import datetime
import random
from collections import defaultdict

from .models import Slot
from .utils import parse_datetime, classify_slot_time, get_weekday, get_week_index, handle_overnight_slots
from .matchups import generate_matchups, fit_games_per_team
from .assign import assign_slots_to_matchups

def to_slots_df(slots_data: List[Dict], params: Dict[str, Any]) -> List[Slot]:
    """Convert raw slots data to Slot objects with proper datetime parsing"""
    timezone = params.get('timezone', 'America/Chicago')
    slots = []
    
    print(f"Parsing {len(slots_data)} slots with timezone {timezone}")
    
    for slot_data in slots_data:
        try:
            # Parse datetime
            event_start = parse_datetime(slot_data['type'], slot_data['event_start'], timezone)
            event_end = parse_datetime(slot_data['type'], slot_data['event_end'], timezone)
            
            # Handle overnight events
            if event_end < event_start:
                event_end = event_end.replace(day=event_end.day + 1)
            
            # Calculate additional fields
            weekday = get_weekday(event_start)
            
            # Use first slot as season start for week calculation
            if not slots:
                season_start = event_start
            else:
                season_start = slots[0].event_start
            
            week_index = get_week_index(event_start, season_start)
            eml_class = classify_slot_time(event_start, params)
            
            slot = Slot(
                id=slot_data['id'],
                event_start=event_start,
                event_end=event_end,
                resource=slot_data.get('resource', 'Unknown'),
                weekday=weekday,
                week_index=week_index,
                eml_class=eml_class
            )
            slots.append(slot)
            
        except Exception as e:
            print(f"Error parsing slot {slot_data}: {e}")
            continue
    
    # Sort by start time
    slots.sort(key=lambda s: s.event_start)
    
    print(f"Successfully parsed {len(slots)} slots")
    if slots:
        print(f"First slot: {slots[0].event_start}")
        print(f"Last slot: {slots[-1].event_start}")
    
    return slots

def create_week1_seed_matchups(teams_data: List[Dict], divisions_data: List[Dict]) -> List[Dict]:
    """Create Week-1 seed matchups with mirrored pairs per division (1vN, 2vN-1, ...)"""
    matchups = []
    
    # Group teams by division
    teams_by_division = defaultdict(list)
    for team in teams_data:
        teams_by_division[team['division_id']].append(team)
    
    print("Creating Week-1 seed matchups with mirrored pairs")
    
    for division_id, division_teams in teams_by_division.items():
        if len(division_teams) < 2:
            continue
            
        print(f"Division {division_id}: {len(division_teams)} teams")
        
        # Sort teams by ID for consistent seeding
        division_teams.sort(key=lambda t: t['id'])
        
        # Create mirrored pairs (1vN, 2vN-1, ...)
        n = len(division_teams)
        for i in range(n // 2):
            home_team = division_teams[i]
            away_team = division_teams[n - 1 - i]
            
            matchups.append({
                'home_team_id': home_team['id'],
                'away_team_id': away_team['id'],
                'division_id': division_id,
                'is_seed': True
            })
    
    print(f"Created {len(matchups)} Week-1 seed matchups")
    return matchups

def run_pipeline(
    slots_data: List[Dict],
    divisions_data: List[Dict], 
    teams_data: List[Dict],
    params: Dict[str, Any]
) -> pd.DataFrame:
    """Main scheduling pipeline with proper greedy algorithm"""
    
    print("=== Starting Scheduling Pipeline ===")
    print(f"Parameters: {params}")
    
    # Set random seed
    random.seed(params.get('seed', 42))
    
    # Convert to DataFrames
    divisions_df = pd.DataFrame(divisions_data)
    teams_df = pd.DataFrame(teams_data)
    
    # Parse slots
    slots = to_slots_df(slots_data, params)
    
    if not slots:
        print("ERROR: No valid slots found")
        return pd.DataFrame()
    
    # Generate regular matchups
    matchups = generate_matchups(divisions_df, teams_df, params)
    
    if not matchups:
        print("ERROR: No matchups generated")
        return pd.DataFrame()
    
    # Fit to games per team
    games_per_team = params.get('gamesPerTeam', 12)
    matchups = fit_games_per_team(matchups, teams_df, games_per_team)
    
    if not matchups:
        print("ERROR: No matchups after fitting to games per team")
        return pd.DataFrame()
    
    # Create Week-1 seed matchups (separate from regular matchups)
    seed_matchups = create_week1_seed_matchups(teams_data, divisions_data)
    
    # Combine seed and regular matchups, but ensure no duplicates
    all_matchups = []
    
    # Add seed matchups first
    for seed_matchup in seed_matchups:
        all_matchups.append(seed_matchup)
    
    # Add regular matchups, avoiding duplicates with seed matchups
    for matchup in matchups:
        # Check if this matchup already exists in seed matchups
        is_duplicate = False
        for seed_matchup in seed_matchups:
            if (seed_matchup['home_team_id'] == matchup.home_team_id and 
                seed_matchup['away_team_id'] == matchup.away_team_id):
                is_duplicate = True
                break
        
        if not is_duplicate:
            all_matchups.append(matchup)
    
    print(f"Total matchups: {len(all_matchups)} ({len(seed_matchups)} seed + {len(all_matchups) - len(seed_matchups)} regular)")
    
    # Greedy slot assignment
    assigned_games = assign_slots_to_matchups(slots, all_matchups, teams_data, params)
    
    if not assigned_games:
        print("ERROR: No games assigned to slots")
        return pd.DataFrame()
    
    # Create final schedule DataFrame
    schedule_data = []
    for game in assigned_games:
        slot = game['slot']
        home_team = game['home_team']
        away_team = game['away_team']
        
        # Get division name
        division_name = divisions_df[divisions_df['id'] == game['division_id']]['name'].iloc[0] if len(divisions_df) > 0 else 'Unknown'
        
        schedule_data.append({
            'Date': slot.event_start.strftime('%Y-%m-%d'),
            'Start': slot.event_start.strftime('%I:%M %p'),
            'End': slot.event_end.strftime('%I:%M %p'),
            'Rink': slot.resource,
            'Division': division_name,
            'Home Team': home_team['name'],
            'Away Team': away_team['name'],
            'E/M/L': slot.eml_class,
            'Weekday': slot.weekday,
            'Week': slot.week_index,
            'Note': ''
        })
    
    # Sort by date and time
    schedule_df = pd.DataFrame(schedule_data)
    if not schedule_df.empty:
        schedule_df = schedule_df.sort_values(['Date', 'Start'])
    
    print(f"=== Pipeline Complete ===")
    print(f"Generated {len(schedule_df)} scheduled games")
    
    return schedule_df
