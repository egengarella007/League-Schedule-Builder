import pandas as pd
import io
from typing import Dict, Any, List
from collections import defaultdict
from datetime import datetime

def calculate_kpis(schedule_df: pd.DataFrame, teams_data: List[Dict], params: Dict[str, Any]) -> Dict[str, Any]:
    """Calculate KPIs from the generated schedule"""
    
    if schedule_df.empty:
        return {
            "max_gap": 0,
            "avg_gap": 0,
            "swaps": 0,
            "early_games": 0,
            "mid_games": 0,
            "late_games": 0
        }
    
    # Calculate gaps per team
    team_gaps = defaultdict(list)
    team_last_game = {}
    
    for _, game in schedule_df.iterrows():
        game_date = datetime.strptime(game['Date'], '%Y-%m-%d')
        
        # Track home team
        home_team = game['Home Team']
        if home_team in team_last_game:
            gap = (game_date - team_last_game[home_team]).days
            team_gaps[home_team].append(gap)
        team_last_game[home_team] = game_date
        
        # Track away team
        away_team = game['Away Team']
        if away_team in team_last_game:
            gap = (game_date - team_last_game[away_team]).days
            team_gaps[away_team].append(gap)
        team_last_game[away_team] = game_date
    
    # Calculate gap statistics
    all_gaps = []
    for gaps in team_gaps.values():
        all_gaps.extend(gaps)
    
    max_gap = max(all_gaps) if all_gaps else 0
    avg_gap = sum(all_gaps) / len(all_gaps) if all_gaps else 0
    
    # Count E/M/L games
    eml_counts = schedule_df['E/M/L'].value_counts()
    early_games = eml_counts.get('Early', 0)
    mid_games = eml_counts.get('Mid', 0)
    late_games = eml_counts.get('Late', 0)
    
    # Count weekday distribution
    weekday_counts = schedule_df['Weekday'].value_counts()
    
    return {
        "max_gap": max_gap,
        "avg_gap": round(avg_gap, 1),
        "swaps": 0,  # Placeholder for future swap optimization
        "early_games": int(early_games),
        "mid_games": int(mid_games),
        "late_games": int(late_games),
        "weekday_distribution": weekday_counts.to_dict() if not weekday_counts.empty else {}
    }

def export_to_xlsx(schedule_df: pd.DataFrame, kpis: Dict[str, Any], params: Dict[str, Any]) -> bytes:
    """Export schedule and KPIs to XLSX format"""
    
    out = io.BytesIO()
    
    with pd.ExcelWriter(out, engine="xlsxwriter") as writer:
        # Sheet 1: Final Schedule
        if not schedule_df.empty:
            schedule_df.to_excel(writer, index=False, sheet_name="Final Schedule")
        else:
            # Create empty schedule sheet
            empty_df = pd.DataFrame(columns=['Date', 'Start', 'End', 'Rink', 'Division', 'Home Team', 'Away Team', 'E/M/L', 'Weekday', 'Week', 'Note'])
            empty_df.to_excel(writer, index=False, sheet_name="Final Schedule")
        
        # Sheet 2: KPIs
        kpis_data = []
        for key, value in kpis.items():
            if isinstance(value, dict):
                for subkey, subvalue in value.items():
                    kpis_data.append({'Metric': f"{key}.{subkey}", 'Value': subvalue})
            else:
                kpis_data.append({'Metric': key, 'Value': value})
        
        kpis_df = pd.DataFrame(kpis_data)
        kpis_df.to_excel(writer, index=False, sheet_name="KPIs")
        
        # Sheet 3: Summary
        summary_data = {
            'Metric': [
                'Total Games', 
                'Total Teams', 
                'Total Divisions',
                'Games per Team',
                'Max Gap (days)',
                'Avg Gap (days)',
                'Early Games',
                'Mid Games', 
                'Late Games'
            ],
            'Value': [
                len(schedule_df),
                len(set(schedule_df['Home Team'].tolist() + schedule_df['Away Team'].tolist())) if not schedule_df.empty else 0,
                schedule_df['Division'].nunique() if not schedule_df.empty else 0,
                params.get('gamesPerTeam', 0),
                kpis.get('max_gap', 0),
                kpis.get('avg_gap', 0),
                kpis.get('early_games', 0),
                kpis.get('mid_games', 0),
                kpis.get('late_games', 0)
            ]
        }
        summary_df = pd.DataFrame(summary_data)
        summary_df.to_excel(writer, index=False, sheet_name="Summary")
        
        # Sheet 4: Parameters
        params_data = []
        for key, value in params.items():
            if isinstance(value, dict):
                for subkey, subvalue in value.items():
                    params_data.append({'Parameter': f"{key}.{subkey}", 'Value': subvalue})
            else:
                params_data.append({'Parameter': key, 'Value': value})
        
        params_df = pd.DataFrame(params_data)
        params_df.to_excel(writer, index=False, sheet_name="Parameters")
    
    return out.getvalue()
