#!/usr/bin/env python3

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from engine.pipeline import run_pipeline
import json

# Sample data for testing
sample_slots = [
    {
        "id": 1,
        "type": "09/05/25",
        "event_start": "9:00 PM",
        "event_end": "10:20 PM",
        "resource": "GPI - Rink 1"
    },
    {
        "id": 2,
        "type": "09/05/25",
        "event_start": "10:30 PM",
        "event_end": "11:50 PM",
        "resource": "GPI - Rink 1"
    },
    {
        "id": 3,
        "type": "09/06/25",
        "event_start": "9:00 PM",
        "event_end": "10:20 PM",
        "resource": "GPI - Rink 2"
    },
    {
        "id": 4,
        "type": "09/06/25",
        "event_start": "10:30 PM",
        "event_end": "11:50 PM",
        "resource": "GPI - Rink 2"
    }
]

sample_teams = [
    {"id": 1, "name": "Team 1", "division_id": 1},
    {"id": 2, "name": "Team 2", "division_id": 1},
    {"id": 3, "name": "Team 3", "division_id": 1},
    {"id": 4, "name": "Team 4", "division_id": 1}
]

sample_divisions = [
    {"id": 1, "name": "Division A"}
]

sample_params = {
    "timezone": "America/Chicago",
    "noBackToBack": True,
    "subDivisionCrossover": False,
    "minRestDays": 3,
    "maxGapDays": 12,
    "idealGapDays": 7,
    "eml": {
        "earlyEnd": "22:01",
        "midEnd": "22:31"
    },
    "gamesPerTeam": 6,
    "weekdayBalance": True,
    "varianceMinimization": True,
    "homeAwayBalance": True,
    "holidayAwareness": True,
    "weights": {
        "gapBias": 1,
        "idleUrgency": 8,
        "emlBalance": 5,
        "weekRotation": 4,
        "weekdayBalance": 0.5,
        "homeAway": 0.5
    },
    "seed": 42
}

def test_scheduler():
    print("=== Testing Scheduler ===")
    print(f"Slots: {len(sample_slots)}")
    print(f"Teams: {len(sample_teams)}")
    print(f"Divisions: {len(sample_divisions)}")
    
    try:
        result = run_pipeline(sample_slots, sample_divisions, sample_teams, sample_params)
        
        if result.empty:
            print("❌ No schedule generated")
            return
        
        print(f"✅ Generated {len(result)} games")
        print("\nSchedule:")
        print(result.to_string(index=False))
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_scheduler()
