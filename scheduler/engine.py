"""
Core scheduling engine using greedy assignment with optimization.
"""

import random
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from .models import Slot, Team, Matchup, ScheduledGame, Schedule, EMLCategory
from .config import SchedulerConfig
from .eml import get_eml_balance_penalty


class SchedulingEngine:
    """Core scheduling engine with greedy assignment."""
    
    def __init__(self, config: SchedulerConfig):
        self.config = config
        random.seed(config.seed)
        
    def schedule(self, slots: List[Slot], matchups: List[Matchup], teams: Dict[str, Team]) -> Schedule:
        """
        Main scheduling function.
        
        Args:
            slots: Available time slots
            matchups: Matchups to schedule
            teams: Team objects with state
        
        Returns:
            Schedule: Complete schedule
        """
        schedule = Schedule()
        schedule.teams = teams
        schedule.slots = slots
        schedule.matchups = matchups
        
        # Sort slots chronologically
        available_slots = sorted(slots, key=lambda x: x.start_time)
        
        # Sort matchups by priority (week target, then order)
        unscheduled_matchups = sorted(matchups, key=lambda x: (x.week_target, x.order_in_week))
        
        # Track scheduled games for constraint checking
        scheduled_games = []
        
        for matchup in unscheduled_matchups:
            # Find eligible slots for this matchup
            eligible_slots = self._find_eligible_slots(
                matchup, available_slots, scheduled_games, teams
            )
            
            if not eligible_slots:
                print(f"Warning: No eligible slots found for {matchup.matchup_id}")
                continue
            
            # Score and select best slot
            best_slot, score = self._select_best_slot(matchup, eligible_slots, teams)
            
            if best_slot:
                # Schedule the game
                game = self._create_scheduled_game(matchup, best_slot, teams)
                schedule.add_game(game)
                scheduled_games.append(game)
                
                # Update team states
                self._update_team_states(game, teams)
                
                # Remove slot from available
                available_slots.remove(best_slot)
                
                print(f"Scheduled {matchup.matchup_id} in {best_slot.slot_id} (score: {score:.2f})")
            else:
                print(f"Failed to schedule {matchup.matchup_id}")
        
        return schedule
    
    def _find_eligible_slots(self, matchup: Matchup, available_slots: List[Slot], 
                           scheduled_games: List[ScheduledGame], teams: Dict[str, Team]) -> List[Slot]:
        """Find slots eligible for a matchup."""
        eligible = []
        
        for slot in available_slots:
            if self._is_slot_eligible(matchup, slot, scheduled_games, teams):
                eligible.append(slot)
        
        return eligible
    
    def _is_slot_eligible(self, matchup: Matchup, slot: Slot, 
                         scheduled_games: List[ScheduledGame], teams: Dict[str, Team]) -> bool:
        """Check if a slot is eligible for a matchup."""
        home_team = teams[matchup.home_team]
        away_team = teams[matchup.away_team]
        
        # Check rest days constraint
        home_rest = home_team.get_rest_days(slot.start_time)
        away_rest = away_team.get_rest_days(slot.start_time)
        
        if home_rest < self.config.rest_min_days or away_rest < self.config.rest_min_days:
            return False
        
        # Check for conflicts (same team already scheduled in this slot)
        for game in scheduled_games:
            if game.scheduled_date == slot.start_time:
                if (matchup.home_team in game.matchup.teams or 
                    matchup.away_team in game.matchup.teams):
                    return False
        
        return True
    
    def _select_best_slot(self, matchup: Matchup, eligible_slots: List[Slot], 
                         teams: Dict[str, Team]) -> Tuple[Optional[Slot], float]:
        """Select the best slot for a matchup based on scoring."""
        if not eligible_slots:
            return None, 0.0
        
        best_slot = None
        best_score = float('inf')
        
        for slot in eligible_slots:
            score = self._calculate_slot_score(matchup, slot, teams)
            if score < best_score:
                best_score = score
                best_slot = slot
        
        return best_slot, best_score
    
    def _calculate_slot_score(self, matchup: Matchup, slot: Slot, teams: Dict[str, Team]) -> float:
        """Calculate score for a slot-matchup combination (lower is better)."""
        home_team = teams[matchup.home_team]
        away_team = teams[matchup.away_team]
        
        score = 0.0
        
        # 1. Idle urgency (teams that haven't played in a while get priority)
        home_idle = home_team.get_rest_days(slot.start_time)
        away_idle = away_team.get_rest_days(slot.start_time)
        
        # Exponential penalty for long idle periods
        home_idle_penalty = self._calculate_idle_penalty(home_idle)
        away_idle_penalty = self._calculate_idle_penalty(away_idle)
        score += self.config.weights.idle_urgency * (home_idle_penalty + away_idle_penalty)
        
        # 2. E/M/L balance
        home_eml_penalty = get_eml_balance_penalty(home_team.eml_counts)
        away_eml_penalty = get_eml_balance_penalty(away_team.eml_counts)
        score += self.config.weights.eml_need * (home_eml_penalty + away_eml_penalty)
        
        # 3. Home/away balance
        home_ha_penalty = abs(home_team.get_home_away_balance())
        away_ha_penalty = abs(away_team.get_home_away_balance())
        score += self.config.weights.home_away_bias * (home_ha_penalty + away_ha_penalty)
        
        # 4. Week rotation (prefer slots closer to target week)
        week_diff = abs(matchup.week_target - self._get_week_number(slot.start_time))
        score += self.config.weights.week_rotation * week_diff
        
        # 5. Random tie-breaker
        score += random.random() * 0.1
        
        return score
    
    def _calculate_idle_penalty(self, idle_days: int) -> float:
        """Calculate penalty for idle days (exponential increase near max_gap)."""
        if idle_days <= self.config.rest_min_days:
            return 0.0
        
        # Exponential penalty as we approach max_gap_days
        if idle_days >= self.config.max_gap_days:
            return 1000.0  # Very high penalty for exceeding max gap
        
        # Exponential curve from rest_min_days to max_gap_days
        normalized = (idle_days - self.config.rest_min_days) / (self.config.max_gap_days - self.config.rest_min_days)
        return normalized ** 2
    
    def _get_week_number(self, date: datetime) -> int:
        """Get week number from date (simple implementation)."""
        # This could be made more sophisticated based on league start date
        return (date.date() - datetime.now().date()).days // 7 + 1
    
    def _create_scheduled_game(self, matchup: Matchup, slot: Slot, teams: Dict[str, Team]) -> ScheduledGame:
        """Create a scheduled game."""
        home_team = teams[matchup.home_team]
        away_team = teams[matchup.away_team]
        
        days_since_home = home_team.get_rest_days(slot.start_time)
        days_since_away = away_team.get_rest_days(slot.start_time)
        
        return ScheduledGame(
            matchup=matchup,
            slot=slot,
            scheduled_date=slot.start_time,
            days_since_home_played=days_since_home,
            days_since_away_played=days_since_away
        )
    
    def _update_team_states(self, game: ScheduledGame, teams: Dict[str, Team]):
        """Update team states after scheduling a game."""
        home_team = teams[game.matchup.home_team]
        away_team = teams[game.matchup.away_team]
        
        home_team.update_after_game(game.scheduled_date, True, game.slot.eml_category)
        away_team.update_after_game(game.scheduled_date, False, game.slot.eml_category)


def schedule(slots: List[Slot], matchups: List[Matchup], config: SchedulerConfig, 
            teams: Optional[Dict[str, Team]] = None) -> Schedule:
    """
    Convenience function to run the scheduler.
    
    Args:
        slots: Available time slots
        matchups: Matchups to schedule
        config: Scheduler configuration
        teams: Optional team objects (will be created from config if not provided)
    
    Returns:
        Schedule: Complete schedule
    """
    if teams is None:
        from .ingest import create_teams_from_config
        teams = create_teams_from_config(config)
    
    engine = SchedulingEngine(config)
    return engine.schedule(slots, matchups, teams)


def validate_schedule(schedule: Schedule, config: SchedulerConfig) -> Dict[str, List[str]]:
    """
    Validate a completed schedule for constraint violations.
    
    Args:
        schedule: Schedule to validate
        config: Scheduler configuration
    
    Returns:
        Dict[str, List[str]]: Validation results
    """
    violations = {
        'errors': [],
        'warnings': []
    }
    
    if not schedule.games:
        violations['errors'].append("No games scheduled")
        return violations
    
    # Check rest day violations
    for game in schedule.games:
        home_team = schedule.teams[game.matchup.home_team]
        away_team = schedule.teams[game.matchup.away_team]
        
        home_rest = home_team.get_rest_days(game.scheduled_date)
        away_rest = away_team.get_rest_days(game.scheduled_date)
        
        if home_rest < config.rest_min_days:
            violations['errors'].append(
                f"Home team {game.matchup.home_team} has insufficient rest: {home_rest} days"
            )
        
        if away_rest < config.rest_min_days:
            violations['errors'].append(
                f"Away team {game.matchup.away_team} has insufficient rest: {away_rest} days"
            )
    
    # Check for scheduling conflicts
    games_by_date = {}
    for game in schedule.games:
        date = game.scheduled_date.date()
        if date not in games_by_date:
            games_by_date[date] = []
        games_by_date[date].append(game)
    
    for date, games in games_by_date.items():
        teams_on_date = set()
        for game in games:
            for team in game.matchup.teams:
                if team in teams_on_date:
                    violations['errors'].append(
                        f"Team {team} scheduled multiple games on {date}"
                    )
                teams_on_date.add(team)
    
    # Check for unscheduled matchups
    scheduled_matchup_ids = {game.matchup.matchup_id for game in schedule.games}
    all_matchup_ids = {matchup.matchup_id for matchup in schedule.matchups}
    unscheduled = all_matchup_ids - scheduled_matchup_ids
    
    if unscheduled:
        violations['warnings'].append(f"Unscheduled matchups: {len(unscheduled)}")
    
    return violations
