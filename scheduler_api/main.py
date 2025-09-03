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

# Import the enhanced scheduler and optimizers
from enhanced_scheduler import generate_enhanced_schedule
from schedule_optimizer import optimize_from_dict
from days_since_optimizer import optimize_days_since_last_played

app = FastAPI(title="League Scheduler API", version="1.0.0")

@app.get("/")
async def root():
    return {"message": "League Scheduler API is running", "version": "1.0.0"}

@app.get("/health")
async def health_check():
    return {"status": "healthy", "message": "Scheduler service is running"}

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
    dryRun: Optional[bool] = False
    optimize_days_since: Optional[bool] = True
    force_full_validation: Optional[bool] = True

class DaysOptimizationRequest(BaseModel):
    schedule_data: Dict[str, Any]
    late_threshold: Optional[str] = "22:31"

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
    """Optimize an existing schedule using the schedule optimizer"""
    print(f"🔧 Received optimization request:")
    print(f"   Schedule games: {len(request.schedule)}")
    print(f"   Target week: {request.target_week}")
    print(f"   Block size: {request.blockSize}")
    print(f"   Early start: {request.earlyStart}")
    print(f"   Mid start: {request.midStart}")
    
    try:
        # Convert request to dict for the optimizer
        params = {
            'blockSize': request.blockSize,
            'earlyStart': request.earlyStart,
            'midStart': request.midStart,
            'target_week': request.target_week,
            'defaultGameMinutes': request.defaultGameMinutes,
            'weights': request.weights,
            'wGlobal': request.wGlobal,
            'wRolling': request.wRolling,
            'wRepeat': request.wRepeat,
            'wDispersion': request.wDispersion,
            'wLateFairness': request.wLateFairness,
            'globalSlack': request.globalSlack,
            'rollingSlack': request.rollingSlack,
            'maxPasses': request.maxPasses,
            'dryRun': request.dryRun,
            'optimize_days_since': request.optimize_days_since,
            'force_full_validation': request.force_full_validation
        }
        
        # Run optimization
        result = optimize_from_dict(request.schedule, None, params)
        
        print(f"✅ Optimization completed successfully")
        return JSONResponse(content=result)
        
    except Exception as e:
        print(f"❌ Optimization failed: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/days-optimize")
async def optimize_days_since(request: DaysOptimizationRequest):
    """Optimize schedule based on days since last played"""
    print(f"🚀 Received days optimization request:")
    print(f"   Schedule buckets: {len(request.schedule_data.get('buckets', []))}")
    print(f"   Late threshold: {request.late_threshold}")
    
    try:
        from datetime import time
        
        # Parse late threshold
        late_hours, late_minutes = map(int, request.late_threshold.split(':'))
        late_threshold = time(late_hours, late_minutes)
        
        # Run days optimization
        optimized_schedule, changes = optimize_days_since_last_played(
            request.schedule_data, 
            late_threshold=late_threshold
        )
        
        result = {
            'success': True,
            'optimized_schedule': optimized_schedule,
            'changes_made': changes,
            'total_changes': len(changes)
        }
        
        print(f"✅ Days optimization completed: {len(changes)} changes made")
        return JSONResponse(content=result)
        
    except Exception as e:
        print(f"❌ Days optimization failed: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
