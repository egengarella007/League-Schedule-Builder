from __future__ import annotations
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import timedelta
import math, random, json
import pandas as pd
from supabase import create_client, Client

# ---------- config ----------
SUPABASE_URL = "https://zcoupiuradompbrsebdp.supabase.co"
SUPABASE_SERVICE_ROLE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Inpjb3VwaXVyYWRvbXBicnNlYmRwIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc1NjYzNDc5MywiZXhwIjoyMDcyMjEwNzkzfQ.lKqb0Po0td0WVkbGH1MtNARUa3WGwFb7BZvPNjLkY7o"

# ---------- models ----------
@dataclass
class Slot:
    id: str
    start: pd.Timestamp     # UTC
    end: pd.Timestamp       # UTC
    rink: Optional[str]
    eml: str
    weekday: str
    week_index: int

@dataclass
class Matchup:
    division: str
    home: str
    away: str
    round_index: int

@dataclass
class TeamState:
    last_played: Optional[pd.Timestamp] = None
    eml_counts: Dict[str,int] = field(default_factory=lambda: {"E":0,"M":0,"L":0})
    weekday_counts: Dict[str,int] = field(default_factory=dict)
    home_count: int = 0
    away_count: int = 0
    first_slot_weeks: set = field(default_factory=set)

# ---------- helpers ----------
def days_between(prev: Optional[pd.Timestamp], next_: pd.Timestamp) -> Optional[int]:
    if prev is None: return None
    return int((next_.date() - prev.date()).days)

def classify_eml(end_local_hhmm: str, early_end: str, mid_end: str) -> str:
    return "E" if end_local_hhmm < early_end else ("M" if end_local_hhmm < mid_end else "L")

# ---------- fetch & prepare ----------
def fetch_inputs(supabase: Client, league_id: str, params: Dict) -> Tuple[List[Slot], List[Dict], List[Dict]]:
    # slots
    res = supabase.table("slots").select("*").eq("league_id", league_id).order("event_start").execute()
    rows = res.data or []
    tz = params.get("timezone", "America/Chicago")

    df = pd.DataFrame(rows)
    if df.empty:
        return [], [], []

    df["start"] = pd.to_datetime(df["event_start"], utc=True)
    df["end"]   = pd.to_datetime(df["event_end"],   utc=True)
    overnight = df["end"] < df["start"]
    if overnight.any():
        df.loc[overnight, "end"] = df.loc[overnight, "end"] + pd.Timedelta(days=1)

    end_local = df["end"].dt.tz_convert(tz)
    df["weekday"] = end_local.dt.day_name()
    df["end_hhmm"] = end_local.dt.strftime("%H:%M")

    early = params["eml"]["earlyEnd"]
    mid   = params["eml"]["midEnd"]
    df["eml"] = df["end_hhmm"].apply(lambda t: classify_eml(t, early, mid))

    start_local = df["start"].dt.tz_convert(tz)
    season_start = start_local.min().normalize()
    df["week_index"] = ((start_local.dt.normalize() - season_start) / pd.Timedelta(days=7)).astype(int) + 1

    df = df.sort_values("start")
    slots = [
        Slot(
            id=str(r.id),
            start=r.start,
            end=r.end,
            rink=r.resource,
            eml=r.eml,
            weekday=r.weekday,
            week_index=int(r.week_index),
        )
        for r in df.itertuples(index=False)
    ]

    # divisions & teams
    divs = supabase.table("divisions").select("*").eq("league_id", league_id).execute().data or []
    teams = supabase.table("teams").select("*").eq("league_id", league_id).execute().data or []
    return slots, divs, teams

# ---------- matchup generation ----------
def mirrored_round(teams: List[str]) -> List[Tuple[str,str]]:
    t = teams[:]
    if len(t) % 2 == 1: t.append("BYE")
    n = len(t); pairs=[]
    for i in range(n//2):
        a,b = t[i], t[-(i+1)]
        if "BYE" not in (a,b): pairs.append((a,b))
    return pairs

def round_robin(teams: List[str]) -> List[List[Tuple[str,str]]]:
    t = teams[:]
    if len(t) % 2 == 1: t.append("BYE")
    n = len(t); half = n//2; arr = t[:]; rounds=[]
    for _ in range(n-1):
        pairs=[]
        for i in range(half):
            a,b = arr[i], arr[-(i+1)]
            if "BYE" not in (a,b): pairs.append((a,b))
        rounds.append(pairs)
        arr = [arr[0]] + [arr[-1]] + arr[1:-1]
    return rounds

def fit_games_per_team(pool: List[Matchup], target: int) -> List[Matchup]:
    from collections import Counter
    cnt = Counter()
    for m in pool:
        cnt[m.home]+=1; cnt[m.away]+=1
    i=0
    while any(cnt[t] < target for t in cnt):
        m = pool[i % len(pool)]
        rev = Matchup(m.division, m.away, m.home, m.round_index)
        pool.append(rev); cnt[rev.home]+=1; cnt[rev.away]+=1; i+=1
    # prune evenly
    keep=[]; per=Counter(); rng=random.Random(42)
    for m in rng.sample(pool, len(pool)):
        if per[m.home] < target and per[m.away] < target:
            keep.append(m); per[m.home]+=1; per[m.away]+=1
    return keep

def build_matchups(divs: List[Dict], teams: List[Dict], params: Dict) -> List[Matchup]:
    id2name = {d["id"]: d["name"] for d in divs}
    by_div: Dict[str,List[str]] = {}
    for t in teams:
        by_div.setdefault(id2name[t["division_id"]], []).append(t["name"])

    pool: List[Matchup] = []
    for div_name, names in by_div.items():
        names = sorted(names)
        rr = round_robin(names)
        for r_i, pairs in enumerate(rr, 1):
            for a,b in pairs:
                pool.append(Matchup(div_name, a, b, r_i))

    if params.get("subDivisionCrossover", False) and len(by_div) > 1:
        div_names = list(by_div.keys())
        for i in range(len(div_names)):
            for j in range(i+1, len(div_names)):
                A, B = by_div[div_names[i]], by_div[div_names[j]]
                for a in A:
                    for b in B:
                        pool.append(Matchup(f"{div_names[i]}×{div_names[j]}", a, b, 999))

    return fit_games_per_team(pool, params["gamesPerTeam"])

# ---------- assignment ----------
def eligible(slot: Slot, m: Matchup, state: Dict[str,TeamState], p: Dict) -> bool:
    gA = days_between(state[m.home].last_played, slot.start)
    gB = days_between(state[m.away].last_played, slot.start)
    if gA is not None and gA < p["minRestDays"]: return False
    if gB is not None and gB < p["minRestDays"]: return False
    if p.get("noBackToBack", True) and (gA == 0 or gB == 0): return False
    return True

def would_break_cap(slot: Slot, m: Matchup, state: Dict[str,TeamState], p: Dict) -> bool:
    gA = days_between(state[m.home].last_played, slot.start)
    gB = days_between(state[m.away].last_played, slot.start)
    return (gA is not None and gA > p["maxGapDays"]) or (gB is not None and gB > p["maxGapDays"])

def cost(slot: Slot, m: Matchup, state: Dict[str,TeamState], p: Dict) -> float:
    A,B = m.home,m.away; stA,stB = state[A], state[B]
    ideal = p["idealGapDays"]
    def gap_term(st): 
        g = days_between(st.last_played, slot.start)
        return abs((g if g is not None else ideal) - ideal)
    gterm = gap_term(stA) + gap_term(stB)

    def urg(st):
        g = days_between(st.last_played, slot.start)
        if g is None: return 0.0
        return max(0.0, math.exp((g - (p["maxGapDays"]-2))/1.5)-1.0)
    uterm = urg(stA) + urg(stB)

    eml_term = stA.eml_counts.get(slot.eml,0) + stB.eml_counts.get(slot.eml,0)
    rot_term = 1.0 if (slot.week_index in stA.first_slot_weeks or slot.week_index in stB.first_slot_weeks) else 0.0
    wday_term = (stA.weekday_counts.get(slot.weekday,0) + stB.weekday_counts.get(slot.weekday,0)) if p.get("weekdayBalance", True) else 0.0
    ha_term = (abs((stA.home_count+1)-stA.away_count) + abs(stB.home_count-(stB.away_count+1))) if p.get("homeAwayBalance", False) else 0.0

    w=p["weights"]
    return (w["gapBias"]*gterm + w["idleUrgency"]*uterm + w["emlBalance"]*eml_term +
            w["weekRotation"]*rot_term + w["weekdayBalance"]*wday_term + w["homeAway"]*ha_term)

# ---------- main run ----------
def run_once(league_id: str, params: Dict):
    supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)

    # create run
    run = supabase.table("runs").insert({"league_id": league_id, "status": "running"}).execute().data[0]

    # fetch inputs
    slots, divs, teams = fetch_inputs(supabase, league_id, params)
    if not slots or not teams:
        supabase.table("runs").update({"status":"failed","finished_at":"now()","kpis":{"error":"missing inputs"}}).eq("id", run["id"]).execute()
        return

    # matchup pool + state
    pool = build_matchups(divs, teams, params)
    all_team_names = sorted({t["name"] for t in teams})
    state = {t: TeamState() for t in all_team_names}
    rng = random.Random(params.get("seed",42))

    # seed week 1 (mirrored pairs by earliest round first)
    week1 = slots[0].week_index
    w1_slots = [s for s in slots if s.week_index == week1]
    w1_assigned = set()

    # prefer lowest round_index
    pool.sort(key=lambda m: (m.round_index, rng.random()))

    for s in w1_slots:
        cands = [m for m in pool if eligible(s,m,state,params)]
        if not cands:
            supabase.table("schedule_games").insert({
                "league_id": league_id, "run_id": run["id"], "slot_id": s.id,
                "division": None, "home_team": None, "away_team": None,
                "eml": s.eml, "weekday": s.weekday, "note": "no-eligible"
            }).execute()
            continue
        pick = sorted(cands, key=lambda m: (m.round_index, rng.random()))[0]
        pool.remove(pick); w1_assigned.add(s.id)
        # commit state
        for team,is_home in [(pick.home,True),(pick.away,False)]:
            st=state[team]; st.last_played=s.start
            st.eml_counts[s.eml]=st.eml_counts.get(s.eml,0)+1
            st.weekday_counts[s.weekday]=st.weekday_counts.get(s.weekday,0)+1
            st.home_count += 1 if is_home else 0
            st.away_count += 1 if not is_home else 0
            st.first_slot_weeks.add(s.week_index)
        supabase.table("schedule_games").insert({
            "league_id": league_id, "run_id": run["id"], "slot_id": s.id,
            "division": pick.division, "home_team": pick.home, "away_team": pick.away,
            "eml": s.eml, "weekday": s.weekday
        }).execute()

    # remaining slots → greedy
    for s in slots[len(w1_slots):]:
        cands = [m for m in pool if eligible(s,m,state,params)]
        if not cands:
            supabase.table("schedule_games").insert({
                "league_id": league_id, "run_id": run["id"], "slot_id": s.id,
                "division": None, "home_team": None, "away_team": None,
                "eml": s.eml, "weekday": s.weekday, "note": "no-eligible"
            }).execute()
            continue

        urgent = [m for m in cands if would_break_cap(s,m,state,params)]
        candset = urgent if urgent else cands
        pick = sorted(candset, key=lambda m: (cost(s,m,state,params) + 1e-6*rng.random()))[0]
        pool.remove(pick)

        # update state
        for team,is_home in [(pick.home,True),(pick.away,False)]:
            st=state[team]; st.last_played=s.start
            st.eml_counts[s.eml]=st.eml_counts.get(s.eml,0)+1
            st.weekday_counts[s.weekday]=st.weekday_counts.get(s.weekday,0)+1
            st.home_count += 1 if is_home else 0
            st.away_count += 1 if not is_home else 0
            # first-of-week marker
            st.first_slot_weeks.add(s.week_index)

        supabase.table("schedule_games").insert({
            "league_id": league_id, "run_id": run["id"], "slot_id": s.id,
            "division": pick.division, "home_team": pick.home, "away_team": pick.away,
            "eml": s.eml, "weekday": s.weekday
        }).execute()

    # KPIs (quick version)
    games = supabase.table("schedule_games").select("*").eq("run_id", run["id"]).execute().data
    eml = {}
    for g in games:
        eml[g["eml"]] = eml.get(g["eml"],0) + (1 if g["home_team"] else 0)
    kpis = {"games": sum(1 for g in games if g["home_team"]),
            "unscheduled": sum(1 for g in games if not g["home_team"]),
            "EML": eml}

    supabase.table("runs").update({
        "status":"succeeded",
        "finished_at":"now()",
        "kpis": kpis
    }).eq("id", run["id"]).execute()

# ---------- example boot ----------
if __name__ == "__main__":
    # pull most recent params for a league (or pass them in directly)
    league_id = "00000000-0000-0000-0000-000000000001"
    supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
    p = supabase.table("scheduler_params").select("*").eq("league_id", league_id)\
        .order("created_at", desc=True).limit(1).execute().data[0]["params"]
    run_once(league_id, p)
