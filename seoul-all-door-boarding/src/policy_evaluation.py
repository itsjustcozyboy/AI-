import numpy as np
import pandas as pd


def evaluation_table():
    rows = [
        ('rear_terminal', '뒷문 단말기 추가 설치', '기존 하차 단말기의 승차 처리·펌웨어 지원과 추가 설치 필요성 확인'),
        ('fare_inspection', '검표·무임승차 대응', '현장 검표 인력·적발률·요금수입 변화 실증'),
        ('transfer_settlement', '수도권 환승 정산', '승차/하차 구분, 중복 태그, 환승 할인·기관 간 정산 검증'),
        ('conflict', '승하차 동선 충돌', '하차 우선, 안내 인력, 정류장 대기열·보도 폭 평가'),
        ('accessibility', '이동약자 접근성', '휠체어 경사판·승강 공간 확보, 승객 안내와 도움 시간 유지'),
        ('maintenance', '운영·유지보수', '통신·유지관리·교육·장애 대응 견적 확보'),
        ('energy', '차종별 에너지', '디젤·CNG 공회전율, 전기버스 보조전력과 조건별 계수 확보'),
    ]
    return pd.DataFrame([{'item': k, 'label': label, 'cost_krw': None, 'status': 'unverified',
                          'required_evidence': evidence} for k, label, evidence in rows])


def conditional_energy(saved_seconds, vehicle_type, rate_per_hour, co2_kg_per_unit,
                       affected_fraction, factor_source):
    """Explicit supplied factors only. electric uses kWh/h; diesel L/h; CNG kg/h.

    Electric CO2 is electricity-supply-associated, not tailpipe emissions.
    Negative savings propagate as an increase. Stops/accelerations are unchanged.
    """
    if vehicle_type not in {'diesel', 'CNG', 'electric'} or not factor_source:
        raise ValueError('Vehicle type and documented factor source are required')
    if not all(np.isfinite(x) for x in [saved_seconds, rate_per_hour, co2_kg_per_unit, affected_fraction]):
        raise ValueError('Finite inputs required')
    if rate_per_hour < 0 or co2_kg_per_unit < 0 or not 0 <= affected_fraction <= 1:
        raise ValueError('Invalid factor')
    energy = saved_seconds / 3600 * rate_per_hour * affected_fraction
    return {'energy_saved': energy, 'co2_kg_saved': energy * co2_kg_per_unit,
            'unit': {'diesel': 'L', 'CNG': 'kg', 'electric': 'kWh'}[vehicle_type],
            'factor_source': factor_source, 'evidence_type': 'conditional_calculation'}


def monetary_benefit(passenger_hours_saved, value_of_time_krw_per_hour, source):
    if not source or not np.isfinite(passenger_hours_saved) or not np.isfinite(value_of_time_krw_per_hour) or value_of_time_krw_per_hour < 0:
        raise ValueError('Explicit passenger-hours and documented value of time required')
    return passenger_hours_saved * value_of_time_krw_per_hour


def prioritize(stop_simulations, observed_stops):
    # Robustness screen only; no invented composite weighting or unverified costs.
    x = stop_simulations[stop_simulations.policy.eq('scenario_3')]
    summary = x.groupby('stop_id', as_index=False).agg(
        min_conditional_daily_seconds=('conditional_daily_saved_seconds', 'min'),
        max_conditional_daily_seconds=('conditional_daily_saved_seconds', 'max'))
    result = observed_stops.merge(summary, on='stop_id', how='left', validate='one_to_one')
    result['positive_in_all_assumptions'] = result.min_conditional_daily_seconds > 0
    result['recommendation_status'] = 'field_validation_candidate_not_final_adoption'
    return result.sort_values(['positive_in_all_assumptions', 'min_conditional_daily_seconds', 'boardings'], ascending=False)
