"""Submission evidence: deterministic exploratory experiments, complete denominators."""
import argparse
from copy import deepcopy
from pathlib import Path
import subprocess
import platform
from datetime import datetime, timezone
from importlib.metadata import version
import numpy as np
import pandas as pd
from .common import ROOT, config, digest, write_json
from .collect import collect
from .preprocess import preprocess
from .eda import analyze
from .scenario_model import compare, policy_rear_share

METRICS = ['all_cells','active_cells','applied_cells','improved_cells','unchanged_cells','worsened_cells',
           'applied_improved_cells','applied_unchanged_cells','applied_worsened_cells',
           'conditional_daily_saved_seconds','worsened_daily_delay_seconds','boardings','applied_boardings']


def experiments(settings, scenarios):
    base = dict(params={**scenarios['common'], **scenarios['conditions']['Base']},
                quantile=settings['selective_quantile'], peak_hours=settings['peak_hours'],
                max_alighting_boarding_ratio=scenarios['policies']['scenario_4']['max_alighting_boarding_ratio'], visits=6)
    yield 'reference', 'reference', deepcopy(base)
    for factor, values in settings['sensitivity'].items():
        for i, value in enumerate(values):
            e = deepcopy(base)
            if factor in e['params']: e['params'][factor] = value
            else: e[{'selective_quantile':'quantile'}.get(factor,factor)] = value
            yield f'oat_{factor}_{i}', 'one_factor', e
    for condition in ['Conservative', 'Optimistic']:
        for q in [.8, .95]:
            e = deepcopy(base); e['params'].update(scenarios['conditions'][condition]); e['quantile']=q
            yield f'joint_{condition}_{q}', 'multiple_factors', e
    for visits in [3,12]:
        e=deepcopy(base); e['visits']=visits
        yield f'visits_{visits}', 'algebraic_scaling_check', e


def fractions(table):
    for scope, denom in [('', 'all_cells'), ('applied_', 'applied_cells')]:
        for sign in ['improved','unchanged','worsened']:
            table[f'{scope}{sign}_fraction'] = table[f'{scope}{sign}_cells'] / table[denom].replace(0,np.nan)
    table['applied_boarding_fraction']=table.applied_boardings/table.boardings.replace(0,np.nan)
    return table


def evaluate(df, experiment, specification):
    e=experiment; p=e['params']; spec={**specification}
    if spec.get('alighting_aware'): spec['max_alighting_boarding_ratio']=e['max_alighting_boarding_ratio']
    threshold=df.loc[df.boardings.gt(0),'boardings'].quantile(e['quantile'])
    selected=df.boardings.gt(0)&df.boardings.ge(threshold)&df.hour.isin(e['peak_hours'])
    rear=policy_rear_share(df.boardings,df.alightings,selected,spec,p)
    active=(df.boardings+df.alightings).gt(0).to_numpy()
    rear=np.where(active,rear,0.)
    _,_,saved,_=compare(df.boardings/df.days_in_month/e['visits'],df.alightings/df.days_in_month/e['visits'],rear,p)
    saved=saved*e['visits']; applied=rear>0; improved=saved>1e-9; worsened=saved< -1e-9
    x=pd.DataFrame(dict(all_cells=np.ones(len(df),int),active_cells=active.astype(int),applied_cells=applied.astype(int),
        improved_cells=improved.astype(int),unchanged_cells=(~(improved|worsened)).astype(int),worsened_cells=worsened.astype(int),
        applied_improved_cells=(applied&improved).astype(int),applied_unchanged_cells=(applied&~(improved|worsened)).astype(int),
        applied_worsened_cells=(applied&worsened).astype(int),conditional_daily_saved_seconds=saved,
        worsened_daily_delay_seconds=np.where(worsened,-saved,0),boardings=df.boardings.to_numpy(),applied_boardings=np.where(applied,df.boardings,0)))
    x['stop_id']=df.stop_id.to_numpy()
    return x,rear,float(threshold)


def stability(ranks,k):
    tops=[]; comparisons=[]
    for policy, group in ranks.groupby('policy',sort=True):
        ref=group[group.experiment.eq('reference')].set_index('stop_id')
        ref_top=set(ref[ref['rank'].le(k)].index)
        for exp,g in group.groupby('experiment',sort=True):
            top=g[g['rank'].le(k)]; tops.append(top)
            common=ref[['rank']].join(g.set_index('stop_id')[['rank']],rsuffix='_other',how='inner')
            comparisons.append(dict(policy=policy,experiment=exp,intersection=len(ref_top&set(top.stop_id)),
                reference_top_count=len(ref_top),setting_top_count=len(top),requested_k=k,
                overlap_fraction=len(ref_top&set(top.stop_id))/len(ref_top) if ref_top else np.nan,
                same_population_n=len(common),spearman=common['rank'].corr(common.rank_other,method='spearman')))
    r=ranks.copy();r['in_top_k']=r['rank'].le(k)
    freq=r.groupby(['policy','stop_id'],as_index=False).agg(inclusion_count=('in_top_k','sum'),experiment_count=('experiment','nunique'),
        min_rank=('rank','min'),max_rank=('rank','max'),min_saved=('conditional_daily_saved_seconds','min'),max_saved=('conditional_daily_saved_seconds','max'))
    freq['inclusion_frequency']=freq.inclusion_count/freq.experiment_count
    freq['sign_flip']=(freq.min_saved < -1e-9)&(freq.max_saved > 1e-9)
    return pd.concat(tops),pd.DataFrame(comparisons),freq


def run(output):
    if output.exists() and any(output.iterdir()): raise FileExistsError('Use a new directory')
    output.mkdir(parents=True,exist_ok=True)
    settings=config('settings.yaml');scenarios=config('scenarios.yaml'); source=settings['source']
    acquisition=collect();df,quality=preprocess(ROOT/source['raw_file'],source['encoding'],settings['analysis']['transport_codes'])
    df=df.reset_index(drop=True); df['cell_id']=np.arange(len(df))
    df['alighting_boarding_ratio']=df.alightings/df.boardings.replace(0,np.nan)
    df['boarding_fraction']=df.boardings/(df.boardings+df.alightings).replace(0,np.nan)
    df['direction_status']='unresolved_monthly_source_no_direction'
    df['field_status']='location_direction_accessibility_terminal_unverified'
    df.to_csv(output/'observed_cells.csv.gz',index=False,compression={'method':'gzip','mtime':0})
    tables,_=analyze(df,settings['analysis'])
    for name,t in tables.items():t.to_csv(output/f'{name}.csv',index=False)
    write_json(output/'quality_report.json',quality)
    summaries=[];stops=[];ranks=[]; configs=[]
    k=settings['analysis']['stability_k']
    for eid,kind,e in experiments(settings['analysis'],scenarios):
        print(eid,flush=True)
        for policy,spec in scenarios['policies'].items():
            x,rear,threshold=evaluate(df,e,spec)
            summary=fractions(pd.DataFrame([x[METRICS].sum()]))
            grouped=fractions(x.groupby('stop_id',as_index=False)[METRICS].sum())
            for t in [summary,grouped]:
                t['experiment']=eid;t['experiment_type']=kind;t['policy']=policy;t['month']=source['month']
                t['evidence_type']='exploratory_assumption_not_observed_effect'
            grouped=grouped.merge(tables['top_stops'][['stop_id','stop_name']],on='stop_id',validate='one_to_one')
            ranked=grouped.sort_values(['conditional_daily_saved_seconds','stop_id'],ascending=[False,True]).copy()
            ranked['rank']=np.arange(1,len(ranked)+1)
            ranks.append(ranked[['experiment','experiment_type','policy','stop_id','stop_name','rank','conditional_daily_saved_seconds']])
            summaries.append(summary);stops.append(grouped)
            # Complete baseline cell effects; every other experiment publishes its own top K operational cells.
            keep=np.ones(len(df),bool) if eid=='reference' else df.stop_id.isin(ranked.head(k).stop_id).to_numpy()
            detail=df.loc[keep].copy();detail['rear_share']=rear[keep]
            detail['conditional_daily_saved_seconds']=x.loc[keep,'conditional_daily_saved_seconds'].to_numpy()
            detail['worsened_daily_delay_seconds']=x.loc[keep,'worsened_daily_delay_seconds'].to_numpy()
            detail['policy']=policy;detail['experiment']=eid
            detail['selection_reason']='peak_positive_demand_quantile_then_composition_screen' if spec.get('alighting_aware') else ('peak_positive_demand_quantile' if spec['selective'] else 'all_active_cells')
            folder=output/'cells';folder.mkdir(exist_ok=True)
            detail.to_csv(folder/f'{eid}_{policy}.csv.gz',index=False,compression={'method':'gzip','mtime':0})
            configs.append(dict(experiment=eid,experiment_type=kind,policy=policy,parameters=e,policy_specification=spec,threshold=threshold))
    comparison=pd.concat(summaries,ignore_index=True)
    comparison['policy_definition']=comparison.policy.map({key: str(value) for key,value in scenarios['policies'].items()})
    comparison['analysis_unit']='month_route_original_label_stop_transport_hour'
    comparison['time_unit']='conditional_vehicle_seconds_per_calendar_day'
    comparison['operating_constraints']='rear_alight_first;field_safety_accessibility_fare_system_unverified'
    comparison.to_csv(output/'policy_comparison.csv',index=False)
    stop=pd.concat(stops,ignore_index=True);rank=pd.concat(ranks,ignore_index=True)
    # Structural visits checks excluded from inclusion frequencies to avoid double weighting.
    top,overlap,freq=stability(rank[rank.experiment_type.ne('algebraic_scaling_check')],k)
    stop=stop.merge(freq,on=['policy','stop_id'],validate='many_to_one');stop['candidate_status']='before_field_verification'
    stop.to_csv(output/'stop_policy_summary.csv.gz',index=False)
    rank.to_csv(output/'candidate_ranks.csv.gz',index=False)
    for name,t in [('top_k_by_setting',top),('rank_overlap',overlap),('candidate_stability',freq),('sign_flip_candidates',freq[freq.sign_flip])]: t.to_csv(output/f'{name}.csv',index=False)
    write_json(output/'experiment_settings.json',configs)
    from .review_figures import render
    render(output,tables,comparison,rank,freq,scenarios)
    manifest=dict(created_at_utc=datetime.now(timezone.utc).isoformat(), git_status=subprocess.check_output(['git','status','--short'],cwd=ROOT,text=True), settings=settings,scenarios=scenarios,raw_sha256=acquisition['sha256'],python=platform.python_version(),
        packages={p:version(p) for p in ['numpy','pandas','matplotlib','PyYAML','scipy','pytest']},
        git_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        source_code_sha256={str(p.relative_to(ROOT)):digest(p) for folder in ['src','config','tests','assets'] for p in sorted((ROOT/folder).rglob('*')) if p.is_file() and '__pycache__' not in str(p)},
        outputs_sha256={str(p.relative_to(output)):digest(p) for p in sorted(output.rglob('*')) if p.is_file()})
    write_json(output/'run_manifest.json',manifest)
    return comparison

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True)
    run(parser.parse_args().output.resolve())
