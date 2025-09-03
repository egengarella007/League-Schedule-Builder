"""
Streamlit web interface for the league scheduler.
"""

import streamlit as st
import pandas as pd
import yaml
import tempfile
import os
from pathlib import Path
import sys
from datetime import datetime

# Add the scheduler package to the path
sys.path.append(str(Path(__file__).parent.parent))

from scheduler.config import SchedulerConfig, load_config, save_config
from scheduler.ingest import load_slots, create_teams_from_config, validate_slots, get_slot_summary
from scheduler.matchups import build_matchups, get_matchup_summary
from scheduler.engine import schedule, validate_schedule
from scheduler.passes import cap_fix, smooth_gaps, balance_weekdays, balance_home_away
from scheduler.export import write_excel


def main():
    st.set_page_config(
        page_title="League Scheduler",
        page_icon="🏈",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    st.title("🏈 League Scheduler")
    
    # Initialize session state
    if 'slots' not in st.session_state:
        st.session_state.slots = []
    if 'divisions' not in st.session_state:
        st.session_state.divisions = []
    if 'config' not in st.session_state:
        # Load default config
        sample_config_path = Path(__file__).parent.parent / "configs" / "sample_league.yaml"
        with open(sample_config_path, 'r') as f:
            config_content = f.read()
        config_data = yaml.safe_load(config_content)
        st.session_state.config = SchedulerConfig(**config_data)
    
    # Create tabs
    tab1, tab2, tab3 = st.tabs(["📥 Import", "🏆 Teams", "📅 Schedule"])
    
    # Import Tab
    with tab1:
        st.header("📥 Import Data")
        
        # File format instructions
        with st.expander("📋 Expected File Format", expanded=True):
            st.markdown("""
            **Your Excel file should have the following structure:**
            
            | Event Start | Event End | Resource |
            |-------------|-----------|----------|
            | 9/6/25 9:00 PM | 9/6/25 10:20 PM | GPI - Rink 4 |
            | 9/6/25 10:30 PM | 9/6/25 11:50 PM | GPI - Rink 1 |
            | 9/7/25 8:00 PM | 9/7/25 9:20 PM | GPI - Rink 2 |
            
            **Note:** Each row represents one available time slot. The scheduler will use all rows in the file.
            """)
        
        # Upload button
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            if st.button("📁 Upload XLS File", type="primary", use_container_width=True):
                st.session_state.show_file_uploader = True
        
        # File uploader
        if st.session_state.get('show_file_uploader', False):
            uploaded_file = st.file_uploader(
                "Select Excel file with time slots",
                type=['xlsx', 'xls'],
                key="file_uploader"
            )
            if uploaded_file:
                st.session_state.uploaded_file = uploaded_file
                st.session_state.show_file_uploader = False
                st.rerun()
        
        # Show uploaded file info and content
        if hasattr(st.session_state, 'uploaded_file') and st.session_state.uploaded_file:
            st.success(f"✅ File uploaded: {st.session_state.uploaded_file.name}")
            
            # Load and display slots
            with st.spinner("Loading time slots..."):
                try:
                    # Save uploaded file temporarily
                    with tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx') as tmp_file:
                        tmp_file.write(st.session_state.uploaded_file.getvalue())
                        tmp_path = tmp_file.name
                    
                    # Load slots
                    slots = load_slots(tmp_path, st.session_state.config)
                    os.unlink(tmp_path)  # Clean up
                    
                    if slots:
                        st.success(f"✅ Loaded {len(slots)} time slots")
                        
                        # Convert slots to DataFrame for display
                        slot_data = []
                        for slot in slots:
                            slot_data.append({
                                'Date': slot.start_time.strftime('%Y-%m-%d'),
                                'Time': slot.start_time.strftime('%H:%M'),
                                'End Time': slot.end_time.strftime('%H:%M'),
                                'Resource': slot.resource,
                                'Duration (hrs)': round((slot.end_time - slot.start_time).total_seconds() / 3600, 1),
                                'Weekday': slot.start_time.strftime('%A'),
                                'E/M/L': slot.eml_category.value
                            })
                        
                        df = pd.DataFrame(slot_data)
                        
                        # Summary metrics
                        col1, col2, col3, col4 = st.columns(4)
                        with col1:
                            st.metric("Total Slots", len(slots))
                        with col2:
                            st.metric("Date Range", f"{df['Date'].min()} to {df['Date'].max()}")
                        with col3:
                            st.metric("Avg Duration", f"{df['Duration (hrs)'].mean():.1f} hrs")
                        with col4:
                            st.metric("Total Hours", f"{df['Duration (hrs)'].sum():.0f}")
                        
                        # Display table
                        st.subheader("📊 Available Time Slots")
                        st.dataframe(df, use_container_width=True)
                        
                    else:
                        st.error("No valid slots found in the uploaded file")
                        st.info("Make sure your file has the correct format with Event Start, Event End, and Resource columns")
                        
                except Exception as e:
                    st.error(f"❌ Error loading slots: {e}")
                    if "Missing required columns" in str(e):
                        st.info("💡 Make sure your Excel file has columns named: Event Start, Event End, and Resource")
                    elif "Could not parse" in str(e):
                        st.info("💡 Check that your date/time format is correct (e.g., 9/6/25 9:00 PM)")
        else:
            st.info("👈 Please upload an Excel file to see the available time slots")
    
    # Teams Tab
    with tab2:
        st.header("🏆 Teams & Divisions")
        
        # Add Sub Division button
        if st.button("➕ Add Sub Division", type="primary"):
            if 'divisions' not in st.session_state:
                st.session_state.divisions = []
            st.session_state.divisions.append({
                'name': f'Sub Division {len(st.session_state.divisions) + 1}',
                'teams': []
            })
            st.rerun()
        
        # Display divisions and teams
        if st.session_state.divisions:
            for i, division in enumerate(st.session_state.divisions):
                with st.expander(f"🏆 {division['name']}", expanded=True):
                    # Add team button for this division
                    if st.button(f"➕ Add Team", key=f"add_team_{i}"):
                        team_name = f"Team {len(division['teams']) + 1}"
                        division['teams'].append(team_name)
                        st.rerun()
                    
                    # Display teams in this division
                    if division['teams']:
                        for j, team in enumerate(division['teams']):
                            col1, col2 = st.columns([3, 1])
                            with col1:
                                st.write(f"• {team}")
                            with col2:
                                if st.button("❌", key=f"remove_team_{i}_{j}"):
                                    division['teams'].pop(j)
                                    st.rerun()
        else:
            st.info("👈 Click 'Add Sub Division' to start building your league structure")
    
    # Schedule Tab
    with tab3:
        st.header("📅 Schedule")
        
        if hasattr(st.session_state, 'uploaded_file') and st.session_state.uploaded_file:
            if st.session_state.divisions:
                st.info("✅ Ready to generate schedule! Add a 'Run Schedule' button here.")
                st.write("This tab will show the final schedule once teams are added and the schedule is generated.")
            else:
                st.info("👈 Go to the Teams tab to add divisions and teams first")
        else:
            st.info("👈 Go to the Import tab to upload your Excel file first")


if __name__ == "__main__":
    main()
