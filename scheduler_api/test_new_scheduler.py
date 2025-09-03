#!/usr/bin/env python3

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from engine.scheduler import run_scheduler
import json

# Sample data for testing
sample_slots = [
    {
        "id": 1,
        "event_start": "2025-09-05T21:00:00-05:00",
        "event_end": "2025-09-05T22:20:00-05:00",
        "resource": "GPI - Rink 1"
    },
    {
        "id": 2,
        "event_start": "2025-09-05T22:30:00-05:00",
        "event_end": "2025-09-05T23:50:00-05:00",
        "resource": "GPI - Rink 1"
    },
    {
        "id": 3,
        "event_start": "2025-09-06T21:00:00-05:00",
        "event_end": "2025-09-06T22:20:00-05:00",
        "resource": "GPI - Rink 2"
    },
    {
        "id": 4,
        "event_start": "2025-09-06T22:30:00-05:00",
        "event_end": "2025-09-06T23:50:00-05:00",
        "resource": "GPI - Rink 2"
    },
    {
        "id": 5,
        "event_start": "2025-09-07T21:00:00-05:00",
        "event_end": "2025-09-07T22:20:00-05:00",
        "resource": "GPI - Rink 1"
    },
    {
        "id": 6,
        "event_start": "2025-09-07T22:30:00-05:00",
        "event_end": "2025-09-07T23:50:00-05:00",
        "resource": "GPI - Rink 1"
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

def test_new_scheduler():
    print("=== Testing New Scheduler ===")
    print(f"Slots: {len(sample_slots)}")
    print(f"Teams: {len(sample_teams)}")
    print(f"Divisions: {len(sample_divisions)}")
    
    try:
        result_df, kpis = run_scheduler(
            slots_raw=sample_slots,
            divisions=sample_divisions,
            teams=sample_teams,
            params=sample_params
        )
        
        if result_df.empty:
            print("❌ No schedule generated")
            return
        
        print(f"✅ Generated {len(result_df)} rows")
        print(f"Games scheduled: {kpis.get('games', 0)}")
        print(f"Unscheduled slots: {kpis.get('unscheduled', 0)}")
        print(f"Max gap: {kpis.get('max_gap', 'N/A')}")
        print(f"Avg gap: {kpis.get('avg_gap', 'N/A')}")
        print(f"EML distribution: {kpis.get('EML', {})}")
        
        print("\nSchedule Preview:")
        print(result_df.head(10).to_string(index=False))
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_new_scheduler()
