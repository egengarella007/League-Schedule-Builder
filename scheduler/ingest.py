"""
Data ingestion for the league scheduler.
"""

import pandas as pd
import pytz
from datetime import datetime
from typing import List, Dict, Optional
from .models import Slot, Team, Weekday, EMLCategory
from .config import SchedulerConfig
from .eml import classify_slot_times


def load_slots(excel_path: str, config: SchedulerConfig) -> List[Slot]:
    """
    Load available time slots from Excel file.
    
    Args:
        excel_path: Path to Excel file with slot data
        config: Scheduler configuration
    
    Returns:
        List[Slot]: List of available slots
    """
    # Read Excel file
    df = pd.read_excel(excel_path)
    
    # Validate required columns exist
    required_columns = [config.columns['start'], config.columns['end'], config.columns['resource']]
    missing_columns = [col for col in required_columns if col not in df.columns]
    
    if missing_columns:
        raise ValueError(f"Missing required columns: {missing_columns}. Found columns: {list(df.columns)}")
    
    # Convert to timezone-aware datetime
    tz = pytz.timezone(config.timezone)
    
    slots = []
    for _, row in df.iterrows():
        try:
            # Parse start and end times
            start_time = pd.to_datetime(row[config.columns['start']])
            end_time = pd.to_datetime(row[config.columns['end']])
            
            # Make timezone-aware
            if start_time.tz is None:
                start_time = tz.localize(start_time)
            if end_time.tz is None:
                end_time = tz.localize(end_time)
            
            # Classify E/M/L and weekday
            start_eml, end_eml, weekday = classify_slot_times(
                start_time, 
                end_time,
                config.eml_cutoffs.early_end,
                config.eml_cutoffs.mid_end
            )
            
            # Create slot
            slot = Slot(
                start_time=start_time,
                end_time=end_time,
                resource=row[config.columns['resource']],
                slot_type="Game Rental",  # Default type
                weekday=weekday,
                eml_category=end_eml  # Use end time for E/M/L classification
            )
            
            slots.append(slot)
            
        except Exception as e:
            print(f"Warning: Could not parse row {row.name}: {e}")
            continue
    
    # Sort by start time
    slots.sort(key=lambda x: x.start_time)
    
    return slots


def create_teams_from_config(config: SchedulerConfig) -> Dict[str, Team]:
    """
    Create Team objects from configuration.
    
    Args:
        config: Scheduler configuration
    
    Returns:
        Dict[str, Team]: Dictionary mapping team names to Team objects
    """
    teams = {}
    
    for division in config.divisions:
        for sub_div in division.sub_divisions:
            for team_name in sub_div.teams:
                team = Team(
                    name=team_name,
                    division=division.name,
                    sub_division=sub_div.name
                )
                teams[team_name] = team
    
    return teams


def load_matchups_from_excel(excel_path: str, config: SchedulerConfig) -> List['Matchup']:
    """
    Load matchups from Excel file (if provided).
    
    Args:
        excel_path: Path to Excel file with matchup data
        config: Scheduler configuration
    
    Returns:
        List[Matchup]: List of matchups
    """
    from .models import Matchup
    
    df = pd.read_excel(excel_path)
    
    matchups = []
    for _, row in df.iterrows():
        matchup = Matchup(
            home_team=row['Home Team'],
            away_team=row['Away Team'],
            division=row.get('Division', 'Unknown'),
            week_target=row.get('Week', 1),
            order_in_week=row.get('Order', 1)
        )
        matchups.append(matchup)
    
    return matchups


def validate_slots(slots: List[Slot]) -> Dict[str, List[str]]:
    """
    Validate slot data for common issues.
    
    Args:
        slots: List of slots to validate
    
    Returns:
        Dict[str, List[str]]: Validation results
    """
    issues = {
        'warnings': [],
        'errors': []
    }
    
    if not slots:
        issues['errors'].append("No slots found")
        return issues
    
    # Check for overlapping slots
    for i, slot1 in enumerate(slots):
        for j, slot2 in enumerate(slots[i+1:], i+1):
            if (slot1.resource == slot2.resource and 
                slot1.start_time < slot2.end_time and 
                slot2.start_time < slot1.end_time):
                issues['warnings'].append(
                    f"Overlapping slots: {slot1.slot_id} and {slot2.slot_id}"
                )
    
    # Check for very short slots
    short_slots = [s for s in slots if s.duration_hours < 1.0]
    if short_slots:
        issues['warnings'].append(
            f"Found {len(short_slots)} slots shorter than 1 hour"
        )
    
    # Check for very long slots
    long_slots = [s for s in slots if s.duration_hours > 4.0]
    if long_slots:
        issues['warnings'].append(
            f"Found {len(long_slots)} slots longer than 4 hours"
        )
    
    return issues


def get_slot_summary(slots: List[Slot]) -> Dict:
    """
    Get summary statistics for slots.
    
    Args:
        slots: List of slots
    
    Returns:
        Dict: Summary statistics
    """
    if not slots:
        return {}
    
    df = pd.DataFrame([
        {
            'date': slot.date,
            'weekday': slot.weekday.value,
            'eml': slot.eml_category.value,
            'resource': slot.resource,
            'duration': slot.duration_hours
        }
        for slot in slots
    ])
    
    summary = {
        'total_slots': len(slots),
        'date_range': {
            'start': df['date'].min(),
            'end': df['date'].max()
        },
        'weekday_distribution': df['weekday'].value_counts().to_dict(),
        'eml_distribution': df['eml'].value_counts().to_dict(),
        'resource_distribution': df['resource'].value_counts().to_dict(),
        'avg_duration': df['duration'].mean(),
        'total_hours': df['duration'].sum()
    }
    
    return summary
