"""
Configuration management for the league scheduler.
"""

from pydantic import BaseModel, Field, field_validator
from typing import List, Dict, Optional, Union
from datetime import time
import pytz


class Weights(BaseModel):
    """Weights for different scheduling objectives."""
    eml_need: float = Field(default=1.0, ge=0.0, description="Weight for E/M/L balance")
    idle_urgency: float = Field(default=3.0, ge=0.0, description="Weight for idle day urgency")
    home_away_bias: float = Field(default=0.5, ge=0.0, description="Weight for home/away balance")
    week_rotation: float = Field(default=0.2, ge=0.0, description="Weight for week rotation")


class EMLCutoffs(BaseModel):
    """E/M/L time cutoffs in 24-hour format."""
    early_end: str = Field(default="21:59", description="End time for early games")
    mid_end: str = Field(default="22:34", description="End time for mid games")
    
    @field_validator('early_end', 'mid_end')
    @classmethod
    def validate_time_format(cls, v):
        try:
            time.fromisoformat(v)
            return v
        except ValueError:
            raise ValueError(f"Invalid time format: {v}. Use HH:MM format.")


class ExcelOut(BaseModel):
    """Excel output configuration."""
    include_summaries: bool = Field(default=True, description="Include summary sheets")
    sheets: Dict[str, Union[str, bool]] = Field(
        default_factory=lambda: {
            "final_name": "Final Schedule",
            "eml_spread": "E-M-L Spread", 
            "weekday_spread": "Weekday Spread",
            "swap_logs": True
        },
        description="Sheet names and options"
    )


class SubDivision(BaseModel):
    """A sub-division containing teams."""
    name: str
    teams: List[str]


class Division(BaseModel):
    """A division containing sub-divisions."""
    name: str
    sub_divisions: List[SubDivision]


class SchedulerConfig(BaseModel):
    """Main configuration for the league scheduler."""
    timezone: str = Field(default="America/Chicago", description="Timezone for scheduling")
    slot_type_filter: List[str] = Field(default=["Game Rental"], description="Slot types to include")
    columns: Dict[str, str] = Field(description="Column mappings for Excel import")
    divisions: List[Division] = Field(description="League divisions and teams")
    
    # Scheduling rules
    rest_min_days: int = Field(default=3, ge=1, description="Minimum rest days between games")
    max_gap_days: int = Field(default=12, ge=1, description="Maximum gap between games")
    target_gap_days: int = Field(default=7, ge=1, description="Target gap between games")
    smoothing_window_days: int = Field(default=10, ge=1, description="Window for gap smoothing")
    
    # Weekday balance
    weekday_heavy_threshold: int = Field(default=8, ge=1, description="Threshold for heavy weekday")
    weekday_light_threshold: int = Field(default=1, ge=0, description="Threshold for light weekday")
    weekday_balance_prefer: List[str] = Field(
        default=["Tuesday", "Wednesday", "Thursday", "Monday", "Friday", "Sunday"],
        description="Preferred weekday order for balancing"
    )
    
    # Home/away balance
    home_away_band: int = Field(default=2, ge=0, description="Home/away balance band (0 to disable)")
    
    # E/M/L configuration
    eml_cutoffs: EMLCutoffs = Field(default_factory=EMLCutoffs)
    
    # Weights
    weights: Weights = Field(default_factory=Weights)
    
    # Random seed for reproducibility
    seed: int = Field(default=42, description="Random seed for tie-breaking")
    
    # Output configuration
    excel: ExcelOut = Field(default_factory=ExcelOut)
    
    @field_validator('timezone')
    @classmethod
    def validate_timezone(cls, v):
        try:
            pytz.timezone(v)
            return v
        except pytz.exceptions.UnknownTimeZoneError:
            raise ValueError(f"Unknown timezone: {v}")
    
    @field_validator('weekday_balance_prefer')
    @classmethod
    def validate_weekdays(cls, v):
        valid_days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        for day in v:
            if day not in valid_days:
                raise ValueError(f"Invalid weekday: {day}. Must be one of {valid_days}")
        return v
    
    def get_all_teams(self) -> List[str]:
        """Get all teams from all divisions."""
        teams = []
        for division in self.divisions:
            for sub_div in division.sub_divisions:
                teams.extend(sub_div.teams)
        return teams
    
    def get_team_division(self, team: str) -> Optional[str]:
        """Get the division name for a given team."""
        for division in self.divisions:
            for sub_div in division.sub_divisions:
                if team in sub_div.teams:
                    return division.name
        return None


def load_config(config_path: str) -> SchedulerConfig:
    """Load configuration from YAML file."""
    import yaml
    
    with open(config_path, 'r') as f:
        config_data = yaml.safe_load(f)
    
    return SchedulerConfig(**config_data)


def save_config(config: SchedulerConfig, config_path: str) -> None:
    """Save configuration to YAML file."""
    import yaml
    
    with open(config_path, 'w') as f:
        yaml.dump(config.model_dump(), f, default_flow_style=False, indent=2)
