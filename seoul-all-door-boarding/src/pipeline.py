"""Run from any directory: python -m src.pipeline (project on Python path)."""
import argparse
import json
import platform
from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path

import pandas as pd

from .common import ROOT, config, digest, write_json
from .collect import collect
from .preprocess import preprocess
from .eda import analyze
from .sensitivity import run_sensitivity
from .policy_evaluation import evaluation_table, prioritize
from .visualize import render, render_model


def run(output, events_path=None, complete_coverage=False):
    settings, scenarios = config('settings.yaml'), config('scenarios.yaml')
    source = settings['source']
    raw = ROOT / source['raw_file']
    if not raw.exists():
        raise FileNotFoundError('Run python -m src.collect first; synthetic fallback is disabled')
    manifest = collect()  # Existing raw must have a verified acquisition manifest.
    if output.exists() and any(output.iterdir()):
        raise FileExistsError('Choose a new output directory to preserve previous runs')
    output.mkdir(parents=True, exist_ok=True)
    df, quality = preprocess(raw, source['encoding'], settings['analysis']['transport_codes'])
    tables, threshold = analyze(df, settings['analysis'])
    for name, table in tables.items():
        table.to_csv(output / f'{name}.csv', index=False)
    write_json(output / 'quality_report.json', quality)
    processed = ROOT / 'data/processed'
    processed.mkdir(parents=True, exist_ok=True)
    df.to_csv(processed / f'boarding_long_{source["month"]}.csv.gz', index=False, compression={'method': 'gzip', 'mtime': 0})
    render(tables, output / 'figures', settings['analysis']['top_n'])
    render_model(scenarios, output)
    stop, route = run_sensitivity(df, settings['analysis'], scenarios, threshold, output)
    candidates = prioritize(stop, tables['top_stops'])
    candidates.to_csv(output / 'pilot_candidates.csv', index=False)
    evaluation_table().to_csv(output / 'policy_costs_and_risks.csv', index=False)
    observed_status = 'not_available'
    if events_path:
        from .dwell_analysis import prepare_events, headway_statistics, aggregate_matched, fit_aggregate_relationship
        events, rejected = prepare_events(pd.read_csv(events_path, dtype=str), settings['analysis']['max_observed_dwell_seconds'])
        events.to_csv(output / 'observed_events.csv', index=False)
        rejected.to_csv(output / 'events_for_review.csv', index=False)
        headway_statistics(events).to_csv(output / 'observed_headways.csv', index=False)
        events.groupby(['route_id', 'stop_id', 'hour']).dwell_seconds.describe().to_csv(output / 'observed_dwell_distribution.csv')
        observed_status = 'observed_dwell_and_headways_only'
        if complete_coverage:
            if not rejected.empty:
                raise ValueError('Rejected events invalidate full coverage; review before aggregate regression')
            matched = aggregate_matched(df, events, complete_coverage=True)
            matched.to_csv(output / 'aggregate_join_audit.csv', index=False)
            coefficients, diagnostics = fit_aggregate_relationship(matched)
            coefficients.to_csv(output / 'observed_regression.csv', index=False)
            write_json(output / 'regression_diagnostics.json', diagnostics)
            observed_status = 'aggregate_association_estimated'
    report = {
        'created_at_utc': datetime.now(timezone.utc).isoformat(), 'python': platform.python_version(),
        'packages': {p: version(p) for p in ['pandas', 'numpy', 'matplotlib', 'PyYAML', 'statsmodels', 'scipy']},
        'raw_sha256': manifest['sha256'], 'settings': settings, 'scenarios': scenarios,
        'source_code_sha256': {p.name: digest(p) for p in sorted((ROOT / 'src').glob('*.py'))},
        'selective_monthly_boarding_threshold': threshold,
        'dwell_evidence': observed_status, 'plan': 'A/B' if events_path else 'C',
        'events_sha256': digest(events_path) if events_path else None,
        'policy_headways': 'not_estimated_without_dynamic_network_model',
        'environmental_and_monetary_benefits': 'not_estimated_without_verified_factors_and_occupancy',
    }
    write_json(output / 'run_manifest.json', report)
    top = tables['top_stops'].iloc[0]
    observed_rows = '\n'.join(f'| {row.stop_id} | {row.stop_name} | {int(row.boardings):,} |'
                              for row in tables['top_stops'].head(5).itertuples())
    candidate_rows = '\n'.join(f'| {row.stop_id} | {row.stop_name} | {row.min_conditional_daily_seconds:.1f} | {row.max_conditional_daily_seconds:.1f} |'
                               for row in candidates.head(5).itertuples())
    text = f'''# 분석 실행 결과 — {source['month']}

## 관측 수요

- 범위: 간선·지선·순환버스. 서울버스의 시외 정류장을 포함할 수 있음.
- 원본 {quality['input_rows']:,}행 중 범위 내 {quality['wide_rows_in_scope']:,}행.
- 월간 카드 승차 합계 {quality['boarding_total']:,}건.
- 최대 승차 정류장: {top.stop_name} ({top.stop_id}), {int(top.boardings):,}건.
- 출처: [서울 열린데이터광장 OA-12913]({source['page_url']}). 공공누리 1유형.

| 정류장 ID | 정류장명 | 관측 월 승차 건수 |
|---|---|---:|
{observed_rows}

## 가정 기반 정책 분석

- 시간당 정차횟수 3·6·12회 × Conservative/Base/Optimistic × 4개 정책.
- 월 승하차 / 달력 일수 / 가정 정차횟수로 유체 평균 승객 부하 산정.
- 정류장·노선별 결과: stop_scenarios.csv, route_scenarios.csv.
- 음수 절감은 지연 증가. 민감도 최솟값·최댓값은 신뢰구간이 아님.
- 후보: pilot_candidates.csv. 비용·현장 안전성 확인 전 도입 권고 확정 불가.

선택적 정책의 현장 검증 후보 상위 5곳. 아래 초 단위 수치는 해당 정류장에 정차하는
분석 범위 노선의 활동 셀을 합한 **가정 일일 차량 시간 절감**이며, 버스 1대·1회 또는 승객의 절감시간이 아님.

| 정류장 ID | 정류장명 | 가정 최소 초/일 | 가정 최대 초/일 |
|---|---|---:|---:|
{candidate_rows}

현재 유체 모형에서는 운행횟수와 평균 부하의 영향이 일일 누적값에서 상쇄될 수 있음.
이 범위는 모든 불확실성을 포함하지 않으며 실증 효과·통계적 신뢰구간이 아님.
문 이용률과 승하차 부하별 효과 부호는 figures/simulated_savings_surface.png에서 확인.

## 증거의 한계

체류시간 자료 상태: {observed_status}. 월 수요 집중은 실측 병목을 증명하지 않음.
현재 운행횟수·재차인원·완전한 방향별 정류장 순서를 확보하지 않았으므로
1회/왕복 운행시간, 승객 시간편익, 차량 감축, 증회, 정책 후 배차간격을 산출하지 않음.
노선 일일 절감은 승하차 활동이 있는 집계 셀만 포함한 가정치이며 완전한 노선 시간표가 아님.
환경계수·비용은 미확인으로 유지. 실제 정책 효과를 검증한 결과가 아님.
'''
    (output / 'summary.md').write_text(text, encoding='utf-8')
    return report


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--output', type=Path, default=ROOT / 'outputs' / 'baseline')
    p.add_argument('--events', type=Path)
    p.add_argument('--verified-complete-month-coverage', action='store_true')
    args = p.parse_args()
    run(args.output.resolve(), args.events, args.verified_complete_month_coverage)
    print(f'Results: {args.output.resolve()}')
