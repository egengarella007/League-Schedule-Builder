"""
Tests for configuration management.
"""

import pytest
import tempfile
import yaml
from pathlib import Path
import sys

# Add the scheduler package to the path
sys.path.append(str(Path(__file__).parent.parent))

from scheduler.config import SchedulerConfig, load_config, save_config


def test_basic_config_creation():
    """Test creating a basic configuration."""
    config_data = {
        "timezone": "America/Chicago",
        "slot_type_filter": ["Game Rental"],
        "columns": {
            "type": "Type",
            "start": "Event Start",
            "end": "Event End",
            "resource": "Resource"
        },
        "divisions": [
            {
                "name": "North",
                "sub_divisions": [
                    {
                        "name": "12-Team",
                        "teams": ["Team 1", "Team 2", "Team 3"]
                    }
                ]
            }
        ]
    }
    
    config = SchedulerConfig(**config_data)
    
    assert config.timezone == "America/Chicago"
    assert config.slot_type_filter == ["Game Rental"]
    assert len(config.divisions) == 1
    assert len(config.divisions[0].sub_divisions) == 1
    assert len(config.divisions[0].sub_divisions[0].teams) == 3


def test_config_validation():
    """Test configuration validation."""
    # Test invalid timezone
    with pytest.raises(ValueError, match="Unknown timezone"):
        SchedulerConfig(
            timezone="Invalid/Timezone",
            columns={"type": "Type", "start": "Start", "end": "End", "resource": "Resource"},
            divisions=[]
        )
    
    # Test invalid weekday
    with pytest.raises(ValueError, match="Invalid weekday"):
        SchedulerConfig(
            timezone="America/Chicago",
            columns={"type": "Type", "start": "Start", "end": "End", "resource": "Resource"},
            divisions=[],
            weekday_balance_prefer=["InvalidDay"]
        )


def test_config_load_save():
    """Test loading and saving configuration."""
    config_data = {
        "timezone": "America/Chicago",
        "slot_type_filter": ["Game Rental"],
        "columns": {
            "type": "Type",
            "start": "Event Start",
            "end": "Event End",
            "resource": "Resource"
        },
        "divisions": [
            {
                "name": "North",
                "sub_divisions": [
                    {
                        "name": "12-Team",
                        "teams": ["Team 1", "Team 2"]
                    }
                ]
            }
        ]
    }
    
    # Create temporary file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        yaml.dump(config_data, f)
        temp_path = f.name
    
    try:
        # Load configuration
        loaded_config = load_config(temp_path)
        
        # Verify loaded config matches original
        assert loaded_config.timezone == config_data["timezone"]
        assert loaded_config.slot_type_filter == config_data["slot_type_filter"]
        assert len(loaded_config.divisions) == len(config_data["divisions"])
        
        # Test saving configuration
        save_path = temp_path.replace('.yaml', '_saved.yaml')
        save_config(loaded_config, save_path)
        
        # Load saved configuration
        saved_config = load_config(save_path)
        assert saved_config.timezone == loaded_config.timezone
        
    finally:
        # Clean up
        import os
        if os.path.exists(temp_path):
            os.unlink(temp_path)
        if os.path.exists(save_path):
            os.unlink(save_path)


def test_get_all_teams():
    """Test getting all teams from configuration."""
    config_data = {
        "timezone": "America/Chicago",
        "columns": {"type": "Type", "start": "Start", "end": "End", "resource": "Resource"},
        "divisions": [
            {
                "name": "North",
                "sub_divisions": [
                    {"name": "A", "teams": ["Team 1", "Team 2"]},
                    {"name": "B", "teams": ["Team 3", "Team 4"]}
                ]
            },
            {
                "name": "South",
                "sub_divisions": [
                    {"name": "C", "teams": ["Team 5"]}
                ]
            }
        ]
    }
    
    config = SchedulerConfig(**config_data)
    all_teams = config.get_all_teams()
    
    assert len(all_teams) == 5
    assert "Team 1" in all_teams
    assert "Team 5" in all_teams


def test_get_team_division():
    """Test getting team division."""
    config_data = {
        "timezone": "America/Chicago",
        "columns": {"type": "Type", "start": "Start", "end": "End", "resource": "Resource"},
        "divisions": [
            {
                "name": "North",
                "sub_divisions": [
                    {"name": "A", "teams": ["Team 1", "Team 2"]}
                ]
            },
            {
                "name": "South",
                "sub_divisions": [
                    {"name": "B", "teams": ["Team 3"]}
                ]
            }
        ]
    }
    
    config = SchedulerConfig(**config_data)
    
    assert config.get_team_division("Team 1") == "North"
    assert config.get_team_division("Team 3") == "South"
    assert config.get_team_division("Unknown Team") is None
