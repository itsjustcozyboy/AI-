# 자료사전

## 실제 다운로드 파일: OA-12913, 2026-09

UTF-8이 아닌 CP949 CSV. 원본 42,155행, 57컬럼. ID는 숫자처럼 보여도 문자열로 보존한다. 아래는 실제 헤더와 첫 행의 예다. 원본 자료형은 CSV 문자열이며 분석 자료형은 로더가 지정한다.

| 실제 원본 컬럼 | 분석 자료형 | 첫 행 예 |
|---|---|---|
| 사용년월 | string | 202609 |
| 노선번호 | string | 470 |
| 노선명 | string | 470번(상암차고지~안골마을) |
| 표준버스정류장ID | string | 100000001 |
| 버스정류장ARS번호 | string | 01001 |
| 역명 | string | 종로2가사거리(00063) |
| 00시승차총승객수 | int64 | 196 |
| 00시하차총승객수 | int64 | 170 |
| 1시승차총승객수 | int64 | 0 |
| 1시하차총승객수 | int64 | 0 |
| 2시승차총승객수 | int64 | 0 |
| 2시하차총승객수 | int64 | 0 |
| 3시승차총승객수 | int64 | 0 |
| 3시하차총승객수 | int64 | 0 |
| 4시승차총승객수 | int64 | 0 |
| 4시하차총승객수 | int64 | 0 |
| 5시승차총승객수 | int64 | 0 |
| 5시하차총승객수 | int64 | 0 |
| 6시승차총승객수 | int64 | 194 |
| 6시하차총승객수 | int64 | 86 |
| 7시승차총승객수 | int64 | 540 |
| 7시하차총승객수 | int64 | 295 |
| 8시승차총승객수 | int64 | 653 |
| 8시하차총승객수 | int64 | 381 |
| 9시승차총승객수 | int64 | 561 |
| 9시하차총승객수 | int64 | 456 |
| 10시승차총승객수 | int64 | 511 |
| 10시하차총승객수 | int64 | 338 |
| 11시승차총승객수 | int64 | 574 |
| 11시하차총승객수 | int64 | 407 |
| 12시승차총승객수 | int64 | 455 |
| 12시하차총승객수 | int64 | 519 |
| 13시승차총승객수 | int64 | 408 |
| 13시하차총승객수 | int64 | 593 |
| 14시승차총승객수 | int64 | 336 |
| 14시하차총승객수 | int64 | 496 |
| 15시승차총승객수 | int64 | 307 |
| 15시하차총승객수 | int64 | 548 |
| 16시승차총승객수 | int64 | 327 |
| 16시하차총승객수 | int64 | 665 |
| 17시승차총승객수 | int64 | 384 |
| 17시하차총승객수 | int64 | 845 |
| 18시승차총승객수 | int64 | 339 |
| 18시하차총승객수 | int64 | 925 |
| 19시승차총승객수 | int64 | 379 |
| 19시하차총승객수 | int64 | 610 |
| 20시승차총승객수 | int64 | 389 |
| 20시하차총승객수 | int64 | 436 |
| 21시승차총승객수 | int64 | 363 |
| 21시하차총승객수 | int64 | 256 |
| 22시승차총승객수 | int64 | 346 |
| 22시하차총승객수 | int64 | 313 |
| 23시승차총승객수 | int64 | 322 |
| 23시하차총승객수 | int64 | 232 |
| 교통수단타입코드 | string | 010 |
| 교통수단타입명 | string | 서울간선버스 |
| 등록일자 | string | 20261003 |

## 정규화된 집계 자료 (내부 스키마)

| 컬럼 | 의미/단위 |
|---|---|
| month | YYYYMM, 원본 사용년월 |
| route_id / route_name | 원본 노선번호/노선명. route_id는 내부 별칭이며 BIS 노선 ID가 아님 |
| stop_id / ars_id | 표준버스정류장ID / ARS번호. 문자열 |
| stop_label / stop_name | 원문 역명 / 표시용 끝 숫자 괄호 제거 이름. 원문을 키에 보존 |
| transport_code / transport_name | 원본 교통수단타입코드/명 |
| registered_date | 원본 등록일자, YYYYMMDD |
| hour | 0–23, Asia/Seoul 시각대, 일별 날짜는 없음 |
| boardings / alightings | 해당 월·원문 식별 셀·시간대의 승차/하차 카드 이용 합계(건) |
| days_in_month | 해당 달의 달력 일수. 영업일 수 아님 |
| evidence_type | observed_monthly_aggregate |

고유키: month, route_id, route_name, stop_id, stop_label, transport_code, hour. 원본 표기가 여러 개인 경우 정류장명만으로 중복 삭제하지 않는다.

## 별도 정차 이벤트의 내부 입력 계약 (공개 데이터 실제 컬럼 아님)

| 필수 컬럼 | 내부 형식 |
|---|---|
| event_id | 이벤트 고유 문자열 |
| vehicle_id / trip_id | 차량/운행 회차 식별 문자열 |
| route_id | 월 집계 노선번호와 별도 crosswalk 완료한 문자열 |
| direction | 방향 문자열. 반대 방향 간 배차 차분 금지 |
| stop_id | 월 집계 표준 정류장 ID와 매핑한 문자열 |
| service_date | YYYY-MM-DD, 운영기관 정의 영업일 |
| arrival_time / departure_time | 날짜 포함 ISO8601. 오프셋 없으면 Asia/Seoul로 해석 |

동일 event_id에 다른 값이 있으면 실패한다. 이벤트별 승하차 수는 현재 공개 자료에서 확보하지 않았으므로 정의만으로 생성하지 않는다. 좌표는 별도 검증 함수에 stop_id, longitude, latitude의 WGS84 입력 계약으로 전달할 수 있다.

## 시뮬레이션 출력

- baseline_seconds / policy_seconds / saved_seconds: 평균 가정 이벤트당 초; saved=baseline-policy.
- saved_fraction: 절감 초/기준 초. 음수는 증가.
- conditional_daily_saved_seconds: 승하차 활동 셀에서 가정한 하루의 차량 초 합계. 승객 초나 실측 일일 절감이 아님.
- assumed_daily_events_in_covered_cells: 활동 셀마다 가정 정차횟수 합계. 실제 운행횟수 아님.
- mean_saved_seconds_per_assumed_event: 위 두 값의 비.
- worsened_cells: 정책 체류시간이 증가하는 월·노선 원문·정류장 원문·시간대 셀 수.
- min/max_conditional_daily_seconds: 설정 범위 최솟값/최댓값, 통계 신뢰구간 아님.
- cost_krw 빈 값: 미확인. 비용 0원을 의미하지 않음.
