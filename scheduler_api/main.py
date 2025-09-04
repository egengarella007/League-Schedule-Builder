from fastapi import FastAPI, HTTPException
from fastapi.responses import Response, JSONResponse
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from io import BytesIO
import json
import pandas as pd
import xlsxwriter
from datetime import datetime, timedelta
import random

# Import the enhanced scheduler and optimization functions
from enhanced_scheduler import generate_enhanced_schedule
from schedule_optimizer import optimize_from_dict

app = FastAPI(title="League Scheduler API", version="1.0.0")

class ScheduleRequest(BaseModel):
    leagueId: str
    runId: Optional[str] = None
    params: Dict[str, Any]
    slots: List[Dict[str, Any]]
    teams: List[Dict[str, Any]]
    divisions: List[Dict[str, Any]]

class OptimizationRequest(BaseModel):
    schedule: List[Dict[str, Any]]
    blockSize: Optional[int] = None  # Will be calculated dynamically based on team count
    blockRecipe: Optional[Dict[str, int]] = None  # Will be calculated dynamically based on team count
    earlyStart: Optional[str] = None  # Will be calculated dynamically based on game duration
    midStart: Optional[str] = None    # Will be calculated dynamically based on game duration
    target_week: Optional[int] = None
    defaultGameMinutes: Optional[int] = None  # Will be calculated dynamically based on team count
    weights: Optional[Dict[str, float]] = None  # Will be calculated dynamically
    wGlobal: Optional[float] = None
    wRolling: Optional[float] = None
    wRepeat: Optional[float] = None
    wDispersion: Optional[float] = None
    wLateFairness: Optional[float] = None
    globalSlack: Optional[int] = None
    rollingSlack: Optional[int] = None
    maxPasses: Optional[int] = None
    dryRun: Optional[bool] = True
    optimize_days_since: Optional[bool] = True
    force_full_validation: Optional[bool] = True

@app.get("/health")
async def health_check():
    return {"status": "healthy", "message": "Scheduler service is running"}

@app.post("/schedule")
async def generate_schedule(request: ScheduleRequest):
    """Generate a league schedule using the enhanced sophisticated algorithm"""
    print(f"🎯 Received schedule request:")
    print(f"   League ID: {request.leagueId}")
    print(f"   Run ID: {request.runId}")
    print(f"   Teams count: {len(request.teams)}")
    print(f"   Slots count: {len(request.slots)}")
    print(f"   Divisions count: {len(request.divisions)}")
    print(f"   Params: {request.params}")
    
    if request.teams:
        print(f"   Sample team: {request.teams[0]}")
    if request.slots:
        print(f"   Sample slot: {request.slots[0]}")
    
    try:
        result = generate_enhanced_schedule(
            request.slots,
            request.teams,
            request.divisions,
            request.params
        )
        print(f"✅ Schedule generation successful: {result['message']}")
        return JSONResponse(content={
            "success": True,
            "message": result["message"],
            "schedule": result["schedule"],
            "kpis": result["kpis"],
            "runId": request.runId
        })
    except Exception as e:
        print(f"❌ Schedule generation failed: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/optimize")
async def optimize_schedule(request: OptimizationRequest):
    """Optimize an existing schedule using the real optimization algorithms"""
    print(f"🔧 Received optimization request:")
    print(f"   Schedule games: {len(request.schedule)}")
    print(f"   Target week: {request.target_week}")
    print(f"   Block size: {request.blockSize}")
    print(f"   Early start: {request.earlyStart}")
    print(f"   Mid start: {request.midStart}")
    
    try:
        # Calculate dynamic parameters based on schedule data
        all_teams = set()
        for game in request.schedule:
            home_team = game.get('home', '') or game.get('HomeTeam', '')
            away_team = game.get('away', '') or game.get('AwayTeam', '')
            if home_team: all_teams.add(home_team)
            if away_team: all_teams.add(away_team)
        
        team_count = len(all_teams)
        print(f"🔧 Detected {team_count} teams in schedule")
        
        # Calculate dynamic defaults
        block_size = request.blockSize
        if block_size is None:
            block_size = max(4, min(20, team_count // 2))
            print(f"🔧 Calculated dynamic block size: {block_size}")
        
        early_start = request.earlyStart
        mid_start = request.midStart
        if early_start is None or mid_start is None:
            # Default to 10:01 PM and 10:31 PM for late game classification
            early_start = early_start or "10:01 PM"
            mid_start = mid_start or "10:31 PM"
            print(f"🔧 Using default EML times: {early_start}, {mid_start}")
        
        default_game_minutes = request.defaultGameMinutes
        if default_game_minutes is None:
            # Dynamic game duration based on team count
            if team_count <= 8:
                default_game_minutes = 60  # Shorter games for smaller leagues
            elif team_count <= 16:
                default_game_minutes = 80  # Standard games
            else:
                default_game_minutes = 90  # Longer games for large leagues
            print(f"🔧 Calculated dynamic game duration: {default_game_minutes} minutes")
        
        # Calculate dynamic weights based on team count
        weights = request.weights
        if weights is None:
            # More teams = higher emphasis on fairness and distribution
            base_weight = 1.0
            if team_count > 16:
                base_weight = 1.5
            elif team_count > 12:
                base_weight = 1.2
            
            weights = {
                "w_eml": base_weight,
                "w_runs": 0.2 * base_weight,
                "w_rest": 0.6 * base_weight
            }
            print(f"🔧 Calculated dynamic weights: {weights}")
        
        # Convert the request to the format expected by optimize_from_dict
        optimization_params = {
            'blockSize': block_size,
            'midStart': mid_start,
            'target_week': request.target_week,
            'optimize_days_since': request.optimize_days_since,
            'force_full_validation': request.force_full_validation,
            'defaultGameMinutes': default_game_minutes,
            'weights': weights
        }
        
        # Call the real optimization function
        print(f"🔧 Calling optimize_from_dict with {len(request.schedule)} games")
        result = optimize_from_dict(request.schedule, None, optimization_params)
        
        print(f"✅ Optimization successful: {result}")
        
        # Return the result in the format expected by your Next.js app
        return JSONResponse(content=result)
        
    except Exception as e:
        print(f"❌ Optimization failed: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
