"""
Data models for the league scheduler.
"""

from dataclasses import dataclass, field
from datetime import datetime, date
from typing import List, Optional, Dict, Any
from enum import Enum
import pandas as pd


class Weekday(Enum):
    """Weekday enumeration."""
    MONDAY = "Monday"
    TUESDAY = "Tuesday"
    WEDNESDAY = "Wednesday"
    THURSDAY = "Thursday"
    FRIDAY = "Friday"
    SATURDAY = "Saturday"
    SUNDAY = "Sunday"


class EMLCategory(Enum):
    """E/M/L game categories."""
    EARLY = "E"
    MID = "M"
    LATE = "L"


@dataclass
class Slot:
    """A time slot available for scheduling."""
    start_time: datetime
    end_time: datetime
    resource: str
    slot_type: str
    weekday: Weekday
    eml_category: EMLCategory
    slot_id: Optional[str] = None
    
    def __post_init__(self):
        if self.slot_id is None:
            self.slot_id = f"{self.resource}_{self.start_time.strftime('%Y%m%d_%H%M')}"
    
    @property
    def date(self) -> date:
        """Get the date of this slot."""
        return self.start_time.date()
    
    @property
    def duration_hours(self) -> float:
        """Get the duration in hours."""
        return (self.end_time - self.start_time).total_seconds() / 3600


@dataclass
class Team:
    """A team in the league."""
    name: str
    division: str
    sub_division: str
    
    # State tracking
    last_played: Optional[datetime] = None
    idle_days: int = 0
    eml_counts: Dict[EMLCategory, int] = field(default_factory=lambda: {EMLCategory.EARLY: 0, EMLCategory.MID: 0, EMLCategory.LATE: 0})
    home_count: int = 0
    away_count: int = 0
    games_played: int = 0
    
    def __post_init__(self):
        """Initialize default values."""
        if not self.eml_counts:
            self.eml_counts = {EMLCategory.EARLY: 0, EMLCategory.MID: 0, EMLCategory.LATE: 0}
    
    def update_after_game(self, game_date: datetime, is_home: bool, eml: EMLCategory):
        """Update team state after playing a game."""
        self.last_played = game_date
        self.eml_counts[eml] += 1
        if is_home:
            self.home_count += 1
        else:
            self.away_count += 1
        self.games_played += 1
    
    def get_rest_days(self, current_date: datetime) -> int:
        """Get days since last game."""
        if self.last_played is None:
            return 999  # Never played
        return (current_date.date() - self.last_played.date()).days
    
    def get_eml_balance_score(self) -> float:
        """Get E/M/L balance score (lower is better)."""
        counts = list(self.eml_counts.values())
        if not counts:
            return 0.0
        return max(counts) - min(counts)
    
    def get_home_away_balance(self) -> int:
        """Get home/away balance (positive = more home, negative = more away)."""
        return self.home_count - self.away_count


@dataclass
class Matchup:
    """A matchup between two teams."""
    home_team: str
    away_team: str
    division: str
    week_target: int
    order_in_week: int
    matchup_id: Optional[str] = None
    
    def __post_init__(self):
        if self.matchup_id is None:
            self.matchup_id = f"{self.home_team}_vs_{self.away_team}_W{self.week_target}"
    
    @property
    def teams(self) -> List[str]:
        """Get both teams in this matchup."""
        return [self.home_team, self.away_team]


@dataclass
class ScheduledGame:
    """A scheduled game."""
    matchup: Matchup
    slot: Slot
    scheduled_date: datetime
    days_since_home_played: int
    days_since_away_played: int
    game_id: Optional[str] = None
    
    def __post_init__(self):
        if self.game_id is None:
            self.game_id = f"{self.matchup.matchup_id}_{self.slot.slot_id}"


@dataclass
class Schedule:
    """A complete schedule."""
    games: List[ScheduledGame] = field(default_factory=list)
    teams: Dict[str, Team] = field(default_factory=dict)
    slots: List[Slot] = field(default_factory=list)
    matchups: List[Matchup] = field(default_factory=list)
    
    def add_game(self, game: ScheduledGame):
        """Add a game to the schedule."""
        self.games.append(game)
    
    def get_team_schedule(self, team_name: str) -> List[ScheduledGame]:
        """Get all games for a specific team."""
        return [game for game in self.games if team_name in game.matchup.teams]
    
    def get_games_by_date(self, game_date: date) -> List[ScheduledGame]:
        """Get all games on a specific date."""
        return [game for game in self.games if game.scheduled_date.date() == game_date]
    
    def to_dataframe(self) -> pd.DataFrame:
        """Convert schedule to pandas DataFrame."""
        if not self.games:
            return pd.DataFrame()
        
        data = []
        for game in self.games:
            data.append({
                'Week': game.matchup.week_target,
                'Order': game.matchup.order_in_week,
                'Date': game.scheduled_date.date(),
                'Day': game.slot.weekday.value,
                'Start Time': game.slot.start_time.time(),
                'End Time': game.slot.end_time.time(),
                'Resource': game.slot.resource,
                'Home Team': game.matchup.home_team,
                'Away Team': game.matchup.away_team,
                'Division': game.matchup.division,
                'EML': game.slot.eml_category.value,
                'Days Since Home Played': game.days_since_home_played,
                'Days Since Away Played': game.days_since_away_played,
                'Game ID': game.game_id
            })
        
        df = pd.DataFrame(data)
        return df.sort_values(['Date', 'Start Time']).reset_index(drop=True)
    
    def get_summary_stats(self) -> Dict[str, Any]:
        """Get summary statistics for the schedule."""
        if not self.games:
            return {}
        
        df = self.to_dataframe()
        
        stats = {
            'total_games': len(self.games),
            'total_teams': len(self.teams),
            'date_range': {
                'start': df['Date'].min(),
                'end': df['Date'].max()
            },
            'eml_distribution': df['EML'].value_counts().to_dict(),
            'weekday_distribution': df['Day'].value_counts().to_dict(),
            'division_games': df['Division'].value_counts().to_dict()
        }
        
        return stats


@dataclass
class SwapLog:
    """Log entry for a schedule swap."""
    swap_id: str
    original_game: ScheduledGame
    new_game: ScheduledGame
    reason: str
    improvement_score: float
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for export."""
        return {
            'swap_id': self.swap_id,
            'reason': self.reason,
            'improvement_score': self.improvement_score,
            'timestamp': self.timestamp,
            'original_home': self.original_game.matchup.home_team,
            'original_away': self.original_game.matchup.away_team,
            'original_date': self.original_game.scheduled_date.date(),
            'original_time': self.original_game.slot.start_time.time(),
            'new_home': self.new_game.matchup.home_team,
            'new_away': self.new_game.matchup.away_team,
            'new_date': self.new_game.scheduled_date.date(),
            'new_time': self.new_game.slot.start_time.time(),
        }
