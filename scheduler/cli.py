"""
Command-line interface for the league scheduler.
"""

import argparse
import sys
import yaml
from pathlib import Path
from .config import SchedulerConfig, load_config
from .ingest import load_slots, create_teams_from_config
from .matchups import build_matchups
from .engine import schedule, validate_schedule
from .passes import cap_fix, smooth_gaps, balance_weekdays, balance_home_away
from .export import write_excel


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="League Scheduler - Production-quality scheduling engine"
    )
    
    parser.add_argument(
        "--slots", 
        required=True,
        help="Path to Excel file with available time slots"
    )
    
    parser.add_argument(
        "--config", 
        required=True,
        help="Path to YAML configuration file"
    )
    
    parser.add_argument(
        "--out", 
        required=True,
        help="Path to output Excel file"
    )
    
    parser.add_argument(
        "--matchups",
        help="Path to Excel file with pre-defined matchups (optional)"
    )
    
    parser.add_argument(
        "--no-passes",
        action="store_true",
        help="Skip optimization passes"
    )
    
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Only validate the schedule without running passes"
    )
    
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose output"
    )
    
    args = parser.parse_args()
    
    try:
        # Load configuration
        print("Loading configuration...")
        config = load_config(args.config)
        
        # Load slots
        print("Loading available time slots...")
        slots = load_slots(args.slots, config)
        print(f"Loaded {len(slots)} time slots")
        
        # Create teams
        print("Creating teams...")
        teams = create_teams_from_config(config)
        print(f"Created {len(teams)} teams")
        
        # Build matchups
        print("Building matchups...")
        matchups = build_matchups(
            config=config,
            matchup_file=args.matchups,
            double_round=True,
            include_cross_division=False
        )
        print(f"Built {len(matchups)} matchups")
        
        # Run initial scheduling
        print("Running initial scheduling...")
        initial_schedule = schedule(slots, matchups, config, teams)
        print(f"Scheduled {len(initial_schedule.games)} games")
        
        # Validate initial schedule
        print("Validating initial schedule...")
        violations = validate_schedule(initial_schedule, config)
        
        if violations['errors']:
            print("ERRORS found in initial schedule:")
            for error in violations['errors']:
                print(f"  - {error}")
        
        if violations['warnings']:
            print("WARNINGS found in initial schedule:")
            for warning in violations['warnings']:
                print(f"  - {warning}")
        
        if args.validate_only:
            print("Validation complete. Exiting.")
            return
        
        # Run optimization passes
        if not args.no_passes:
            print("Running optimization passes...")
            
            # Cap fix pass
            print("\n1. Running cap fix pass...")
            schedule_after_cap = cap_fix(initial_schedule, config)
            
            # Gap smoothing pass
            print("\n2. Running gap smoothing pass...")
            schedule_after_smooth = smooth_gaps(schedule_after_cap, config)
            
            # Weekday balance pass
            print("\n3. Running weekday balance pass...")
            schedule_after_weekday = balance_weekdays(schedule_after_smooth, config)
            
            # Home/away balance pass
            print("\n4. Running home/away balance pass...")
            final_schedule = balance_home_away(schedule_after_weekday, config)
        else:
            final_schedule = initial_schedule
        
        # Validate final schedule
        print("\nValidating final schedule...")
        final_violations = validate_schedule(final_schedule, config)
        
        if final_violations['errors']:
            print("ERRORS found in final schedule:")
            for error in final_violations['errors']:
                print(f"  - {error}")
        else:
            print("No errors found in final schedule!")
        
        if final_violations['warnings']:
            print("WARNINGS found in final schedule:")
            for warning in final_violations['warnings']:
                print(f"  - {warning}")
        
        # Export to Excel
        print(f"\nExporting schedule to {args.out}...")
        write_excel(final_schedule, config, args.out)
        
        # Print summary
        print("\n" + "="*50)
        print("SCHEDULING COMPLETE")
        print("="*50)
        
        stats = final_schedule.get_summary_stats()
        print(f"Total games scheduled: {stats.get('total_games', 0)}")
        print(f"Total teams: {stats.get('total_teams', 0)}")
        print(f"Date range: {stats.get('date_range', {}).get('start', 'N/A')} to {stats.get('date_range', {}).get('end', 'N/A')}")
        
        if 'eml_distribution' in stats:
            print(f"E/M/L distribution: {stats['eml_distribution']}")
        
        if 'weekday_distribution' in stats:
            print(f"Weekday distribution: {stats['weekday_distribution']}")
        
        print(f"\nSchedule exported to: {args.out}")
        
    except FileNotFoundError as e:
        print(f"ERROR: File not found: {e}")
        sys.exit(1)
    except yaml.YAMLError as e:
        print(f"ERROR: Invalid YAML configuration: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"ERROR: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
