from typing import Dict, Any
from datetime import datetime, timedelta
from .models import Slot, TeamState
from .utils import days_between

def calculate_slot_cost(
    slot: Slot, 
    home_team_state: TeamState, 
    away_team_state: TeamState, 
    params: Dict[str, Any]
) -> float:
    """Calculate cost for assigning a slot to a matchup"""
    cost = 0.0
    
    # Gap bias: minimize abs(gap - idealGapDays)
    ideal_gap = params.get('idealGapDays', 7)
    weights = params.get('weights', {})
    
    for team_state in [home_team_state, away_team_state]:
        if team_state.last_game_date:
            gap = days_between(slot.event_start, team_state.last_game_date)
            gap_penalty = abs(gap - ideal_gap) * weights.get('gapBias', 1.0)
            cost += gap_penalty
    
    # Idle urgency: exponential penalty as gaps near maxGapDays
    max_gap = params.get('maxGapDays', 12)
    for team_state in [home_team_state, away_team_state]:
        if team_state.last_game_date:
            gap = days_between(slot.event_start, team_state.last_game_date)
            if gap >= max_gap:
                urgency_penalty = (gap - max_gap + 1) ** 2 * weights.get('idleUrgency', 8.0)
                cost += urgency_penalty
    
    # E/M/L balance: penalize giving the same E/M/L to teams who already have more of it
    eml_balance_weight = weights.get('emlBalance', 5.0)
    for team_state in [home_team_state, away_team_state]:
        if slot.eml_class == 'Early':
            cost += team_state.early_games * eml_balance_weight
        elif slot.eml_class == 'Mid':
            cost += team_state.mid_games * eml_balance_weight
        elif slot.eml_class == 'Late':
            cost += team_state.late_games * eml_balance_weight
    
    # Week rotation: penalize reusing first slot of the week
    week_rotation_weight = weights.get('weekRotation', 4.0)
    # This is a simplified version - you could track which teams have played in which week slots
    if slot.week_index <= 2:  # Early weeks get slight penalty
        cost += week_rotation_weight
    
    # Weekday balance (if enabled)
    if params.get('weekdayBalance', False):
        weekday_weight = weights.get('weekdayBalance', 0.5)
        for team_state in [home_team_state, away_team_state]:
            current_weekday_count = team_state.weekday_counts.get(slot.weekday, 0)
            cost += current_weekday_count * weekday_weight
    
    # Home/Away balance (if enabled)
    if params.get('homeAwayBalance', False):
        home_away_weight = weights.get('homeAway', 0.5)
        home_imbalance = abs(home_team_state.home_games - home_team_state.away_games)
        away_imbalance = abs(away_team_state.home_games - away_team_state.away_games)
        cost += (home_imbalance + away_imbalance) * home_away_weight
    
    return cost
