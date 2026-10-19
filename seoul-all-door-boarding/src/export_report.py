"""Preserve a compact, traceable report alongside source code."""
import argparse
import shutil
from pathlib import Path

import pandas as pd

from .common import ROOT, digest, write_json


def export_report(run, destination):
    if destination.exists() and any(destination.iterdir()):
        raise FileExistsError('Use a fresh report destination')
    if not (run / 'run_manifest.json').exists():
        raise ValueError('Only completed runs can be exported')
    destination.mkdir(parents=True, exist_ok=True)
    for name in ['summary.md', 'quality_report.json', 'run_manifest.json', 'policy_costs_and_risks.csv',
                 'hourly_demand.csv', 'route_concentration.csv', 'top_cell_scenarios.csv']:
        shutil.copy2(run / name, destination / name)
    for name in ['top_stops.csv', 'peak_candidates.csv', 'pilot_candidates.csv']:
        pd.read_csv(run / name, dtype={'stop_id': str}).head(30).to_csv(destination / name, index=False)
    shutil.copytree(run / 'figures', destination / 'figures')
    write_json(destination / 'export_manifest.json', {
        'source_run': str(run.resolve()), 'top_tables_truncated_to_rows': 30,
        'files_sha256': {str(p.relative_to(destination)): digest(p) for p in sorted(destination.rglob('*')) if p.is_file()},
    })


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--run', type=Path, default=ROOT / 'outputs/baseline')
    p.add_argument('--destination', type=Path, default=ROOT / 'docs/results')
    args = p.parse_args()
    export_report(args.run, args.destination)
