"""
Report path management with archive + latest pattern.

Implements the standardized report output structure:
- All reports go to <run_dir>/reports/
- Archive folder stores timestamped versions
- Latest folder contains most recent outputs
- latest.txt points to archive location (no symlinks)
"""

import os
import shutil
from datetime import datetime
from dataclasses import dataclass
from typing import Optional, Tuple


@dataclass
class ReportPaths:
    """
    Standardized paths for a report generation run.
    
    Structure:
        <run_dir>/
        ├── raw/                        # Raw simulation data
        │   ├── logs/                   # JSONL logs
        │   └── results/                # JSON results
        └── reports/
            ├── health/                 # Data quality & sanity checks
            │   ├── health_dashboard.png
        │   ├── summary.md
            │   ├── plots/
            │   └── _history/<timestamp>/
            ├── trick_strategy/         # Strategy performance analysis
            │   ├── paired/
            │   ├── head_to_head/
        │   └── _history/<timestamp>/
            ├── bidding_strategy/       # Hand evaluation & bidding
            │   └── README.md (placeholder)
            ├── dashboards/<strategy>/  # DEPRECATED: Legacy location
            │   ├── dashboard.png
            │   ├── plots/
        │   └── _history/<timestamp>/
            ├── paired/                 # DEPRECATED: Legacy location
            ├── head_to_head/           # DEPRECATED: Legacy location
            ├── summary.md
            └── manifest.json
    """
    run_dir: str
    timestamp: str
    reports_root: str
    
    # Raw data paths (with backward compatibility)
    raw_root: str
    logs_dir: str
    results_dir: str
    
    # Health dashboard paths
    health_root: str
    health_archive: str
    health_plots: str
    
    # Trick strategy paths
    trick_strategy_root: str
    trick_strategy_archive: str
    trick_strategy_paired: str
    trick_strategy_h2h: str
    
    # Bidding strategy paths
    bidding_strategy_root: str
    
    # Legacy dashboard paths (for backward compatibility)
    dashboards_root: str
    dashboards_archive: str
    
    # Legacy paired comparison paths
    paired_root: str
    paired_archive: str
    
    # Legacy head-to-head paths
    h2h_root: str
    h2h_archive: str
    h2h_matchups: str
    
    # Top-level paths
    summary_md: str
    manifest_json: str


def get_report_paths(run_dir: str, timestamp: Optional[str] = None) -> ReportPaths:
    """
    Get standardized report paths for a run.
    
    Args:
        run_dir: Base directory for the run (e.g., data/runs/<run_id>)
        timestamp: Timestamp for archiving (defaults to now)
    
    Returns:
        ReportPaths instance with all standardized paths
    """
    if timestamp is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    reports_root = os.path.join(run_dir, "reports")
    raw_root = os.path.join(run_dir, "raw")
    
    # Backward compatibility: check if raw/ exists, otherwise use legacy locations
    if os.path.exists(raw_root):
        logs_dir = os.path.join(raw_root, "logs")
        results_dir = os.path.join(raw_root, "results")
    else:
        # Legacy locations (directly under run_dir)
        logs_dir = os.path.join(run_dir, "logs")
        results_dir = os.path.join(run_dir, "results")
    
    return ReportPaths(
        run_dir=run_dir,
        timestamp=timestamp,
        reports_root=reports_root,
        
        # Raw data paths
        raw_root=raw_root,
        logs_dir=logs_dir,
        results_dir=results_dir,
        
        # Health dashboard paths
        health_root=os.path.join(reports_root, "health"),
        health_archive=os.path.join(reports_root, "_history", "health", timestamp),
        health_plots=os.path.join(reports_root, "health", "plots"),
        
        # Trick strategy paths
        trick_strategy_root=os.path.join(reports_root, "trick_strategy"),
        trick_strategy_archive=os.path.join(reports_root, "_history", "trick_strategy", timestamp),
        trick_strategy_paired=os.path.join(reports_root, "trick_strategy", "paired"),
        trick_strategy_h2h=os.path.join(reports_root, "trick_strategy", "head_to_head"),
        
        # Bidding strategy paths
        bidding_strategy_root=os.path.join(reports_root, "bidding_strategy"),
        
        # Legacy dashboard paths (for backward compatibility)
        dashboards_root=os.path.join(reports_root, "dashboards"),
        dashboards_archive=os.path.join(reports_root, "_history", "dashboards", timestamp),
        
        # Legacy paired comparison paths
        paired_root=os.path.join(reports_root, "paired"),
        paired_archive=os.path.join(reports_root, "_history", "paired", timestamp),
        
        # Legacy head-to-head paths
        h2h_root=os.path.join(reports_root, "head_to_head"),
        h2h_archive=os.path.join(reports_root, "_history", "head_to_head", timestamp),
        h2h_matchups=os.path.join(reports_root, "head_to_head", "matchups"),
        
        # Top-level paths
        summary_md=os.path.join(reports_root, "summary.md"),
        manifest_json=os.path.join(reports_root, "manifest.json"),
    )


def write_latest_pointer(latest_dir: str, archive_relative_path: str):
    """
    Write latest.txt file pointing to archive location.
    
    Args:
        latest_dir: Directory containing the latest artifacts
        archive_relative_path: Relative path from latest_dir to archive
    """
    os.makedirs(latest_dir, exist_ok=True)
    latest_txt = os.path.join(latest_dir, "latest.txt")
    
    with open(latest_txt, "w") as f:
        f.write(f"# Latest report generated at: {datetime.now().isoformat()}\n")
        f.write(f"# Archive location (relative): {archive_relative_path}\n")
        f.write(f"{archive_relative_path}\n")


def copy_to_latest(archive_path: str, latest_path: str, is_dir: bool = False):
    """
    Copy archive artifacts to latest location.
    
    Args:
        archive_path: Source path (in archive)
        latest_path: Destination path (latest location)
        is_dir: True if copying a directory, False for file
    """
    os.makedirs(os.path.dirname(latest_path), exist_ok=True)
    
    if is_dir:
        # Remove existing directory if present
        if os.path.exists(latest_path):
            shutil.rmtree(latest_path)
        shutil.copytree(archive_path, latest_path)
    else:
        shutil.copy2(archive_path, latest_path)


def ensure_dir(path: str):
    """Ensure directory exists."""
    os.makedirs(path, exist_ok=True)


def dashboard_paths(
    paths: ReportPaths,
    strategy: str
) -> Tuple[str, str, str]:
    """
    Get paths for a strategy dashboard.
    
    Returns:
        (archive_dir, latest_dir, latest_txt_path)
    """
    archive_dir = os.path.join(paths.dashboards_archive, strategy)
    latest_dir = os.path.join(paths.dashboards_root, strategy)
    latest_txt = os.path.join(latest_dir, "latest.txt")
    
    return archive_dir, latest_dir, latest_txt


def get_data_paths(run_dir: str) -> Tuple[str, str]:
    """
    Get data paths with backward compatibility.
    
    Returns logs and results directories, checking both new (raw/) and legacy
    locations.
    
    Args:
        run_dir: Base run directory
    
    Returns:
        (logs_dir, results_dir)
    """
    paths = get_report_paths(run_dir)
    return paths.logs_dir, paths.results_dir

