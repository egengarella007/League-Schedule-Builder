#!/usr/bin/env python3

import sys
sys.path.append('/Users/egengarella/Scheduler')
from scheduler_api.enhanced_scheduler import EnhancedScheduler
from collections import defaultdict

# Test the segment logic step by step
params = {'noInterdivision': True, 'gamesPerTeam': 6, 'debugSegments': True}
scheduler = EnhancedScheduler(params)

# Simulate the team data structure
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

# Test division mapping
team_names = [team['name'] for team in teams]
scheduler.team_div = {t['name']: scheduler._norm_div(t.get('division')) for t in teams}

print(f'✅ Team division mapping:')
for team, div in scheduler.team_div.items():
    print(f'   {team} → {div}')

# Test division round sizes
div_round = scheduler._div_round_sizes()
print(f'\n🔧 Division round sizes: {div_round}')
print(f'   Div 12: {div_round.get("div 12", 0)} games per round')
print(f'   Div 8: {div_round.get("div 8", 0)} games per round')
print(f'   Total per segment: {sum(div_round.values())}')

# Test segment assignment
test_slots = []
for i in range(30):  # 30 slots to test
    test_slots.append({
        "SlotID": f"slot_{i+1}",
        "Start": f"2025-12-{i+1:02d} 10:00 PM",
        "End": f"2025-12-{i+1:02d} 11:00 PM",
        "Rink": f"Rink {(i % 4) + 1}",
        "Week": f"Week {(i // 7) + 1}",
        "Bucket": "Mid"
    })

print(f'\n🔧 Testing segment assignment for {len(test_slots)} slots...')
processed_slots = scheduler._segment_and_assign_divisions(test_slots)

# Show segment assignments
print(f'\n📊 Segment assignments:')
segments = defaultdict(list)
for slot in processed_slots:
    seg = slot.get("Segment", 0)
    div = slot.get("AssignedDivision", "All")
    segments[seg].append((slot["SlotID"], div))

for seg_num in sorted(segments.keys()):
    print(f'   Segment {seg_num}: {len(segments[seg_num])} slots')
    for slot_id, div in segments[seg_num]:
        print(f'     {slot_id} → {div}')

# Test the "every 10 games, each team plays once" logic
print(f'\n🎯 Testing segment enforcement logic:')
print(f'   - Each segment should have exactly {sum(div_round.values())} slots')
print(f'   - Div 12 gets {div_round.get("div 12", 0)} slots per segment')
print(f'   - Div 8 gets {div_round.get("div 8", 0)} slots per segment')
print(f'   - Every team should play exactly once per segment')

# Simulate what happens when we try to assign games
print(f'\n🔍 Simulating game assignment...')
played_in_segment = defaultdict(set)

for i, slot in enumerate(processed_slots[:20]):  # Test first 20 slots
    seg = slot.get("Segment", 0)
    slot_div = slot.get("AssignedDivision", "All")
    
    print(f'\n   Slot {i+1} ({slot["SlotID"]}): Segment {seg}, Division {slot_div}')
    
    # Find available teams for this division
    available_teams = [t for t, d in scheduler.team_div.items() if d == slot_div]
    print(f'     Available teams: {available_teams}')
    
    # Find teams that haven't played in this segment yet
    unplayed_teams = [t for t in available_teams if t not in played_in_segment[seg]]
    print(f'     Teams not yet in segment {seg}: {unplayed_teams}')
    
    if len(unplayed_teams) >= 2:
        # Pick first two available teams
        team_a, team_b = unplayed_teams[0], unplayed_teams[1]
        print(f'     ✅ Assigning: {team_a} vs {team_b}')
        
        # Mark them as played in this segment
        played_in_segment[seg].add(team_a)
        played_in_segment[seg].add(team_b)
        
        print(f'     Teams now in segment {seg}: {list(played_in_segment[seg])}')
    else:
        print(f'     ❌ Not enough teams available for this slot')

print(f'\n✅ Segment enforcement test complete!')
print(f'   This should show exactly how the "every 10 games, each team plays once" rule works.')
