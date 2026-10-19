import pandas as pd

from src.common import config
from src.preprocess import preprocess
from src.eda import analyze
from src.sensitivity import run_sensitivity
from src.policy_evaluation import prioritize
from test_preprocess import source_row


def test_small_end_to_end_and_selective_scope(tmp_path):
    p = tmp_path / 'fixture.csv'
    pd.DataFrame([source_row()]).to_csv(p, encoding='cp949', index=False)
    df, _ = preprocess(p)
    settings = config('settings.yaml')['analysis']
    tables, threshold = analyze(df, settings)
    stop, route = run_sensitivity(df, settings, config('scenarios.yaml'), threshold, tmp_path)
    assert len(route) == 36
    assert (route.loc[route.policy.eq('scenario_0'), 'conditional_daily_saved_seconds'] == 0).all()
    # The top demand hours in this synthetic fixture are not peak hours, so selective policy is unchanged.
    assert (route.loc[route.policy.eq('scenario_3'), 'conditional_daily_saved_seconds'] == 0).all()
    assert len(prioritize(stop, tables['top_stops'])) == 1
    assert (tmp_path / 'stop_sensitivity_range.csv').exists()
