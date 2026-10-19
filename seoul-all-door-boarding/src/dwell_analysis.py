"""Optional Plan A adapter. No operational records are included in this project."""
import numpy as np
import pandas as pd

from .validate import nonnegative, require_columns, unique

EVENT_REQUIRED = ['event_id', 'vehicle_id', 'trip_id', 'route_id', 'direction', 'stop_id',
                  'service_date', 'arrival_time', 'departure_time']
AGG_KEY = ['month', 'route_id', 'stop_id', 'hour']


def prepare_events(events, max_seconds=600):
    require_columns(events, EVENT_REQUIRED)
    x = events.drop_duplicates().copy()
    unique(x, ['event_id'])
    if x[EVENT_REQUIRED].isna().any().any() or x[EVENT_REQUIRED].astype(str).eq('').any().any():
        raise ValueError('Missing event fields')
    pd.to_datetime(x.service_date, format='%Y-%m-%d', errors='raise')
    for field in ['arrival_time', 'departure_time']:
        timestamps = pd.to_datetime(x[field], errors='raise', format='mixed')
        if timestamps.dt.tz is None:
            timestamps = timestamps.dt.tz_localize('Asia/Seoul')
        else:
            timestamps = timestamps.dt.tz_convert('Asia/Seoul')
        x[field] = timestamps
    x['dwell_seconds'] = (x.departure_time - x.arrival_time).dt.total_seconds()
    x['month'] = x.arrival_time.dt.strftime('%Y%m')
    x['hour'] = x.arrival_time.dt.hour
    x['invalid_reason'] = np.where(x.dwell_seconds < 0, 'negative_dwell',
                                   np.where(x.dwell_seconds > max_seconds, 'above_review_threshold', ''))
    return x[x.invalid_reason.eq('')].copy(), x[~x.invalid_reason.eq('')].copy()


def aggregate_matched(demand, events, complete_coverage=False):
    """Explicit assertion of full month/hour coverage is required from the data custodian.

    Aggregate BOTH inputs to identical keys. No monthly total is assigned to a vehicle event.
    Route labels must already have an audited crosswalk to demand route_id.
    """
    if not complete_coverage:
        raise ValueError('Complete month/hour coverage and ID crosswalk must be verified first')
    d = demand.groupby(AGG_KEY, as_index=False)[['boardings', 'alightings']].sum()
    e = events.groupby(AGG_KEY, as_index=False).agg(
        mean_dwell_seconds=('dwell_seconds', 'mean'), median_dwell_seconds=('dwell_seconds', 'median'),
        event_count=('event_id', 'size'))
    matched = d.merge(e, on=AGG_KEY, how='outer', validate='one_to_one', indicator=True)
    matched['boardings_per_event'] = matched.boardings / matched.event_count
    matched['alightings_per_event'] = matched.alightings / matched.event_count
    return matched


def fit_aggregate_relationship(matched):
    """Associational WLS, fixed effects, route-clustered 95% intervals; not policy causality."""
    import statsmodels.formula.api as smf
    x = matched[matched['_merge'].eq('both')].copy()
    if x.route_id.nunique() < 2:
        raise ValueError('At least two route clusters required (many more recommended)')
    formula = ('mean_dwell_seconds ~ boardings_per_event + alightings_per_event'
               ' + C(route_id) + C(stop_id) + C(hour) + C(month)')
    model = smf.wls(formula, data=x, weights=x.event_count)
    matrix = model.exog
    if matrix.shape[0] <= matrix.shape[1] or np.linalg.matrix_rank(matrix) < matrix.shape[1]:
        raise ValueError('Insufficient or collinear fixed-effects design; revise scope')
    result = model.fit(cov_type='cluster', cov_kwds={'groups': x.route_id})
    interval = result.conf_int()
    table = pd.DataFrame({'term': result.params.index, 'coefficient': result.params.values,
                          'lower_95': interval[0].values, 'upper_95': interval[1].values})
    return table, {'n_aggregates': int(result.nobs), 'route_clusters': int(x.route_id.nunique()),
                   'interpretation': 'aggregate association, not a causal treatment effect',
                   'warning': 'Few clusters yield unreliable intervals; assess before reporting'}


def headway_statistics(events):
    keys = ['route_id', 'direction', 'stop_id', 'service_date']
    require_columns(events, keys + ['arrival_time'])
    x = events.sort_values(keys + ['arrival_time']).copy()
    x['headway_seconds'] = x.groupby(keys).arrival_time.diff().dt.total_seconds()
    h = x.dropna(subset=['headway_seconds']).copy()
    expected = h.groupby(keys).headway_seconds.transform('median')
    h['short_gap'] = h.headway_seconds < .5 * expected
    h['long_gap'] = h.headway_seconds > 1.5 * expected
    result = h.groupby(keys, as_index=False).agg(
        intervals=('headway_seconds', 'size'), mean_seconds=('headway_seconds', 'mean'),
        std_seconds=('headway_seconds', 'std'), short_gap_rate=('short_gap', 'mean'),
        long_gap_rate=('long_gap', 'mean'))
    result['cv'] = result.std_seconds / result.mean_seconds.replace(0, np.nan)
    result['evidence_type'] = 'observed_headways'
    return result
