"""Audit completed full-data results and export report evidence without truncating totals."""
import argparse
import json
import shutil
from pathlib import Path
import numpy as np
import pandas as pd
from .common import digest, write_json
from .review_analysis import METRICS

LABELS = {'scenario_0':'현행','scenario_1':'제한 뒷문','scenario_2':'전 문 확대','scenario_3':'피크 선택','scenario_4':'하차 고려 선택'}


def table(frame):
    return '\n'.join(['| '+' | '.join(map(str,frame.columns))+' |', '| '+' | '.join(['---']*len(frame.columns))+' |'] + ['| '+' | '.join(map(str,row))+' |' for row in frame.itertuples(index=False,name=None)])


def export(run, destination):
    if destination.exists() and any(destination.iterdir()):
        raise FileExistsError('Choose a fresh export directory')
    manifest=json.loads((run/'run_manifest.json').read_text())
    for name,checksum in manifest['outputs_sha256'].items():
        assert digest(run/name)==checksum, name
    comparison=pd.read_csv(run/'policy_comparison.csv')
    stops=pd.read_csv(run/'stop_policy_summary.csv.gz',dtype={'stop_id':str})
    grouped=stops.groupby(['experiment','policy'])[METRICS].sum().sort_index()
    expected=comparison.set_index(['experiment','policy'])[METRICS].sort_index()
    np.testing.assert_allclose(grouped,expected,rtol=1e-10,atol=1e-6)
    configs=json.loads((run/'experiment_settings.json').read_text())
    assert len(configs)==len(comparison)
    assert {(x['experiment'],x['policy']) for x in configs}==set(comparison.set_index(['experiment','policy']).index)
    for scope,denom in [('', 'all_cells'),('applied_', 'applied_cells')]:
        for sign in ['improved','unchanged','worsened']:
            np.testing.assert_allclose(comparison[scope+sign+'_fraction'],comparison[scope+sign+'_cells']/comparison[denom].replace(0,np.nan),equal_nan=True)
    reference=comparison[comparison.experiment.eq('reference')].copy()
    for policy in LABELS:
        cell=pd.read_csv(run/'cells'/f'reference_{policy}.csv.gz',dtype={'stop_id':str})
        by_stop=cell.groupby('stop_id').conditional_daily_saved_seconds.sum().sort_index()
        target=stops[(stops.experiment=='reference')&(stops.policy==policy)].set_index('stop_id').sort_index()
        np.testing.assert_allclose(by_stop,target.conditional_daily_saved_seconds,atol=1e-7)
        assert (cell.loc[cell.rear_share.eq(0),'conditional_daily_saved_seconds']==0).all()
        worsened=cell.conditional_daily_saved_seconds.lt(-1e-9)
        row=reference[reference.policy.eq(policy)].iloc[0]
        assert worsened.sum()==row.worsened_cells
        np.testing.assert_allclose(cell.worsened_daily_delay_seconds.sum(),row.worsened_daily_delay_seconds)
        if policy=='scenario_4':
            detail=cell
    for eid in ['visits_3','visits_12']:
        np.testing.assert_allclose(comparison[comparison.experiment.eq(eid)].conditional_daily_saved_seconds,reference.conditional_daily_saved_seconds,atol=1e-6)
    destination.mkdir(parents=True)
    for name in ['policy_comparison.csv','quality_report.json','run_manifest.json','experiment_settings.json','hourly_demand.csv','top_stops.csv','top_k_by_setting.csv','rank_overlap.csv','candidate_stability.csv','sign_flip_candidates.csv']:
        shutil.copy2(run/name,destination/name)
    shutil.copytree(run/'figures',destination/'figures')
    top=pd.read_csv(run/'top_k_by_setting.csv',dtype={'stop_id':str})
    top=top[(top.experiment=='reference')&(top.policy=='scenario_4')].sort_values('rank').head(3)
    selected=detail[detail.stop_id.isin(top.stop_id)]
    selected.to_csv(destination/'pilot_operating_cells.csv',index=False)
    operating=selected[selected.rear_share.gt(0)].groupby(['stop_id','stop_name','route_id','route_name'],as_index=False).agg(hours=('hour',lambda x:','.join(map(str,sorted(set(x))))),monthly_boardings=('boardings','sum'),monthly_alightings=('alightings','sum'),daily_saved_seconds=('conditional_daily_saved_seconds','sum'))
    operating.to_csv(destination/'pilot_route_hours.csv',index=False)
    reference['정책']=reference.policy.map(LABELS)
    display=pd.DataFrame({'정책':reference['정책'],'조건부 차량시간 절감(시간/일)':reference.conditional_daily_saved_seconds.div(3600).map(lambda v:f'{v:.3f}'),'악화 셀':reference.worsened_cells.astype(int),'전체 셀 중 악화(%)':reference.worsened_fraction.mul(100).map(lambda v:f'{v:.3f}'),'적용 셀':reference.applied_cells.astype(int),'적용 승차(%)':reference.applied_boarding_fraction.mul(100).map(lambda v:f'{v:.3f}')})
    q=json.loads((run/'quality_report.json').read_text())
    summary=f'''# 보고서용 검증 수치

관측: 2026년 9월, 간선·지선·순환. 원본 {q['input_rows']:,}행, 범위 내 {q['wide_rows_in_scope']:,}행 → {q['hourly_cells']:,}시간 셀. 월 승차 {q['boarding_total']:,}건, 하차 {q['alighting_total']:,}건.

출처: 서울특별시 OA-12913. 월·노선·원문 정류장 표기·표준 ID·차종·시간대 집계. 서울버스의 시외 정류장 포함 가능. 차량 정차 이벤트 아님.

기준 Base/reference의 전체 모집단 합계 (서로 다른 설정을 합산하지 않음):

{table(display)}

시간은 모형에 따른 조건부 차량 시간이며 승객 시간 또는 실측 효과가 아니다. 적용 셀 분모의 악화 비율과 악화 지연 합계는 policy_comparison.csv에 별도 보존한다. 현행은 적용 셀이 0이므로 적용 셀 비율은 결측이다.

우선 현장 검토 3곳 (기준 순위일 뿐 확정 도입 순위 아님):

{table(top[['stop_id','stop_name','rank','conditional_daily_saved_seconds']])}

마지막 열 단위: 초/달력일. 대상 노선·시간대는 pilot_route_hours.csv, 미적용 셀을 포함한 상세 범위는 pilot_operating_cells.csv. 방향·좌표·접근성·단말기는 미확인.

기준 1 + 한 요인 16 + 복수 요인 4 = 탐색 21개. 별도 운행횟수 상쇄 점검 2개. 상위 K=10, 동점은 표준 ID 오름차순. 포함 빈도는 확률이 아니다. 모든 정책·설정의 전체 합계는 policy_comparison.csv, 전체 정류장은 원 실행 stop_policy_summary.csv.gz. 상세 전 셀은 원 실행 cells/reference_*.csv.gz. 나머지 설정 상세는 설정별 상위 K 정류장만 공개한다.

원 실행: {run.name}. 입력·설정·코드·환경·결과 해시: run_manifest.json. 5개 PNG는 figures/01_hourly.png부터 05_stability.png까지이며 관측/가정을 명시했다.
'''
    (destination/'summary.md').write_text(summary)
    write_json(destination/'verification.json',{'status':'passed','checks':['all_run_output_hashes','all_setting_stop_to_policy_rollup','reference_cells_to_stops_all_five_policies','nonapplied_zero_change','worsened_counts_and_delay','all_and_applied_denominators','experiment_traceability','visits_algebraic_cancellation'],'empirical_policy_validation':False})
    write_json(destination/'export_manifest.json',{'source_run':str(run.resolve()),'source_manifest_sha256':digest(run/'run_manifest.json'),'full_totals':True,'pilot_detail_scope':'reference scenario_4 top 3 stops, all their cells','files_sha256':{str(p.relative_to(destination)):digest(p) for p in sorted(destination.rglob('*')) if p.is_file()}})
    return display

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);p.add_argument('--destination',type=Path,required=True)
    a=p.parse_args();print(export(a.run.resolve(),a.destination.resolve()).to_string(index=False))
