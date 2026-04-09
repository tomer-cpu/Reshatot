#!/usr/bin/env python3
"""
Scheduler for daily price data fetching.

Supports three modes:
1. schedule library - lightweight Python-based scheduler (default)
2. systemd - generates a systemd timer unit
3. crontab - prints crontab line for manual setup

Usage:
    python scheduler.py                         # Run scheduler (default: daily at 06:00)
    python scheduler.py --time 08:30            # Run daily at 08:30
    python scheduler.py --interval 12           # Run every 12 hours
    python scheduler.py --install-cron          # Install as crontab entry
    python scheduler.py --install-systemd       # Generate systemd timer files
    python scheduler.py --run-once              # Run once immediately then exit
"""

import argparse
import json
import logging
import os
import subprocess
import sys
import time
from datetime import datetime, date

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
STATUS_FILE = os.path.join(PROJECT_DIR, "data", ".fetch_status.json")


def load_status():
    """Load the last fetch status from disk."""
    if os.path.exists(STATUS_FILE):
        with open(STATUS_FILE, "r") as f:
            return json.load(f)
    return {}


def save_status(status):
    """Save fetch status to disk."""
    os.makedirs(os.path.dirname(STATUS_FILE), exist_ok=True)
    with open(STATUS_FILE, "w") as f:
        json.dump(status, f, indent=2, ensure_ascii=False)


def run_fetch_job(output_dir="data", chain_filter=None):
    """Execute a fetch job and record results."""
    from main import run_fetch, get_all_chains, create_scraper

    logger.info(f"{'='*60}")
    logger.info(f"  Starting scheduled fetch - {datetime.now()}")
    logger.info(f"{'='*60}")

    start_time = datetime.now()

    # Run the actual fetch
    run_fetch(chain_filter=chain_filter, output_dir=output_dir)

    # Import into SQLite
    logger.info("Importing data into SQLite...")
    from database import Database
    db = Database()
    db.import_data_dir(output_dir)
    db.close()

    # Verify freshness of downloaded data
    chains = get_all_chains()
    if chain_filter:
        filter_lower = chain_filter.lower()
        chains = [
            c for c in chains
            if filter_lower in c["name"].lower() or filter_lower in c.get("name_he", "")
        ]

    freshness_report = []
    for chain_config in chains:
        scraper = create_scraper(chain_config, output_dir)
        if scraper:
            result = scraper.verify_freshness()
            freshness_report.append(result)

    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()

    # Build status report
    status = {
        "last_run": end_time.isoformat(),
        "duration_seconds": round(duration, 1),
        "date": str(date.today()),
        "chains": {},
    }

    fresh_total = 0
    stale_total = 0
    no_data_total = 0

    for report in freshness_report:
        chain_name = report["chain"]
        status["chains"][chain_name] = {
            "status": report["status"],
            "total_files": report["total_files"],
            "fresh": report.get("fresh", 0),
            "stale": report.get("stale", 0),
        }
        if report["status"] == "fresh":
            fresh_total += 1
        elif report["status"] == "stale":
            stale_total += 1
        else:
            no_data_total += 1

    status["summary"] = {
        "total_chains": len(freshness_report),
        "fresh": fresh_total,
        "stale": stale_total,
        "no_data_or_unknown": no_data_total,
    }

    save_status(status)

    # Print freshness report
    print(f"\n{'='*60}")
    print(f"  Freshness Report - {date.today()}")
    print(f"{'='*60}")
    print(f"  {'Chain':<30} {'Status':<10} {'Fresh':<8} {'Stale':<8} {'Files':<8}")
    print(f"  {'-'*30} {'-'*10} {'-'*8} {'-'*8} {'-'*8}")
    for report in freshness_report:
        icon = "V" if report["status"] == "fresh" else "X" if report["status"] == "stale" else "?"
        print(
            f"  {report['chain']:<30} {icon:<10} "
            f"{report.get('fresh', 0):<8} {report.get('stale', 0):<8} "
            f"{report['total_files']:<8}"
        )
    print(f"\n  Duration: {duration:.1f}s")
    print(f"  Fresh chains: {fresh_total}/{len(freshness_report)}")
    if stale_total:
        print(f"  WARNING: {stale_total} chains have stale (not today's) data!")
    print()

    return status


def run_scheduler(run_time="06:00", interval_hours=None, chain_filter=None, output_dir="data"):
    """Run the scheduler loop using the schedule library."""
    import schedule

    def job():
        run_fetch_job(output_dir=output_dir, chain_filter=chain_filter)

    if interval_hours:
        schedule.every(interval_hours).hours.do(job)
        logger.info(f"Scheduled: every {interval_hours} hours")
    else:
        schedule.every().day.at(run_time).do(job)
        logger.info(f"Scheduled: daily at {run_time}")

    logger.info("Scheduler started. Press Ctrl+C to stop.")
    logger.info(f"Next run: {schedule.next_run()}")

    try:
        while True:
            schedule.run_pending()
            time.sleep(60)
    except KeyboardInterrupt:
        logger.info("Scheduler stopped.")


def install_cron(run_time="06:00", chain_filter=None, output_dir="data"):
    """Print crontab entry for daily fetch."""
    hour, minute = run_time.split(":")
    python = sys.executable
    script = os.path.join(PROJECT_DIR, "scheduler.py")
    args = f"--run-once --output {output_dir}"
    if chain_filter:
        args += f' --chain "{chain_filter}"'

    cron_line = f"{minute} {hour} * * * cd {PROJECT_DIR} && {python} {script} {args} >> {PROJECT_DIR}/data/cron.log 2>&1"

    print(f"\nAdd this line to your crontab (run 'crontab -e'):\n")
    print(f"  {cron_line}")
    print(f"\nOr install automatically:")
    print(f"  (crontab -l 2>/dev/null; echo '{cron_line}') | crontab -")
    print()


def install_systemd(run_time="06:00", chain_filter=None, output_dir="data"):
    """Generate systemd service and timer files."""
    python = sys.executable
    script = os.path.join(PROJECT_DIR, "scheduler.py")
    args = f"--run-once --output {output_dir}"
    if chain_filter:
        args += f' --chain "{chain_filter}"'

    service_content = f"""[Unit]
Description=Israeli Supermarket Price Data Fetcher
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
WorkingDirectory={PROJECT_DIR}
ExecStart={python} {script} {args}
StandardOutput=append:{PROJECT_DIR}/data/systemd.log
StandardError=append:{PROJECT_DIR}/data/systemd.log

[Install]
WantedBy=multi-user.target
"""

    timer_content = f"""[Unit]
Description=Daily Israeli supermarket price data fetch

[Timer]
OnCalendar=*-*-* {run_time}:00
Persistent=true

[Install]
WantedBy=timers.target
"""

    service_path = os.path.expanduser("~/.config/systemd/user/reshatot-fetch.service")
    timer_path = os.path.expanduser("~/.config/systemd/user/reshatot-fetch.timer")

    os.makedirs(os.path.dirname(service_path), exist_ok=True)

    with open(service_path, "w") as f:
        f.write(service_content)
    with open(timer_path, "w") as f:
        f.write(timer_content)

    print(f"\nSystemd files created:")
    print(f"  Service: {service_path}")
    print(f"  Timer:   {timer_path}")
    print(f"\nTo enable:")
    print(f"  systemctl --user daemon-reload")
    print(f"  systemctl --user enable --now reshatot-fetch.timer")
    print(f"\nTo check status:")
    print(f"  systemctl --user status reshatot-fetch.timer")
    print(f"  systemctl --user list-timers")
    print()


def show_status():
    """Display the last fetch status."""
    status = load_status()
    if not status:
        print("No fetch history found. Run a fetch first.")
        return

    print(f"\n{'='*60}")
    print(f"  Last Fetch Status")
    print(f"{'='*60}")
    print(f"  Last run:  {status.get('last_run', 'unknown')}")
    print(f"  Duration:  {status.get('duration_seconds', '?')}s")
    print(f"  Date:      {status.get('date', 'unknown')}")

    summary = status.get("summary", {})
    print(f"  Chains:    {summary.get('total_chains', '?')}")
    print(f"  Fresh:     {summary.get('fresh', '?')}")
    print(f"  Stale:     {summary.get('stale', '?')}")
    print(f"  No data:   {summary.get('no_data_or_unknown', '?')}")
    print()


def main():
    parser = argparse.ArgumentParser(
        description="Scheduler for daily supermarket price data fetching",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scheduler.py                      Run scheduler (daily at 06:00)
  python scheduler.py --time 08:30         Run daily at 08:30
  python scheduler.py --interval 12        Run every 12 hours
  python scheduler.py --run-once           Fetch once and exit
  python scheduler.py --install-cron       Print crontab entry
  python scheduler.py --install-systemd    Generate systemd timer
  python scheduler.py --status             Show last fetch status
        """,
    )
    parser.add_argument("--time", default="06:00", help="Daily run time HH:MM (default: 06:00)")
    parser.add_argument("--interval", type=int, help="Run every N hours instead of daily")
    parser.add_argument("--chain", type=str, help="Filter by chain name")
    parser.add_argument("--output", default="data", help="Output directory (default: data)")
    parser.add_argument("--run-once", action="store_true", help="Fetch once and exit")
    parser.add_argument("--install-cron", action="store_true", help="Print crontab entry")
    parser.add_argument("--install-systemd", action="store_true", help="Generate systemd timer")
    parser.add_argument("--status", action="store_true", help="Show last fetch status")

    args = parser.parse_args()

    if args.status:
        show_status()
    elif args.install_cron:
        install_cron(args.time, args.chain, args.output)
    elif args.install_systemd:
        install_systemd(args.time, args.chain, args.output)
    elif args.run_once:
        run_fetch_job(output_dir=args.output, chain_filter=args.chain)
    else:
        run_scheduler(
            run_time=args.time,
            interval_hours=args.interval,
            chain_filter=args.chain,
            output_dir=args.output,
        )


if __name__ == "__main__":
    main()
