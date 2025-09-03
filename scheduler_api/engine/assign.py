from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
from collections import defaultdict
import random
from .models import Slot, Matchup, TeamState
from .costs import calculate_slot_cost
from .utils import days_between

def assign_slots_to_matchups(
    slots: List[Slot], 
    matchups: List, 
    teams: List[Dict], 
    params: Dict[str, Any]
) -> List[Dict]:
    """Greedy slot assignment algorithm"""
    
    # Initialize team states
    team_states = {}
    for team in teams:
        team_states[team['id']] = TeamState(team_id=team['id'])
    
    # Sort slots by start time
    available_slots = sorted(slots, key=lambda s: s.event_start)
    
    print(f"Starting assignment: {len(matchups)} matchups, {len(available_slots)} slots")
    print(f"First slot: {available_slots[0].event_start if available_slots else 'None'}")
    print(f"Last slot: {available_slots[-1].event_start if available_slots else 'None'}")
    
    assigned_games = []
    no_eligible_reasons = defaultdict(int)
    
    for matchup in matchups:
        # Handle both dictionary and Matchup objects
        if isinstance(matchup, dict):
            home_team_id = matchup['home_team_id']
            away_team_id = matchup['away_team_id']
            division_id = matchup['division_id']
        else:
            home_team_id = matchup.home_team_id
            away_team_id = matchup.away_team_id
            division_id = matchup.division_id
        
        best_slot = None
        best_cost = float('inf')
        
        # Find best available slot
        for slot in available_slots:
            if slot.assigned:
                continue
                
            # Check eligibility constraints
            home_team_state = team_states[home_team_id]
            away_team_state = team_states[away_team_id]
            
            # Min rest days constraint
            min_rest_days = params.get('minRestDays', 3)
            for team_state in [home_team_state, away_team_state]:
                if team_state.last_game_date:
                    rest_days = days_between(slot.event_start, team_state.last_game_date)
                    if rest_days < min_rest_days:
                        no_eligible_reasons[f"rest_days_{rest_days}"] += 1
                        continue
            
            # No back-to-back constraint
            if params.get('noBackToBack', True):
                for team_state in [home_team_state, away_team_state]:
                    if team_state.last_game_date:
                        days_between_games = days_between(slot.event_start, team_state.last_game_date)
                        if days_between_games <= 1:
                            no_eligible_reasons["back_to_back"] += 1
                            continue
            
            # Calculate cost for this slot
            cost = calculate_slot_cost(slot, home_team_state, away_team_state, params)
            
            if cost < best_cost:
                best_cost = cost
                best_slot = slot
        
        if best_slot:
            # Assign the slot
            best_slot.assigned = True
            home_team_state = team_states[home_team_id]
            away_team_state = team_states[away_team_id]
            
            # Update team states
            home_team_state.last_game_date = best_slot.event_start
            home_team_state.games_played += 1
            home_team_state.home_games += 1
            home_team_state.weekday_counts[best_slot.weekday] += 1
            
            away_team_state.last_game_date = best_slot.event_start
            away_team_state.games_played += 1
            away_team_state.away_games += 1
            away_team_state.weekday_counts[best_slot.weekday] += 1
            
            # Update E/M/L counts
            if best_slot.eml_class == 'Early':
                home_team_state.early_games += 1
                away_team_state.early_games += 1
            elif best_slot.eml_class == 'Mid':
                home_team_state.mid_games += 1
                away_team_state.mid_games += 1
            elif best_slot.eml_class == 'Late':
                home_team_state.late_games += 1
                away_team_state.late_games += 1
            
            # Create game record
            home_team = next(t for t in teams if t['id'] == home_team_id)
            away_team = next(t for t in teams if t['id'] == away_team_id)
            
            game_record = {
                'home_team': home_team,
                'away_team': away_team,
                'slot': best_slot,
                'division_id': division_id,
                'cost': best_cost
            }
            
            assigned_games.append(game_record)
            
        else:
            # No eligible slot found
            no_eligible_reasons["no_slots_available"] += 1
            print(f"No eligible slot found for matchup {home_team_id} vs {away_team_id}")
    
    # Log assignment results
    print(f"Assigned {len(assigned_games)} out of {len(matchups)} matchups")
    print("Top 5 'no-eligible' reasons:")
    for reason, count in sorted(no_eligible_reasons.items(), key=lambda x: x[1], reverse=True)[:5]:
        print(f"  {reason}: {count}")
    
    return assigned_games
