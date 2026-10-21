import numpy as np
import pandas as pd
import pytest
from src.common import config
from src.scenario_model import compare, policy_rear_share
from src.review_analysis import evaluate, experiments, fractions, stability, METRICS


def test_reference_examples_and_share_edges():
    s=config('scenarios.yaml');p={**s['common'],**s['conditions']['Base']}
    np.testing.assert_allclose(compare(10,[0,10,20],.5,p)[2],[15,-3.72,-18.3])
    assert compare(10,20,1,p)[2] < 0
    assert compare(10,20,0,p)[2] == 0
    for r in [-.01,1.01,np.inf,np.nan]:
        with pytest.raises(ValueError):compare(10,0,r,p)
    with pytest.raises(ValueError):policy_rear_share([10],[0],[True],{'rear_share':.9,'selective':True},{'rear_share_scale':2})


def test_denominators_and_rollup():
    s=config('scenarios.yaml');settings=config('settings.yaml')['analysis'];e=next(experiments(settings,s))[2]
    e['quantile']=0; e['peak_hours']=[8]
    df=pd.DataFrame(dict(boardings=[300,300,0,0],alightings=[0,600,0,300],days_in_month=[30]*4,hour=[8,8,8,10],stop_id=['a','a','b','b']))
    x,rear,_=evaluate(df,e,s['policies']['scenario_3'])
    assert list(x.worsened_cells)==[0,1,0,0]
    t=fractions(pd.DataFrame([x[METRICS].sum()])).iloc[0]
    assert t.all_cells==4 and t.active_cells==3 and t.applied_cells==2
    assert t.worsened_fraction==.25 and t.applied_worsened_fraction==.5
    assert t.worsened_daily_delay_seconds > 0
    np.testing.assert_allclose(x.groupby('stop_id')[METRICS].sum().sum(),x[METRICS].sum())
    x,rear,_=evaluate(df,e,s['policies']['scenario_4'])
    assert list(rear>0)==[True,False,False,False]
    assert (x.loc[rear==0,'conditional_daily_saved_seconds']==0).all()
    e['params']['crowding']=.4
    x,rear,_=evaluate(df,e,s['policies']['scenario_4']);assert (rear==0).all()


def test_small_population_stability_and_configs():
    rows=[]
    for exp,ids in [('reference',['a','b']),('other',['b','a'])]:
        for rank,id_ in enumerate(ids,1): rows.append(dict(policy='p',experiment=exp,stop_id=id_,rank=rank,conditional_daily_saved_seconds=3-rank))
    top,overlap,freq=stability(pd.DataFrame(rows),10)
    assert len(top)==4 and (overlap.reference_top_count==2).all() and (overlap.overlap_fraction==1).all()
    assert (freq.inclusion_frequency==1).all()
    s=config('scenarios.yaml'); e=list(experiments(config('settings.yaml')['analysis'],s))
    assert len({x[0] for x in e})==23
    e[1][2]['params']['tag_seconds']=999
    assert e[0][2]['params']['tag_seconds']==1.5
