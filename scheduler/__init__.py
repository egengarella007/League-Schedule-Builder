"""
League Scheduler - Production-quality scheduling engine with optimization passes.
"""

__version__ = "0.1.0"

from .config import SchedulerConfig
from .models import Slot, Team, Matchup, Schedule
from .engine import schedule
from .export import write_excel

__all__ = [
    "SchedulerConfig",
    "Slot", 
    "Team",
    "Matchup",
    "Schedule",
    "schedule",
    "write_excel",
]
