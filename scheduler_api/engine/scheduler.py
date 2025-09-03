from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta
import math, random, json
import pandas as pd

# -----------------------------
# Models
# -----------------------------
@dataclass
class Slot:
    id: int
    start: pd.Timestamp      # tz-aware UTC
    end: pd.Timestamp        # tz-aware UTC
    rink: Optional[str]
    eml: str                 # "E","M","L" (by END time in local tz)
    weekday: str             # Monday..Sunday (local tz)
    week_index: int          # season-relative week idx (1..)
    division_hint: Optional[str] = None  # if slot is reserved per division, else None

@dataclass(frozen=True, eq=True)
class Matchup:
    division: str
    home: str
    away: str
    round_index: int         # for rotation scoring

@dataclass
class TeamState:
    last_played: Optional[pd.Timestamp] = None
    eml_counts: Dict[str,int] = field(default_factory=lambda: {"E":0,"M":0,"L":0})
    weekday_counts: Dict[str,int] = field(default_factory=dict)
    home_count: int = 0
    away_count: int = 0
    first_slot_weeks: set = field(default_factory=set)

# -----------------------------
# Helpers
# -----------------------------
def _days_between(prev: Optional[pd.Timestamp], next_: pd.Timestamp) -> Optional[int]:
    if prev is None: return None
    return int((next_.date() - prev.date()).days)

def _classify_eml(end_local_hhmm: str, early_end: str, mid_end: str) -> str:
    # UI semantics: "games ending before this time"
    if end_local_hhmm < early_end: return "E"
    if end_local_hhmm < mid_end:   return "M"
    return "L"

# -----------------------------
# Slots parsing / classification
# -----------------------------
def build_slots_df(slots_raw: List[Dict], params: Dict) -> pd.DataFrame:
    """slots_raw rows must have event_start, event_end (ISO or naive local),
    resource (rink), optional id."""
    tz = params.get("timezone", "America/Chicago")
    df = pd.DataFrame(slots_raw).copy()
    if "id" not in df.columns:
        df["id"] = range(1, len(df)+1)

    # Parse to tz-aware UTC
    df["start"] = pd.to_datetime(df["event_start"], utc=True)
    df["end"]   = pd.to_datetime(df["event_end"], utc=True)

    # Overnight guard (rare if times already include date)
    overnight = df["end"] < df["start"]
    if overnight.any():
        df.loc[overnight, "end"] = df.loc[overnight, "end"] + pd.Timedelta(days=1)

    # Localized features for E/M/L and weekday
    start_local = df["start"].dt.tz_convert(tz)
    end_local   = df["end"].dt.tz_convert(tz)
    df["weekday"] = end_local.dt.day_name()
    df["end_hhmm"] = end_local.dt.strftime("%H:%M")

    early = params["eml"]["earlyEnd"]   # e.g. "22:01"
    mid   = params["eml"]["midEnd"]     # e.g. "22:31"
    df["eml"] = df["end_hhmm"].apply(lambda t: _classify_eml(t, early, mid))

    # Season-relative week index (1..)
    season_start = start_local.min().normalize()
    df["week_index"] = ((start_local.dt.normalize() - season_start) / pd.Timedelta(days=7)).astype(int) + 1

    # Division hint (optional; leave None if not used)
    if "division_hint" not in df.columns:
        df["division_hint"] = None

    df = df[["id","start","end","resource","eml","weekday","week_index","division_hint"]].sort_values("start")
    return df

# -----------------------------
# Matchups generation
# -----------------------------
def _mirrored_round(team_names: List[str]) -> List[Tuple[str,str]]:
    t = team_names[:]
    if len(t) % 2 == 1:
        t.append("BYE")
    pairs = []
    n = len(t)
    for i in range(n // 2):
        a, b = t[i], t[-(i+1)]
        if "BYE" not in (a,b):
            pairs.append((a, b))
    return pairs

def _round_robin(teams: List[str]) -> List[List[Tuple[str,str]]]:
    t = teams[:]
    if len(t) % 2 == 1:
        t.append("BYE")
    n = len(t)
    half = n // 2
    rounds = []
    arr = t[:]
    for _ in range(n-1):
        pairs = []
        for i in range(half):
            a, b = arr[i], arr[-(i+1)]
            if "BYE" not in (a,b):
                pairs.append((a,b))
        rounds.append(pairs)
        # rotate (circle method)
        arr = [arr[0]] + [arr[-1]] + arr[1:-1]
    return rounds

def generate_matchups(divisions: List[Dict], teams: List[Dict], params: Dict) -> List[Matchup]:
    """Return a pool of Matchup (intra-division RR; optional cross-division),
       then trimmed/extended to hit gamesPerTeam per team overall."""
    # group team names by division label
    id2div = {d["id"]: d["name"] for d in divisions}
    by_div: Dict[str, List[str]] = {}
    for t in teams:
        by_div.setdefault(id2div[t["division_id"]], []).append(t["name"])

    # build intra-division rounds
    intra: List[Matchup] = []
    round_idx = 1
    for div_name, names in by_div.items():
        names = sorted(names)
        rr = _round_robin(names)
        for r_i, pairs in enumerate(rr, 1):
            for (a,b) in pairs:
                intra.append(Matchup(div_name, a, b, r_i))
        round_idx = max(round_idx, len(rr))

    # optional cross-division
    cross: List[Matchup] = []
    if params.get("subDivisionCrossover", False) and len(by_div) > 1:
        div_names = list(by_div.keys())
        for i in range(len(div_names)):
            for j in range(i+1, len(div_names)):
                A = by_div[div_names[i]]
                B = by_div[div_names[j]]
                for a in A:
                    for b in B:
                        cross.append(Matchup(f"{div_names[i]}×{div_names[j]}", a, b, round_idx+1))

    pool = intra + cross
    # Fit to gamesPerTeam (keep even counts)
    pool = _fit_games_per_team(pool, params["gamesPerTeam"])
    return pool

def _fit_games_per_team(pool: List[Matchup], games_per_team: int) -> List[Matchup]:
    from collections import Counter
    cnt = Counter()
    for m in pool:
        cnt[m.home]+=1; cnt[m.away]+=1
    # add reverse legs until everyone >= target
    i = 0
    while any(cnt[t] < games_per_team for t in cnt):
        m = pool[i % len(pool)]
        rev = Matchup(m.division, m.away, m.home, m.round_index)
        pool.append(rev)
        cnt[rev.home]+=1; cnt[rev.away]+=1
        i += 1
    # prune down evenly if needed
    keep: List[Matchup] = []
    per = Counter()
    rng = random.Random(42)
    for m in rng.sample(pool, len(pool)):
        if per[m.home] < games_per_team and per[m.away] < games_per_team:
            keep.append(m)
            per[m.home]+=1; per[m.away]+=1
    # Ensure every team present in counts (stable)
    return keep

# -----------------------------
# Assignment (seed week1 + greedy)
# -----------------------------
def _initial_state(all_teams: List[str]) -> Dict[str, TeamState]:
    return {t: TeamState() for t in all_teams}

def _eligible(slot: Slot, m: Matchup, state: Dict[str,TeamState], p: Dict) -> bool:
    gA = _days_between(state[m.home].last_played, slot.start)
    gB = _days_between(state[m.away].last_played, slot.start)
    if gA is not None and gA < p["minRestDays"]: return False
    if gB is not None and gB < p["minRestDays"]: return False
    if p.get("noBackToBack", True):
        if gA == 0 or gB == 0: return False
    return True

def _would_break_cap(slot: Slot, m: Matchup, state: Dict[str,TeamState], p: Dict) -> bool:
    gA = _days_between(state[m.home].last_played, slot.start)
    gB = _days_between(state[m.away].last_played, slot.start)
    return (gA is not None and gA > p["maxGapDays"]) or (gB is not None and gB > p["maxGapDays"])

def _cost(slot: Slot, m: Matchup, state: Dict[str,TeamState], p: Dict) -> float:
    A, B = m.home, m.away
    stA, stB = state[A], state[B]

    # gaps
    gapA = _days_between(stA.last_played, slot.start)
    gapB = _days_between(stB.last_played, slot.start)
    ideal = p["idealGapDays"]
    gA = abs((gapA if gapA is not None else ideal) - ideal)
    gB = abs((gapB if gapB is not None else ideal) - ideal)
    gap_term = gA + gB

    # urgency near cap
    def urg(g):
        if g is None: return 0.0
        return max(0.0, math.exp((g - (p["maxGapDays"] - 2)) / 1.5) - 1.0)
    urg_term = urg(gapA) + urg(gapB)

    # EML balance (avoid giving more of the same)
    eml_term = stA.eml_counts.get(slot.eml, 0) + stB.eml_counts.get(slot.eml, 0)

    # week rotation: penalize if first slot of week already used by either
    rot_term = 1.0 if slot.week_index in stA.first_slot_weeks or slot.week_index in stB.first_slot_weeks else 0.0

    # weekday balance
    wday_term = 0.0
    if p.get("weekdayBalance", True):
        wday_term = stA.weekday_counts.get(slot.weekday, 0) + stB.weekday_counts.get(slot.weekday, 0)

    # home/away balance (project imbalance if we pick this)
    ha_term = 0.0
    if p.get("homeAwayBalance", False):
        ha_term = abs((stA.home_count+1) - stA.away_count) + abs(stB.home_count - (stB.away_count+1))

    w = p["weights"]
    cost = (
        w["gapBias"]      * gap_term +
        w["idleUrgency"]  * urg_term +
        w["emlBalance"]   * eml_term +
        w["weekRotation"] * rot_term +
        w["weekdayBalance"] * wday_term +
        w["homeAway"]       * ha_term
    )
    return cost

def seed_week1(slots: List[Slot], pool: List[Matchup], state: Dict[str,TeamState], p: Dict):
    if not slots: return [], pool
    week1 = slots[0].week_index
    w1_slots = [s for s in slots if s.week_index == week1]
    # Build mirrored pairs per division from pool
    by_div: Dict[str,List[Matchup]] = {}
    for m in pool:
        by_div.setdefault(m.division, []).append(m)
    # prefer earliest pairings (round_index == 1)
    for div in list(by_div.keys()):
        by_div[div].sort(key=lambda m: m.round_index)

    assignments = []
    used: set = set()
    i = 0
    rng = random.Random(p.get("seed",42))
    for s in w1_slots:
        # find next earliest-round matchup for any division
        candidates = [m for m in pool if m not in used and _eligible(s, m, state, p)]
        if not candidates: 
            assignments.append((s, None))
            continue
        candidates.sort(key=lambda m: (m.round_index, rng.random()))
        pick = candidates[0]
        assignments.append((s, pick))
        used.add(pick)
        # commit state
        for team, is_home in [(pick.home, True), (pick.away, False)]:
            st = state[team]
            st.last_played = s.start
            st.eml_counts[s.eml] = st.eml_counts.get(s.eml,0)+1
            st.weekday_counts[s.weekday] = st.weekday_counts.get(s.weekday,0)+1
            if is_home: st.home_count += 1
            else: st.away_count += 1
        # mark first-of-week
        state[pick.home].first_slot_weeks.add(s.week_index)
        state[pick.away].first_slot_weeks.add(s.week_index)
        i += 1
    # remove used from pool
    pool2 = [m for m in pool if m not in used]
    return assignments, pool2

def greedy_assign(slots: List[Slot], start_idx: int, pool: List[Matchup], state: Dict[str,TeamState], p: Dict):
    rng = random.Random(p.get("seed",42))
    assignments = []
    for i in range(start_idx, len(slots)):
        s = slots[i]
        cands = [m for m in pool if _eligible(s, m, state, p)]

        if not cands:
            assignments.append((s, None))
            continue

        urgent = [m for m in cands if _would_break_cap(s, m, state, p)]
        candset = urgent if urgent else cands

        scored = []
        for m in candset:
            scored.append((_cost(s, m, state, p) + 1e-6*rng.random(), m))
        scored.sort(key=lambda x: x[0])
        _, pick = scored[0]

        assignments.append((s, pick))
        pool.remove(pick)
        # commit
        for team, is_home in [(pick.home, True), (pick.away, False)]:
            st = state[team]
            st.last_played = s.start
            st.eml_counts[s.eml] = st.eml_counts.get(s.eml,0)+1
            st.weekday_counts[s.weekday] = st.weekday_counts.get(s.weekday,0)+1
            if is_home: st.home_count += 1
            else: st.away_count += 1
        # first-of-week marker
        if i == 0 or s.week_index != slots[i-1].week_index:
            state[pick.home].first_slot_weeks.add(s.week_index)
            state[pick.away].first_slot_weeks.add(s.week_index)
    return assignments

# -----------------------------
# KPIs & export
# -----------------------------
def compute_kpis(final_df: pd.DataFrame, tz: str) -> Dict:
    # gaps per team from chronological schedule
    kpis = {}
    sched = final_df[final_df["HomeTeam"].notna()].copy()
    if sched.empty:
        return {"games":0,"unscheduled":len(final_df),"max_gap":None,"avg_gap":None,"EML":{},"weekday":{},"swaps":0}
    # gaps
    def team_gaps(name: str) -> List[int]:
        tdf = sched[(sched["HomeTeam"]==name)|(sched["AwayTeam"]==name)].sort_values("StartUTC")
        if len(tdf) < 2: return []
        gaps = []
        prev = tdf.iloc[0]["StartUTC"]
        for _, row in tdf.iloc[1:].iterrows():
            gaps.append(int((row["StartUTC"].date() - prev.date()).days))
            prev = row["StartUTC"]
        return gaps
    teams = sorted(set(sched["HomeTeam"])|set(sched["AwayTeam"]))
    all_gaps = []
    for t in teams:
        all_gaps += team_gaps(t)
    kpis["games"] = len(sched)
    kpis["unscheduled"] = int(final_df["HomeTeam"].isna().sum())
    kpis["max_gap"] = max(all_gaps) if all_gaps else None
    kpis["avg_gap"] = round(sum(all_gaps)/len(all_gaps),2) if all_gaps else None
    kpis["EML"] = sched["EML"].value_counts().to_dict()
    kpis["weekday"] = sched["Weekday"].value_counts().to_dict()
    kpis["swaps"] = 0
    return kpis

def to_xlsx(final_df: pd.DataFrame, path: str):
    with pd.ExcelWriter(path, engine="xlsxwriter") as w:
        final_df.to_excel(w, index=False, sheet_name="Final Schedule")

# -----------------------------
# Orchestration
# -----------------------------
def run_scheduler(slots_raw: List[Dict], divisions: List[Dict], teams: List[Dict], params: Dict,
                  write_path: Optional[str]=None) -> Tuple[pd.DataFrame, Dict]:
    sdf = build_slots_df(slots_raw, params)
    pool = generate_matchups(divisions, teams, params)

    # Convert to Slot objects
    slots: List[Slot] = []
    for r in sdf.itertuples(index=False):
        slots.append(Slot(
            id=int(r.id), start=r.start, end=r.end, rink=r.resource,
            eml=r.eml, weekday=r.weekday, week_index=int(r.week_index),
            division_hint=r.division_hint
        ))

    # Team universe
    all_teams = sorted(set([t["name"] for t in teams]))
    state = _initial_state(all_teams)

    # Week-1 seeding
    seed_assigns, pool = seed_week1(slots, pool, state, params)
    # Greedy for the rest
    start_idx = len(seed_assigns)  # because seed filled week-1 prefix
    tail = greedy_assign(slots, start_idx, pool, state, params)

    assignments = seed_assigns + tail

    # Build final schedule DataFrame
    rows = []
    tz = params.get("timezone","America/Chicago")
    for s, m in assignments:
        start_local = s.start.tz_convert(tz)
        end_local   = s.end.tz_convert(tz)
        if m is None:
            rows.append(dict(
                Date=start_local.strftime("%m/%d/%y"),
                Start=start_local.strftime("%I:%M %p"),
                End=end_local.strftime("%I:%M %p"),
                Rink=s.rink, Division=None, HomeTeam=None, AwayTeam=None,
                EML=s.eml, Weekday=s.weekday, Round=None, Note="no-eligible",
                StartUTC=s.start
            ))
        else:
            rows.append(dict(
                Date=start_local.strftime("%m/%d/%y"),
                Start=start_local.strftime("%I:%M %p"),
                End=end_local.strftime("%I:%M %p"),
                Rink=s.rink, Division=m.division, HomeTeam=m.home, AwayTeam=m.away,
                EML=s.eml, Weekday=s.weekday, Round=m.round_index, Note=None,
                StartUTC=s.start
            ))
    final_df = pd.DataFrame(rows).sort_values("StartUTC").reset_index(drop=True)

    kpis = compute_kpis(final_df, tz)
    if write_path:
        to_xlsx(final_df.drop(columns=["StartUTC"]), write_path)
    return final_df.drop(columns=["StartUTC"]), kpis
