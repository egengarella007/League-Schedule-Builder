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

# Import only the enhanced scheduler (remove optimization imports)
from enhanced_scheduler import generate_enhanced_schedule

app = FastAPI(title="League Scheduler API", version="1.0.0")

class ScheduleRequest(BaseModel):
    leagueId: str
    runId: Optional[str] = None
    params: Dict[str, Any]
    slots: List[Dict[str, Any]]
    teams: List[Dict[str, Any]]
    divisions: List[Dict[str, Any]]

@app.get("/")
async def root():
    return {"message": "League Scheduler API is running", "version": "1.0.0"}

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
