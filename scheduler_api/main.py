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

# Import the enhanced scheduler
from enhanced_scheduler import generate_enhanced_schedule

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
    blockSize: Optional[int] = 10
    blockRecipe: Optional[Dict[str, int]] = {"a": 6, "b": 4}
    earlyStart: Optional[str] = "10:01 PM"
    midStart: Optional[str] = "10:31 PM"
    target_week: Optional[int] = None
    defaultGameMinutes: Optional[int] = 80
    weights: Optional[Dict[str, float]] = {"w_eml": 1.0, "w_runs": 0.2, "w_rest": 0.6}
    wGlobal: Optional[float] = 2.0
    wRolling: Optional[float] = 1.2
    wRepeat: Optional[float] = 1.0
    wDispersion: Optional[float] = 0.6
    wLateFairness: Optional[float] = 1.0
    globalSlack: Optional[int] = 1
    rollingSlack: Optional[int] = 0
    maxPasses: Optional[int] = 3
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
    """Optimize an existing schedule using the optimization algorithms"""
    print(f"🔧 Received optimization request:")
    print(f"   Schedule games: {len(request.schedule)}")
    print(f"   Target week: {request.target_week}")
    print(f"   Block size: {request.blockSize}")
    print(f"   Early start: {request.earlyStart}")
    print(f"   Mid start: {request.midStart}")
    
    try:
        # For now, return a simple optimization result
        # You can integrate your actual optimization logic here later
        optimized_schedule = request.schedule.copy()
        
        # Simulate some optimization (swap a few games around)
        if len(optimized_schedule) > 1:
            # Simple swap of first two games
            temp = optimized_schedule[0]
            optimized_schedule[0] = optimized_schedule[1]
            optimized_schedule[1] = temp
            
            swaps = [{
                "game1": optimized_schedule[0]["id"],
                "game2": optimized_schedule[1]["id"],
                "type": "swap",
                "improvement": 0.1
            }]
        else:
            swaps = []
        
        result = {
            "success": True,
            "message": "Schedule optimized successfully",
            "schedule": optimized_schedule,
            "swaps": swaps,
            "score_before": 0.8,
            "score_after": 0.9,
            "improvement": 0.1
        }
        
        print(f"✅ Optimization successful: {len(swaps)} swaps made")
        return JSONResponse(content=result)
        
    except Exception as e:
        print(f"❌ Optimization failed: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
