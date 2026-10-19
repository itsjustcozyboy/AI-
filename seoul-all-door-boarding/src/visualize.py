import os
os.environ.setdefault('MPLCONFIGDIR', '/tmp/seoul-adb-matplotlib')
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


def render(tables, output, top_n=30):
    output.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update({'figure.dpi': 150, 'axes.spines.top': False, 'axes.spines.right': False})

    def save(name):
        plt.gcf().text(.01, .01, 'Source: Seoul Metropolitan Government, OA-12913 | monthly card counts', fontsize=7)
        plt.tight_layout(rect=(0, .04, 1, 1))
        plt.savefig(output / f'{name}.png')
        plt.close()

    h = tables['hourly_demand']
    plt.figure(figsize=(9, 4)); plt.bar(h.hour, h.boardings, color='#227c9d')
    plt.xlabel('Hour (Asia/Seoul)'); plt.ylabel('Monthly boardings')
    plt.title('Observed monthly demand | selected Seoul bus types'); save('hourly_demand')
    s = tables['top_stops'].head(top_n).iloc[::-1]
    plt.figure(figsize=(9, 8)); plt.barh(s.stop_id, s.boardings, color='#227c9d')
    plt.xlabel('Monthly boardings'); plt.ylabel('Standard stop ID')
    plt.title('Observed demand ranking (not measured dwell)'); save('top_stops')
    r = tables['route_concentration'].sort_values('hhi', ascending=False).head(top_n).copy()
    # Some route labels are Korean. Keep an explicit mapping where no Korean font is installed.
    r['plot_label'] = [label if str(label).isascii() else f'Rank {i+1:02d} (see CSV)'
                       for i, label in enumerate(r.route_id)]
    r.to_csv(output / 'route_plot_labels.csv', index=False)
    r = r.iloc[::-1]
    plt.figure(figsize=(9, 8)); plt.barh(r.plot_label, r.hhi, color='#3a7d44')
    plt.xlabel('Stop-level boarding HHI'); plt.ylabel('Route label'); save('route_concentration')
    p = tables['peak_candidates'].head(top_n).iloc[::-1]
    plt.figure(figsize=(9, 8)); plt.barh(p.stop_id + ' @ ' + p.hour.astype(str), p.boardings, color='#e08e45')
    plt.xlabel('Monthly boardings in selected peak hour'); save('peak_candidates')
    ids = tables['top_stops'].head(top_n).stop_id
    m = tables['stop_hour_demand'].pivot(index='stop_id', columns='hour', values='boardings').reindex(ids)
    plt.figure(figsize=(10, 8)); plt.imshow(m, aspect='auto', cmap='YlGnBu')
    plt.xticks(range(24)); plt.yticks(range(len(m)), m.index); plt.xlabel('Hour')
    plt.colorbar(label='Monthly boardings'); plt.title('Observed stop-hour demand'); save('stop_hour_heatmap')
    c = tables['top_stops']
    plt.figure(figsize=(8, 4)); plt.plot(np.arange(1, len(c)+1)/len(c), c.cumulative_share)
    plt.xlabel('Fraction of stops, highest demand first'); plt.ylabel('Cumulative boarding share')
    save('demand_concentration')


def render_model(scenarios, output):
    """Demand/rear-share surface is wholly hypothetical, separate from observed EDA."""
    from .scenario_model import compare
    params = {**scenarios['common'], **scenarios['conditions']['Base']}
    b, r = np.meshgrid(np.arange(0, 51), np.linspace(0, 1, 51))
    fig, axes = plt.subplots(1, 3, figsize=(13, 4), sharey=True)
    tables = []
    for ax, a in zip(axes, [0, 5, 20]):
        _, _, saved, _ = compare(b, a, r, params)
        artist = ax.pcolormesh(b, r, saved, cmap='RdBu', vmin=-60, vmax=60, shading='auto')
        ax.contour(b, r, saved, levels=[0], colors='black', linewidths=.6)
        ax.set_title(f'Assumed alightings: {a}')
        ax.set_xlabel('Assumed boardings/event')
        tables.append(pd.DataFrame({'boardings': b.ravel(), 'alightings': a, 'rear_share': r.ravel(),
                                    'saved_seconds': saved.ravel(), 'evidence_type': 'assumption_based_simulation'}))
    axes[0].set_ylabel('Rear-door boarding share')
    fig.colorbar(artist, ax=axes, label='Saved seconds/event (negative = delay)', shrink=.8)
    fig.suptitle('Hypothetical service model | Base assumptions | NOT measured policy effects')
    fig.text(.01, .01, 'All service parameters are uncalibrated assumptions; black contour = zero savings.', fontsize=8)
    fig.subplots_adjust(top=.80, bottom=.18, right=.78, wspace=.2)
    fig.savefig(output / 'figures' / 'simulated_savings_surface.png')
    plt.close(fig)
    pd.concat(tables).to_csv(output / 'modeled_savings_by_demand.csv', index=False)
