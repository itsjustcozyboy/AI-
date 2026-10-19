import pandas as pd
import pytest

from src.dwell_analysis import prepare_events, aggregate_matched, headway_statistics


def fixture():
    return pd.DataFrame([
        {'event_id': str(i), 'vehicle_id': str(i), 'trip_id': str(i), 'route_id': 'TEST',
         'direction': 'out', 'stop_id': '0001', 'service_date': '2026-02-01',
         'arrival_time': f'2026-02-01T23:{minute}:50', 'departure_time': departure}
        for i, minute, departure in [(1, '49', '2026-02-01T23:50:10'),
                                     (2, '59', '2026-02-02T00:00:10')]])


def test_midnight_and_headways():
    e, bad = prepare_events(fixture())
    assert bad.empty
    assert e.dwell_seconds.tolist() == [20, 20]
    assert headway_statistics(e).mean_seconds.iloc[0] == 600


def test_negative_duration_quarantined():
    x = fixture(); x.loc[0, 'departure_time'] = '2026-02-01T00:00:00'
    e, bad = prepare_events(x)
    assert len(e) == 1 and len(bad) == 1


def test_aggregate_join_preserves_demand_not_per_event_duplication():
    e, _ = prepare_events(fixture())
    demand = pd.DataFrame([{'month': '202602', 'route_id': 'TEST', 'stop_id': '0001',
                           'hour': 23, 'boardings': 100, 'alightings': 50}])
    with pytest.raises(ValueError, match='coverage'):
        aggregate_matched(demand, e)
    joined = aggregate_matched(demand, e, complete_coverage=True)
    assert len(joined) == 1
    assert joined.boardings.iloc[0] == 100
    assert joined.boardings_per_event.iloc[0] == 50


def test_regression_recovers_synthetic_association():
    import itertools
    import numpy as np
    from src.dwell_analysis import fit_aggregate_relationship
    rng = np.random.default_rng(23)
    x = pd.DataFrame(list(itertools.product(['r1', 'r2', 'r3', 'r4'], ['s1', 's2', 's3'], [7, 8], ['202601', '202602'])),
                     columns=['route_id', 'stop_id', 'hour', 'month'])
    x['boardings_per_event'] = rng.uniform(0, 20, len(x))
    x['alightings_per_event'] = rng.uniform(0, 20, len(x))
    x['event_count'] = 10
    x['mean_dwell_seconds'] = 5 + 2*x.boardings_per_event + .5*x.alightings_per_event + rng.normal(0, .01, len(x))
    x['_merge'] = 'both'
    table, diagnostics = fit_aggregate_relationship(x)
    assert table.set_index('term').loc['boardings_per_event', 'coefficient'] == pytest.approx(2, abs=.01)
    assert diagnostics['n_aggregates'] == len(x)
