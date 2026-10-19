import numpy as np


def analyze(df, settings):
    """Monthly observed demand; peak hours include all days, never mislabeled weekdays."""
    hourly = df.groupby('hour', as_index=False)[['boardings', 'alightings']].sum()
    stops = df.groupby('stop_id', as_index=False).agg(
        stop_name=('stop_name', 'first'), boardings=('boardings', 'sum'), alightings=('alightings', 'sum'))
    stops = stops.sort_values(['boardings', 'stop_id'], ascending=[False, True])
    stops['cumulative_share'] = stops.boardings.cumsum() / stops.boardings.sum()
    route_stop = df.groupby(['route_id', 'stop_id'], as_index=False).boardings.sum()
    route_stop['share'] = route_stop.boardings / route_stop.groupby('route_id').boardings.transform('sum')
    route_stop['share_squared'] = route_stop.share ** 2
    routes = route_stop.groupby('route_id', as_index=False).agg(
        boardings=('boardings', 'sum'), hhi=('share_squared', 'sum'), max_stop_share=('share', 'max'),
        stops=('stop_id', 'nunique'))
    peak = df[df.hour.isin(settings['peak_hours'])].groupby(['stop_id', 'hour'], as_index=False).agg(
        stop_name=('stop_name', 'first'), boardings=('boardings', 'sum'), alightings=('alightings', 'sum'))
    peak = peak.sort_values(['boardings', 'stop_id', 'hour'], ascending=[False, True, True])
    heatmap = df.groupby(['stop_id', 'hour'], as_index=False).boardings.sum()
    distribution = df[['boardings', 'alightings']].quantile([0, .25, .5, .75, .9, .95, .99, 1]).reset_index(names='quantile')
    threshold = df.loc[df.boardings > 0, 'boardings'].quantile(settings['selective_quantile'])
    return {'hourly_demand': hourly, 'top_stops': stops, 'route_concentration': routes,
            'peak_candidates': peak, 'stop_hour_demand': heatmap, 'demand_distribution': distribution}, float(threshold)
