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
        <run_dir>/reports/
        ├── dashboards/<strategy>/
        │   ├── dashboard.png           # Latest
        │   ├── plots/                  # Latest
        │   └── _history/<timestamp>/   # Archive
        ├── paired/
        │   ├── paired_comparison.png   # Latest
        │   ├── summary.md
        │   └── _history/<timestamp>/
        ├── head_to_head/
        │   ├── comparison_matrix.png   # Latest
        │   ├── summary.md
        │   ├── matchups/               # Latest per-matchup plots
        │   └── _history/<timestamp>/
        ├── summary.md                  # Overall summary
        └── manifest.json               # What was generated
    """
    run_dir: str
    timestamp: str
    reports_root: str
    
    # Dashboard paths
    dashboards_root: str
    dashboards_archive: str
    
    # Paired comparison paths
    paired_root: str
    paired_archive: str
    
    # Head-to-head paths
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
    
    return ReportPaths(
        run_dir=run_dir,
        timestamp=timestamp,
        reports_root=reports_root,
        
        # Dashboard paths
        dashboards_root=os.path.join(reports_root, "dashboards"),
        dashboards_archive=os.path.join(reports_root, "_history", "dashboards", timestamp),
        
        # Paired comparison paths
        paired_root=os.path.join(reports_root, "paired"),
        paired_archive=os.path.join(reports_root, "_history", "paired", timestamp),
        
        # Head-to-head paths
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

