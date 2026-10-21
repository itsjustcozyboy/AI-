"""Two-door fluid service model. Inputs may be hypothetical mean passengers/event."""
import numpy as np


def dwell_seconds(boardings, alightings, rear_share, params):
    b, a, r = np.broadcast_arrays(np.asarray(boardings, float), np.asarray(alightings, float),
                                  np.asarray(rear_share, float))
    if not all(np.isfinite(x).all() for x in (b, a, r)) or (b < 0).any() or (a < 0).any():
        raise ValueError('Passenger loads must be finite and nonnegative')
    if ((r < 0) | (r > 1)).any():
        raise ValueError('Rear share must be in [0,1]')
    required = ['overhead_seconds', 'tag_seconds', 'front_move_seconds', 'rear_move_seconds',
                'alight_seconds', 'interference', 'crowding', 'accessibility_seconds',
                'accessibility_probability']
    if any(not np.isfinite(params[k]) or params[k] < 0 for k in required):
        raise ValueError('Parameters must be finite and nonnegative')
    if params['accessibility_probability'] > 1:
        raise ValueError('Assistance probability must be <= 1')
    factor = 1 + params['crowding']
    # Conservative sequential tag+movement at each entrance. Rear door alights then boards.
    front = b * (1 - r) * (params['tag_seconds'] + params['front_move_seconds']) * factor
    rear_board = b * r * (params['tag_seconds'] + params['rear_move_seconds']) * factor
    rear_alight = a * params['alight_seconds'] * factor
    conflict = params['interference'] * np.minimum(rear_board, rear_alight)
    service = np.maximum(front, rear_alight + rear_board + conflict)
    # Expected assistance overhead; same assumption across policies, never removed as a benefit.
    assistance = params['accessibility_probability'] * params['accessibility_seconds']
    return params['overhead_seconds'] + service + assistance


def compare(boardings, alightings, rear_share, params):
    baseline = dwell_seconds(boardings, alightings, 0.0, params)
    policy = dwell_seconds(boardings, alightings, rear_share, params)
    saved = baseline - policy
    return baseline, policy, saved, np.divide(saved, baseline, out=np.zeros_like(saved), where=baseline > 0)


def policy_rear_share(boardings, alightings, selected, specification, modifiers):
    """Monthly composition screen; rear alighting finishes before rear boarding."""
    b, a = np.broadcast_arrays(np.asarray(boardings, float), np.asarray(alightings, float))
    share = specification['rear_share'] * modifiers['rear_share_scale']
    if not np.isfinite(share) or not 0 <= share <= 1:
        raise ValueError('Effective rear share must be in [0,1]')
    eligible = np.asarray(selected, bool) if specification['selective'] else np.ones(b.shape, bool)
    if specification.get('alighting_aware'):
        ratio = specification['max_alighting_boarding_ratio']
        if not np.isfinite(ratio) or ratio < 0:
            raise ValueError('Invalid composition threshold')
        eligible = eligible & (b > 0) & (a <= ratio * b) & (modifiers['crowding'] <= specification['max_crowding'])
    return np.where(eligible, share, 0.)
