#!/usr/bin/env python3
"""
Test script for the proper row-by-row scheduler approach
"""

import json
from datetime import datetime, timedelta
import pandas as pd

# Sample parameters that match the UI schema
SAMPLE_PARAMS = {
    "timezone": "America/Chicago",
    "gamesPerTeam": 12,
    "noBackToBack": True,
    "subDivisionCrossover": False,
    "minRestDays": 3,
    "maxGapDays": 12,
    "idealGapDays": 7,
    "eml": {
        "earlyEnd": "22:01",
        "midEnd": "22:31"
    },
    "weekdayBalance": True,
    "varianceMinimization": False,
    "homeAwayBalance": True,
    "holidayAwareness": False,
    "weights": {
        "gapBias": 1.0,
        "idleUrgency": 8.0,
        "emlBalance": 5.0,
        "weekRotation": 4.0,
        "weekdayBalance": 0.5,
        "homeAway": 0.5
    },
    "seed": 42
}

# Sample data
SAMPLE_SLOTS = [
    {
        "id": "slot-1",
        "event_start": "2025-09-06T21:00:00Z",
        "event_end": "2025-09-06T22:20:00Z",
        "resource": "GPI - Rink 1"
    },
    {
        "id": "slot-2", 
        "event_start": "2025-09-06T22:30:00Z",
        "event_end": "2025-09-06T23:50:00Z",
        "resource": "GPI - Rink 2"
    },
    {
        "id": "slot-3",
        "event_start": "2025-09-07T20:00:00Z", 
        "event_end": "2025-09-07T21:20:00Z",
        "resource": "GPI - Rink 1"
    },
    {
        "id": "slot-4",
        "event_start": "2025-09-07T21:30:00Z",
        "event_end": "2025-09-07T22:50:00Z", 
        "resource": "GPI - Rink 2"
    }
]

SAMPLE_DIVISIONS = [
    {"id": "div-1", "name": "12-Team Division"},
    {"id": "div-2", "name": "8-Team Division"}
]

SAMPLE_TEAMS = [
    # 12-Team Division
    {"id": "team-1", "division_id": "div-1", "name": "Team 1"},
    {"id": "team-2", "division_id": "div-1", "name": "Team 2"},
    {"id": "team-3", "division_id": "div-1", "name": "Team 3"},
    {"id": "team-4", "division_id": "div-1", "name": "Team 4"},
    {"id": "team-5", "division_id": "div-1", "name": "Team 5"},
    {"id": "team-6", "division_id": "div-1", "name": "Team 6"},
    {"id": "team-7", "division_id": "div-1", "name": "Team 7"},
    {"id": "team-8", "division_id": "div-1", "name": "Team 8"},
    {"id": "team-9", "division_id": "div-1", "name": "Team 9"},
    {"id": "team-10", "division_id": "div-1", "name": "Team 10"},
    {"id": "team-11", "division_id": "div-1", "name": "Team 11"},
    {"id": "team-12", "division_id": "div-1", "name": "Team 12"},
    # 8-Team Division
    {"id": "team-13", "division_id": "div-2", "name": "South Team 1"},
    {"id": "team-14", "division_id": "div-2", "name": "South Team 2"},
    {"id": "team-15", "division_id": "div-2", "name": "South Team 3"},
    {"id": "team-16", "division_id": "div-2", "name": "South Team 4"},
    {"id": "team-17", "division_id": "div-2", "name": "South Team 5"},
    {"id": "team-18", "division_id": "div-2", "name": "South Team 6"},
    {"id": "team-19", "division_id": "div-2", "name": "South Team 7"},
    {"id": "team-20", "division_id": "div-2", "name": "South Team 8"}
]

def test_scheduler_logic():
    """Test the scheduler logic without database dependencies"""
    
    print("=== Testing Proper Scheduler Approach ===")
    print(f"Parameters: {json.dumps(SAMPLE_PARAMS, indent=2)}")
    print(f"Slots: {len(SAMPLE_SLOTS)}")
    print(f"Teams: {len(SAMPLE_TEAMS)}")
    print(f"Divisions: {len(SAMPLE_DIVISIONS)}")
    
    # Test slot processing
    print("\n=== Slot Processing ===")
    tz = SAMPLE_PARAMS.get("timezone", "America/Chicago")
    
    df = pd.DataFrame(SAMPLE_SLOTS)
    df["start"] = pd.to_datetime(df["event_start"], utc=True)
    df["end"] = pd.to_datetime(df["event_end"], utc=True)
    
    # Handle overnight events
    overnight = df["end"] < df["start"]
    if overnight.any():
        df.loc[overnight, "end"] = df.loc[overnight, "end"] + pd.Timedelta(days=1)
    
    # Localize for E/M/L classification
    end_local = df["end"].dt.tz_convert(tz)
    df["weekday"] = end_local.dt.day_name()
    df["end_hhmm"] = end_local.dt.strftime("%H:%M")
    
    # Classify E/M/L
    early = SAMPLE_PARAMS["eml"]["earlyEnd"]
    mid = SAMPLE_PARAMS["eml"]["midEnd"]
    
    def classify_eml(end_local_hhmm: str, early_end: str, mid_end: str) -> str:
        return "E" if end_local_hhmm < early_end else ("M" if end_local_hhmm < mid_end else "L")
    
    df["eml"] = df["end_hhmm"].apply(lambda t: classify_eml(t, early, mid))
    
    # Week index
    start_local = df["start"].dt.tz_convert(tz)
    season_start = start_local.min().normalize()
    df["week_index"] = ((start_local.dt.normalize() - season_start) / pd.Timedelta(days=7)).astype(int) + 1
    
    print("Processed slots:")
    for _, row in df.iterrows():
        print(f"  {row['start']} - {row['end']} | {row['resource']} | {row['eml']} | {row['weekday']} | Week {row['week_index']}")
    
    # Test matchup generation
    print("\n=== Matchup Generation ===")
    
    # Group teams by division
    id2name = {d["id"]: d["name"] for d in SAMPLE_DIVISIONS}
    by_div = {}
    for t in SAMPLE_TEAMS:
        by_div.setdefault(id2name[t["division_id"]], []).append(t["name"])
    
    print("Teams by division:")
    for div_name, names in by_div.items():
        print(f"  {div_name}: {names}")
    
    # Generate round-robin matchups
    def round_robin(teams: list) -> list:
        t = teams[:]
        if len(t) % 2 == 1:
            t.append("BYE")
        n = len(t)
        half = n // 2
        arr = t[:]
        rounds = []
        for _ in range(n-1):
            pairs = []
            for i in range(half):
                a, b = arr[i], arr[-(i+1)]
                if "BYE" not in (a, b):
                    pairs.append((a, b))
            rounds.append(pairs)
            arr = [arr[0]] + [arr[-1]] + arr[1:-1]
        return rounds
    
    pool = []
    for div_name, names in by_div.items():
        names = sorted(names)
        rr = round_robin(names)
        for r_i, pairs in enumerate(rr, 1):
            for a, b in pairs:
                pool.append({
                    "division": div_name,
                    "home": a,
                    "away": b,
                    "round_index": r_i
                })
    
    print(f"Generated {len(pool)} matchups:")
    for matchup in pool[:10]:  # Show first 10
        print(f"  {matchup['home']} vs {matchup['away']} ({matchup['division']}, Round {matchup['round_index']})")
    if len(pool) > 10:
        print(f"  ... and {len(pool) - 10} more")
    
    # Test assignment logic
    print("\n=== Assignment Logic ===")
    
    # Simulate assigning first few slots
    assigned_games = []
    remaining_matchups = pool.copy()
    
    for i, slot in enumerate(df.head(3).itertuples()):
        if not remaining_matchups:
            print(f"  Slot {i+1}: No eligible matchups")
            continue
        
        # Simple assignment: take first available matchup
        matchup = remaining_matchups.pop(0)
        assigned_games.append({
            "slot_id": slot.id,
            "date": slot.start.strftime("%m/%d/%y"),
            "start": slot.start.strftime("%I:%M %p"),
            "end": slot.end.strftime("%I:%M %p"),
            "rink": slot.resource,
            "division": matchup["division"],
            "home_team": matchup["home"],
            "away_team": matchup["away"],
            "eml": slot.eml,
            "weekday": slot.weekday
        })
        
        print(f"  Slot {i+1}: {matchup['home']} vs {matchup['away']} at {slot.resource}")
    
    print(f"\n=== Results ===")
    print(f"Assigned {len(assigned_games)} games")
    print(f"Remaining matchups: {len(remaining_matchups)}")
    
    # Show sample schedule
    print("\nSample Schedule:")
    for game in assigned_games:
        print(f"  {game['date']} {game['start']} | {game['rink']} | {game['home_team']} vs {game['away_team']} | {game['eml']}")
    
    print("\n✅ Proper approach test completed successfully!")
    print("\nNext steps:")
    print("1. Run the proper-schema.sql in Supabase SQL editor")
    print("2. Test the scheduler_worker.py with real database")
    print("3. Update the frontend to use the new approach")

if __name__ == "__main__":
    test_scheduler_logic()
