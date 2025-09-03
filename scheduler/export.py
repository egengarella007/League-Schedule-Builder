"""
Export functionality for writing schedules to Excel.
"""

import pandas as pd
from datetime import datetime
from typing import Dict, List, Optional
from .models import Schedule, EMLCategory, Weekday
from .config import SchedulerConfig


def write_excel(schedule: Schedule, config: SchedulerConfig, output_path: str) -> None:
    """
    Write schedule to Excel file with summary sheets.
    
    Args:
        schedule: Schedule to export
        config: Scheduler configuration
        output_path: Path to output Excel file
    """
    print(f"Writing schedule to {output_path}")
    
    with pd.ExcelWriter(output_path, engine='xlsxwriter') as writer:
        # Write main schedule
        _write_final_schedule(schedule, config, writer)
        
        # Write summary sheets if requested
        if config.excel.include_summaries:
            _write_eml_spread(schedule, config, writer)
            _write_weekday_spread(schedule, config, writer)
            _write_team_summary(schedule, config, writer)
            _write_gap_analysis(schedule, config, writer)
    
    print(f"Schedule exported successfully to {output_path}")


def _write_final_schedule(schedule: Schedule, config: SchedulerConfig, writer) -> None:
    """Write the main schedule sheet."""
    df = schedule.to_dataframe()
    
    if df.empty:
        print("Warning: No games to export")
        return
    
    # Format the dataframe
    df = df.copy()
    
    # Format time columns
    df['Start Time'] = df['Start Time'].apply(lambda x: x.strftime('%I:%M %p'))
    df['End Time'] = df['End Time'].apply(lambda x: x.strftime('%I:%M %p'))
    
    # Format date column
    df['Date'] = df['Date'].apply(lambda x: x.strftime('%m/%d/%Y'))
    
    # Reorder columns for better readability
    column_order = [
        'Week', 'Order', 'Date', 'Day', 'Start Time', 'End Time', 'Resource',
        'Home Team', 'Away Team', 'Division', 'EML',
        'Days Since Home Played', 'Days Since Away Played'
    ]
    
    df = df[column_order]
    
    # Write to Excel
    sheet_name = config.excel.sheets.get('final_name', 'Final Schedule')
    df.to_excel(writer, sheet_name=sheet_name, index=False)
    
    # Get the worksheet for formatting
    worksheet = writer.sheets[sheet_name]
    workbook = writer.book
    
    # Add formatting
    _format_schedule_worksheet(worksheet, workbook, df)


def _write_eml_spread(schedule: Schedule, config: SchedulerConfig, writer) -> None:
    """Write E/M/L distribution summary."""
    sheet_name = config.excel.sheets.get('eml_spread', 'E-M-L Spread')
    
    # Calculate E/M/L distribution by team
    eml_data = []
    for team_name, team in schedule.teams.items():
        eml_data.append({
            'Team': team_name,
            'Division': team.division,
            'Early': team.eml_counts.get(EMLCategory.EARLY, 0),
            'Mid': team.eml_counts.get(EMLCategory.MID, 0),
            'Late': team.eml_counts.get(EMLCategory.LATE, 0),
            'Total': team.games_played,
            'Balance Score': team.get_eml_balance_score()
        })
    
    df = pd.DataFrame(eml_data)
    df = df.sort_values(['Division', 'Team'])
    
    df.to_excel(writer, sheet_name=sheet_name, index=False)
    
    # Add summary statistics
    worksheet = writer.sheets[sheet_name]
    workbook = writer.book
    
    # Add summary at the bottom
    summary_row = len(df) + 3
    worksheet.write(summary_row, 0, 'Summary Statistics')
    worksheet.write(summary_row + 1, 0, f'Average Balance Score: {df["Balance Score"].mean():.2f}')
    worksheet.write(summary_row + 2, 0, f'Teams with Perfect Balance: {(df["Balance Score"] == 0).sum()}')


def _write_weekday_spread(schedule: Schedule, config: SchedulerConfig, writer) -> None:
    """Write weekday distribution summary."""
    sheet_name = config.excel.sheets.get('weekday_spread', 'Weekday Spread')
    
    # Calculate weekday distribution by team
    weekday_data = []
    for team_name, team in schedule.teams.items():
        team_games = schedule.get_team_schedule(team_name)
        weekday_counts = {weekday.value: 0 for weekday in Weekday}
        
        for game in team_games:
            weekday = game.slot.weekday.value
            weekday_counts[weekday] += 1
        
        row_data = {'Team': team_name, 'Division': team.division}
        row_data.update(weekday_counts)
        weekday_data.append(row_data)
    
    df = pd.DataFrame(weekday_data)
    df = df.sort_values(['Division', 'Team'])
    
    df.to_excel(writer, sheet_name=sheet_name, index=False)
    
    # Add summary statistics
    worksheet = writer.sheets[sheet_name]
    workbook = writer.book
    
    # Calculate overall weekday distribution
    overall_weekdays = {weekday.value: 0 for weekday in Weekday}
    for game in schedule.games:
        weekday = game.slot.weekday.value
        overall_weekdays[weekday] += 1
    
    summary_row = len(df) + 3
    worksheet.write(summary_row, 0, 'Overall Weekday Distribution')
    for i, (weekday, count) in enumerate(overall_weekdays.items()):
        worksheet.write(summary_row + 1, i + 2, weekday)
        worksheet.write(summary_row + 2, i + 2, count)


def _write_team_summary(schedule: Schedule, config: SchedulerConfig, writer) -> None:
    """Write team summary statistics."""
    sheet_name = 'Team Summary'
    
    # Calculate team statistics
    team_data = []
    for team_name, team in schedule.teams.items():
        team_games = schedule.get_team_schedule(team_name)
        team_games.sort(key=lambda x: x.scheduled_date)
        
        # Calculate gaps
        gaps = []
        for i in range(len(team_games) - 1):
            gap = (team_games[i + 1].scheduled_date.date() - 
                   team_games[i].scheduled_date.date()).days
            gaps.append(gap)
        
        avg_gap = sum(gaps) / len(gaps) if gaps else 0
        max_gap = max(gaps) if gaps else 0
        min_gap = min(gaps) if gaps else 0
        
        team_data.append({
            'Team': team_name,
            'Division': team.division,
            'Games Played': team.games_played,
            'Home Games': team.home_count,
            'Away Games': team.away_count,
            'Home/Away Balance': team.get_home_away_balance(),
            'EML Balance Score': team.get_eml_balance_score(),
            'Average Gap': avg_gap,
            'Max Gap': max_gap,
            'Min Gap': min_gap,
            'First Game': team_games[0].scheduled_date.date() if team_games else None,
            'Last Game': team_games[-1].scheduled_date.date() if team_games else None
        })
    
    df = pd.DataFrame(team_data)
    df = df.sort_values(['Division', 'Team'])
    
    # Format date columns
    df['First Game'] = df['First Game'].apply(lambda x: x.strftime('%m/%d/%Y') if x else '')
    df['Last Game'] = df['Last Game'].apply(lambda x: x.strftime('%m/%d/%Y') if x else '')
    
    df.to_excel(writer, sheet_name=sheet_name, index=False)


def _write_gap_analysis(schedule: Schedule, config: SchedulerConfig, writer) -> None:
    """Write gap analysis summary."""
    sheet_name = 'Gap Analysis'
    
    # Collect all gaps
    all_gaps = []
    gap_details = []
    
    for team_name, team in schedule.teams.items():
        team_games = schedule.get_team_schedule(team_name)
        team_games.sort(key=lambda x: x.scheduled_date)
        
        for i in range(len(team_games) - 1):
            gap = (team_games[i + 1].scheduled_date.date() - 
                   team_games[i].scheduled_date.date()).days
            all_gaps.append(gap)
            
            gap_details.append({
                'Team': team_name,
                'Division': team.division,
                'Gap': gap,
                'Game 1': team_games[i].scheduled_date.date(),
                'Game 2': team_games[i + 1].scheduled_date.date(),
                'Violation': gap > config.max_gap_days
            })
    
    if not all_gaps:
        return
    
    # Create gap statistics
    gap_stats = {
        'Total Gaps': len(all_gaps),
        'Average Gap': sum(all_gaps) / len(all_gaps),
        'Min Gap': min(all_gaps),
        'Max Gap': max(all_gaps),
        'Gaps > Max': sum(1 for gap in all_gaps if gap > config.max_gap_days),
        'Gaps < Min Rest': sum(1 for gap in all_gaps if gap < config.rest_min_days),
        'Target Gap': config.target_gap_days,
        'Max Gap Limit': config.max_gap_days,
        'Min Rest Days': config.rest_min_days
    }
    
    # Write gap statistics
    stats_df = pd.DataFrame([gap_stats])
    stats_df.to_excel(writer, sheet_name=sheet_name, index=False)
    
    # Write gap details
    details_df = pd.DataFrame(gap_details)
    details_df = details_df.sort_values(['Team', 'Game 1'])
    
    # Format date columns
    details_df['Game 1'] = details_df['Game 1'].apply(lambda x: x.strftime('%m/%d/%Y'))
    details_df['Game 2'] = details_df['Game 2'].apply(lambda x: x.strftime('%m/%d/%Y'))
    
    details_df.to_excel(writer, sheet_name=sheet_name, startrow=len(stats_df) + 3, index=False)


def _format_schedule_worksheet(worksheet, workbook, df: pd.DataFrame) -> None:
    """Apply formatting to the schedule worksheet."""
    # Define formats
    header_format = workbook.add_format({
        'bold': True,
        'text_wrap': True,
        'valign': 'top',
        'fg_color': '#D7E4BC',
        'border': 1
    })
    
    date_format = workbook.add_format({'num_format': 'mm/dd/yyyy'})
    time_format = workbook.add_format({'num_format': 'hh:mm AM/PM'})
    
    # Set column widths
    column_widths = {
        'Week': 6,
        'Order': 6,
        'Date': 12,
        'Day': 10,
        'Start Time': 10,
        'End Time': 10,
        'Resource': 15,
        'Home Team': 20,
        'Away Team': 20,
        'Division': 15,
        'EML': 5,
        'Days Since Home Played': 18,
        'Days Since Away Played': 18
    }
    
    for i, col in enumerate(df.columns):
        worksheet.set_column(i, i, column_widths.get(col, 12))
    
    # Apply header format
    for col_num, value in enumerate(df.columns.values):
        worksheet.write(0, col_num, value, header_format)
    
    # Apply conditional formatting for violations
    if 'Days Since Home Played' in df.columns:
        home_col = df.columns.get_loc('Days Since Home Played')
        worksheet.conditional_format(1, home_col, len(df), home_col, {
            'type': 'cell',
            'criteria': '>',
            'value': 12,
            'format': workbook.add_format({'bg_color': '#FFC7CE'})
        })
    
    if 'Days Since Away Played' in df.columns:
        away_col = df.columns.get_loc('Days Since Away Played')
        worksheet.conditional_format(1, away_col, len(df), away_col, {
            'type': 'cell',
            'criteria': '>',
            'value': 12,
            'format': workbook.add_format({'bg_color': '#FFC7CE'})
        })
