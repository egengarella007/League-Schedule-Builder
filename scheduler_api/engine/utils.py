import pandas as pd
from datetime import datetime, timedelta
import pytz
from typing import List, Dict, Any

def parse_datetime(date_str: str, time_str: str, timezone: str) -> datetime:
    """Parse date and time strings into a timezone-aware datetime"""
    try:
        # Parse the date and time
        if '/' in date_str:
            # Format: MM/DD/YY
            date_obj = datetime.strptime(date_str, '%m/%d/%y')
        else:
            # Format: YYYY-MM-DD
            date_obj = datetime.strptime(date_str, '%Y-%m-%d')
        
        # Parse the time
        if 'PM' in time_str or 'AM' in time_str:
            time_obj = datetime.strptime(time_str, '%I:%M %p')
        else:
            time_obj = datetime.strptime(time_str, '%H:%M')
        
        # Combine date and time
        combined = datetime.combine(date_obj.date(), time_obj.time())
        
        # Apply timezone
        tz = pytz.timezone(timezone)
        return tz.localize(combined)
        
    except Exception as e:
        print(f"Error parsing datetime: {date_str} {time_str} - {e}")
        # Return a default datetime if parsing fails
        return datetime.now(pytz.timezone(timezone))

def days_between(dt1: datetime, dt2: datetime) -> int:
    """Calculate days between two datetime objects"""
    return abs((dt1.date() - dt2.date()).days)

def classify_slot_time(dt: datetime, params: Dict[str, Any]) -> str:
    """Classify slot as Early, Mid, or Late based on end time"""
    eml_config = params.get('eml', {})
    early_end = eml_config.get('earlyEnd', '22:01')
    mid_end = eml_config.get('midEnd', '22:31')
    
    # Parse the time thresholds
    early_hour, early_minute = map(int, early_end.split(':'))
    mid_hour, mid_minute = map(int, mid_end.split(':'))
    
    # Convert to minutes for comparison
    early_minutes = early_hour * 60 + early_minute
    mid_minutes = mid_hour * 60 + mid_minute
    slot_minutes = dt.hour * 60 + dt.minute
    
    if slot_minutes <= early_minutes:
        return 'Early'
    elif slot_minutes <= mid_minutes:
        return 'Mid'
    else:
        return 'Late'

def get_weekday(dt: datetime) -> str:
    """Get weekday name"""
    return dt.strftime('%A')

def get_week_index(dt: datetime, season_start: datetime) -> int:
    """Calculate week index from season start"""
    delta = dt - season_start
    return (delta.days // 7) + 1

def handle_overnight_slots(slots_df: pd.DataFrame, timezone: str) -> pd.DataFrame:
    """Handle slots that span overnight"""
    # This is a placeholder - overnight handling would go here
    return slots_df
