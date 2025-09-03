from dataclasses import dataclass
from datetime import datetime
from typing import Optional, List, Dict, Any
import pandas as pd

@dataclass
class Slot:
    id: int
    event_start: datetime
    event_end: datetime
    resource: str
    weekday: str
    week_index: int
    eml_class: str
    assigned: bool = False

@dataclass
class Matchup:
    home_team_id: int
    away_team_id: int
    division_id: int
    assigned_slot: Optional[Slot] = None

@dataclass
class TeamState:
    team_id: int
    last_game_date: Optional[datetime] = None
    games_played: int = 0
    early_games: int = 0
    mid_games: int = 0
    late_games: int = 0
    home_games: int = 0
    away_games: int = 0
    weekday_counts: Dict[str, int] = None
    
    def __post_init__(self):
        if self.weekday_counts is None:
            self.weekday_counts = {
                'Monday': 0, 'Tuesday': 0, 'Wednesday': 0, 
                'Thursday': 0, 'Friday': 0, 'Saturday': 0, 'Sunday': 0
            }
