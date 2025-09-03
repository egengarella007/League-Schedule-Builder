"""
E/M/L (Early/Mid/Late) classification for game times.
"""

from datetime import time
from typing import Union
from .models import EMLCategory, Weekday


def eml_category(dt: Union[time, str], early_end: str = "21:59", mid_end: str = "22:34") -> EMLCategory:
    """
    Classify a time as Early, Mid, or Late based on end time.
    
    Args:
        dt: Time to classify (time object or string in HH:MM format)
        early_end: End time for early games (default: "21:59")
        mid_end: End time for mid games (default: "22:34")
    
    Returns:
        EMLCategory: EARLY, MID, or LATE
    """
    if isinstance(dt, str):
        dt = time.fromisoformat(dt)
    
    early_end_time = time.fromisoformat(early_end)
    mid_end_time = time.fromisoformat(mid_end)
    
    if dt <= early_end_time:
        return EMLCategory.EARLY
    elif dt <= mid_end_time:
        return EMLCategory.MID
    else:
        return EMLCategory.LATE


def get_weekday(dt) -> Weekday:
    """
    Get weekday from datetime object.
    
    Args:
        dt: datetime object
    
    Returns:
        Weekday: Weekday enum value
    """
    weekday_map = {
        0: Weekday.MONDAY,
        1: Weekday.TUESDAY,
        2: Weekday.WEDNESDAY,
        3: Weekday.THURSDAY,
        4: Weekday.FRIDAY,
        5: Weekday.SATURDAY,
        6: Weekday.SUNDAY
    }
    
    # datetime.weekday() returns 0=Monday, 6=Sunday
    return weekday_map[dt.weekday()]


def classify_slot_times(start_time, end_time, early_end: str = "21:59", mid_end: str = "22:34"):
    """
    Classify both start and end times of a slot.
    
    Args:
        start_time: Start time (datetime or time)
        end_time: End time (datetime or time)
        early_end: End time for early games
        mid_end: End time for mid games
    
    Returns:
        tuple: (start_eml, end_eml, weekday)
    """
    if hasattr(start_time, 'time'):
        start_t = start_time.time()
        end_t = end_time.time()
        weekday = get_weekday(start_time)
    else:
        start_t = start_time
        end_t = end_time
        weekday = None
    
    start_eml = eml_category(start_t, early_end, mid_end)
    end_eml = eml_category(end_t, early_end, mid_end)
    
    return start_eml, end_eml, weekday


def get_eml_preference_score(team_eml_counts, preferred_eml: EMLCategory = None) -> float:
    """
    Calculate E/M/L preference score for a team.
    
    Args:
        team_eml_counts: Dict of EML counts for the team
        preferred_eml: Preferred EML category (optional)
    
    Returns:
        float: Score indicating how much the team needs this EML category
    """
    if not team_eml_counts:
        return 0.0
    
    counts = list(team_eml_counts.values())
    min_count = min(counts)
    max_count = max(counts)
    
    # Base score is the difference between max and min
    score = max_count - min_count
    
    # If a preferred category is specified, boost score for that category
    if preferred_eml and preferred_eml in team_eml_counts:
        preferred_count = team_eml_counts[preferred_eml]
        if preferred_count < min_count:
            score += (min_count - preferred_count) * 2  # Boost for underrepresented preferred
    
    return score


def get_eml_balance_penalty(team_eml_counts) -> float:
    """
    Calculate penalty for E/M/L imbalance.
    
    Args:
        team_eml_counts: Dict of EML counts for the team
    
    Returns:
        float: Penalty score (higher = more imbalanced)
    """
    if not team_eml_counts:
        return 0.0
    
    counts = list(team_eml_counts.values())
    return max(counts) - min(counts)
