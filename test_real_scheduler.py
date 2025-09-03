#!/usr/bin/env python3

import sys
sys.path.append('/Users/egengarella/Scheduler')
from scheduler_api.enhanced_scheduler import EnhancedScheduler
from datetime import datetime, timedelta

# Test the ACTUAL scheduler with real data
params = {'noInterdivision': True, 'gamesPerTeam': 6, 'debugSegments': True}
scheduler = EnhancedScheduler(params)

# Create realistic test data
teams = [
    {'name': 'Team 1', 'division': 'div 12'},
    {'name': 'Team 2', 'division': 'div 12'},
    {'name': 'Team 3', 'division': 'div 12'},
    {'name': 'Team 4', 'division': 'div 12'},
    {'name': 'Team 5', 'division': 'div 12'},
    {'name': 'Team 6', 'division': 'div 12'},
    {'name': 'Team 7', 'division': 'div 12'},
    {'name': 'Team 8', 'division': 'div 12'},
    {'name': 'Team 9', 'division': 'div 12'},
    {'name': 'Team 10', 'division': 'div 12'},
    {'name': 'Team 11', 'division': 'div 12'},
    {'name': 'Team 12', 'division': 'div 12'},
    {'name': '1', 'division': 'Div 8'},
    {'name': '2', 'division': 'Div 8'},
    {'name': '3', 'division': 'Div 8'},
    {'name': '4', 'division': 'Div 8'},
    {'name': '5', 'division': 'Div 8'},
    {'name': '6', 'division': 'Div 8'},
    {'name': '7', 'division': 'Div 8'},
    {'name': '8', 'division': 'Div 8'}
]

# Create realistic slots (30 slots = 3 segments of 10)
slots = []
base_date = datetime(2025, 12, 1, 20, 0)  # 8 PM start

for i in range(30):
    slot_date = base_date + timedelta(days=i)
    slots.append({
        "SlotID": f"slot_{i+1}",
        "event_start": slot_date.isoformat(),
        "event_end": (slot_date + timedelta(hours=1)).isoformat(),
        "Rink": f"GPI - Rink {(i % 4) + 1}",
        "Week": f"Week {(i // 7) + 1}",
        "Bucket": "Mid",
        "Holiday": False
    })

print(f'🔧 Testing REAL scheduler with:')
print(f'   - {len(teams)} teams')
print(f'   - {len(slots)} slots')
print(f'   - noInterdivision: {params["noInterdivision"]}')
print(f'   - gamesPerTeam: {params["gamesPerTeam"]}')
print(f'   - debugSegments: {params["debugSegments"]}')

try:
    # Run the actual scheduler
    print(f'\n🚀 Running scheduler...')
    schedule = scheduler.build_schedule(slots, teams)
    
    print(f'\n✅ Schedule generated successfully!')
    print(f'   Total games: {len(schedule)}')
    
    # Analyze the schedule for segment violations
    print(f'\n🔍 Analyzing schedule for segment violations...')
    
    # Group games by segment
    segments = {}
    for game in schedule:
        slot_id = game["SlotID"]
        # Find the slot to get segment info
        slot = next((s for s in slots if s["SlotID"] == slot_id), None)
        if slot:
            seg = slot.get("Segment", 0)
            if seg not in segments:
                segments[seg] = []
            segments[seg].append(game)
    
    # Check each segment
    for seg_num in sorted(segments.keys()):
        games_in_seg = segments[seg_num]
        teams_in_seg = []
        
        for game in games_in_seg:
            teams_in_seg.extend([game["HomeTeam"], game["AwayTeam"]])
        
        # Check for duplicates
        duplicates = [team for team in set(teams_in_seg) if teams_in_seg.count(team) > 1]
        
        print(f'\n   Segment {seg_num}: {len(games_in_seg)} games')
        print(f'     Teams: {teams_in_seg}')
        
        if duplicates:
            print(f'     ❌ VIOLATION: Teams {duplicates} play multiple times!')
        else:
            print(f'     ✅ All teams unique in this segment')
    
    print(f'\n🎯 Segment enforcement test complete!')
    
except Exception as e:
    print(f'\n❌ Scheduler failed with error: {e}')
    import traceback
    traceback.print_exc()
