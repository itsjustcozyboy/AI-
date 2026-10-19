import numpy as np
import pandas as pd

from .scenario_model import compare


def run_sensitivity(df, settings, scenarios, threshold, output):
    """Evaluate all observed cells; publish compact grouped results and top-cell details.

    Monthly/days/assumed visits is a fluid mean, not an observed vehicle load.
    Daily savings cover only hour cells with observed passenger activity.
    """
    cells = df[(df.boardings + df.alightings) > 0].copy()
    selected = (cells.boardings >= threshold) & cells.hour.isin(settings['peak_hours'])
    top = cells.boardings.rank(method='first', ascending=False) <= settings['top_n']
    stop_outputs, route_outputs, details = [], [], []
    for visits in settings['assumed_visits_per_hour']:
        if not np.isfinite(visits) or visits <= 0:
            raise ValueError('Assumed visits/hour must be positive')
        b = cells.boardings.to_numpy() / cells.days_in_month.to_numpy() / visits
        a = cells.alightings.to_numpy() / cells.days_in_month.to_numpy() / visits
        for condition, modifiers in scenarios['conditions'].items():
            params = {**scenarios['common'], **modifiers}
            for policy, specification in scenarios['policies'].items():
                share = specification['rear_share'] * modifiers['rear_share_scale']
                rear = np.where(selected, share, 0) if specification['selective'] else share
                baseline, dwell, saved, ratio = compare(b, a, rear, params)
                out = cells[['month', 'route_id', 'stop_id']].copy()
                out['baseline_seconds_sum'] = baseline * visits
                out['policy_seconds_sum'] = dwell * visits
                out['conditional_daily_saved_seconds'] = saved * visits
                out['assumed_daily_events_in_covered_cells'] = visits
                out['worsened_cells'] = (saved < -1e-9).astype(int)
                value_cols = list(out.columns[3:])
                for keys, sink in [(['month', 'stop_id'], stop_outputs), (['month', 'route_id'], route_outputs)]:
                    grouped = out.groupby(keys, as_index=False)[value_cols].sum()
                    grouped['mean_saved_seconds_per_assumed_event'] = grouped.conditional_daily_saved_seconds / grouped.assumed_daily_events_in_covered_cells
                    grouped['saved_fraction'] = grouped.conditional_daily_saved_seconds / grouped.baseline_seconds_sum
                    grouped['condition'] = condition
                    grouped['policy'] = policy
                    grouped['assumed_visits_per_hour'] = visits
                    grouped['evidence_type'] = 'assumption_based_simulation'
                    sink.append(grouped)
                detail = cells.loc[top, ['month', 'route_id', 'route_name', 'stop_id', 'stop_label', 'hour', 'boardings', 'alightings']].copy()
                detail['mean_boardings_per_assumed_event'] = b[top]
                detail['baseline_seconds'] = baseline[top]
                detail['policy_seconds'] = dwell[top]
                detail['saved_seconds'] = saved[top]
                detail['saved_fraction'] = ratio[top]
                detail['condition'], detail['policy'] = condition, policy
                detail['assumed_visits_per_hour'] = visits
                detail['evidence_type'] = 'assumption_based_simulation'
                details.append(detail)
    stop = pd.concat(stop_outputs, ignore_index=True)
    route = pd.concat(route_outputs, ignore_index=True)
    for name, table in [('stop_scenarios', stop), ('route_scenarios', route), ('top_cell_scenarios', pd.concat(details))]:
        table.to_csv(output / f'{name}.csv', index=False)
    for name, table, key in [('stop', stop, 'stop_id'), ('route', route, 'route_id')]:
        bounds = table.groupby(['month', key, 'policy'], as_index=False).agg(
            min_conditional_daily_seconds=('conditional_daily_saved_seconds', 'min'),
            max_conditional_daily_seconds=('conditional_daily_saved_seconds', 'max'))
        bounds['interpretation'] = 'scenario_envelope_not_confidence_interval'
        bounds.to_csv(output / f'{name}_sensitivity_range.csv', index=False)
    return stop, route
