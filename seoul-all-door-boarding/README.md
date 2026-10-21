# 서울 시내버스 전 문 승차 정책 분석

공식 승하차 집계로 우선 조사할 정류장을 찾고, 문별 승객 처리 모형으로 정책 시나리오를 비교하는 **Plan C 연구 MVP**입니다. 실제 체류시간 감소를 검증한 연구가 아닙니다.

2026-10-19에 서울 열린데이터광장 OA-12913의 **2026년 9월 CSV 원본 42,155행**을 내려받았습니다. 수집 시점·SHA-256·실제 컬럼은 `data/raw/boarding_202609.csv.manifest.json`에 기록했습니다. 파일은 월별 정류장·노선·시간대 카드 이용 합계이며 차량별 승하차 기록이 아닙니다.

## 제출 전 보완 결과 (2026-10-21)

최신 작성 근거는 [보고서 자료 묶음](docs/report_materials.md), [전체 정책 비교와 검증 수치](docs/results_submission_20261021/summary.md), [시범 운영안](docs/pilot_design.md), [검증 기록](docs/verification.md), [AI 활용 기록](docs/ai_usage.md)입니다. 기존 `docs/results/`와 `outputs/baseline/`은 이전 결과로 보존합니다.

새 실행은 원본부터 23개 설정 × 5정책을 분석합니다. 각 설정의 전체 정책 합계와 악화 분모, 전체 정류장 순위, 기준 전 셀 및 다른 설정의 상위 K 정류장 상세를 공개합니다. 문헌 보정 없는 탐색 모형이며 효과의 실증 검증이 아닙니다.

```bash
cd seoul-all-door-boarding
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements.lock.txt
.venv/bin/python -m src.collect --register-existing
.venv/bin/python -m pytest -q
.venv/bin/python -m src.review_analysis --output outputs/submission_reproduction
.venv/bin/python -m src.submission_materials --run outputs/submission_reproduction --destination docs/results_reproduction
```

기존 공식 원본을 등록하거나, 원본이 없으면 `src.collect`가 설정된 공식 파일 수집을 시도합니다. 네트워크 실패 시 자동 대체하지 않습니다. 출력 경로가 이미 채워져 있으면 실패하므로 새 경로를 사용하세요. 이 작업의 새 환경은 `/tmp/seoul-submission-venv/bin/python`, 전체 결과는 `outputs/submission_20261021/`, 공개 근거는 `docs/results_submission_20261021/`입니다. 한글 폰트는 `assets/NanumGothic-Regular.ttf`를 명시적으로 사용하며 OFL 라이선스를 동봉합니다.

## 기존 MVP 실행

Python **3.12** 권장. 기본 환경의 Python 3.14는 이 의존성 조합의 검증 대상이 아닙니다.

```bash
cd seoul-all-door-boarding
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.lock.txt
python -m src.collect
python -m src.pipeline --output outputs/baseline
python -m src.export_report --run outputs/baseline --destination docs/results-new
python -m pytest -q
```

현재 작업 공간에서는 다음으로 바로 실행할 수 있습니다.

```bash
/tmp/seoul-adb-py312/bin/python -m pytest -q
# 기존 결과를 보존하므로 재실행은 새 디렉터리 사용
/tmp/seoul-adb-py312/bin/python -m src.pipeline --output outputs/reproduction
```

인증키 없이 공식 파일을 받습니다. 네트워크가 제한된 환경에서는 공식 페이지에서 같은 월 파일을 받아 `data/raw/boarding_202609.csv`에 놓고 `python -m src.collect --register-existing`을 실행합니다. 원본이 이미 등록되면 SHA-256을 확인하며 덮어쓰지 않습니다. 다운로드 주소·POST 매개변수는 확인한 공식 페이지 폼에서 가져왔습니다. 월을 변경할 때는 공식 페이지에서 해당 파일의 `seq`를 확인하고 설정의 월과 함께 바꿉니다. 임의 URL 추측이나 합성 데이터로의 자동 대체는 없습니다.

## 결과 확인

- `outputs/baseline/summary.md`: 관측 수요와 가정 기반 결과를 구분한 실행 보고서
- `outputs/baseline/figures/`: 시간대 수요, 상위 정류장, 노선 집중도, 피크 후보, 히트맵, 누적 집중도 PNG 6종
- `outputs/baseline/figures/simulated_savings_surface.png`: 승차 수·하차 수·뒷문 이용률에 따른 가정 모형의 절감/지연 영역
- `outputs/baseline/*scenarios.csv`: 정류장·노선·상위 셀의 가정 기반 결과
- `outputs/baseline/*sensitivity_range.csv`: 가정 조합 최솟값·최댓값. 통계적 신뢰구간 아님
- `outputs/baseline/pilot_candidates.csv`: 선택적 전 문 승차의 현장 검증 후보
- `outputs/baseline/policy_costs_and_risks.csv`: 미확인 비용을 빈 값으로 둔 평가표
- `outputs/baseline/quality_report.json`, `run_manifest.json`: 품질, 설정, 입력·코드 해시 및 버전
- `data/processed/boarding_long_202609.csv.gz`: 검증 후 시간대별 긴 형식 자료

대형 원본·중간 산출물·재생성 가능한 결과는 Git에서 제외합니다. 검증된 실행의 작은 결과 요약과 그림은 `docs/results/`에 보존합니다. 전체 결과는 위 명령으로 재생성할 수 있습니다.

다운로드 원본의 SHA-256도 설정에 고정했습니다. 제공기관이 같은 파일을 수정하면 수집을 중단합니다. 다른 월이나 수정본을 사용하려면 원본과 기간을 검토한 뒤 `expected_sha256`과 수집 설정을 함께 갱신하세요. 기존 검증 스냅샷과 혼합하지 마세요.

## 분석 범위와 해석

기본 범위는 실제 원본 코드 `010` 간선, `020` 지선, `040` 순환입니다. 마을·광역·심야·기타는 제외하며 설정으로 변경할 수 있습니다. 서울버스가 경기도 등에서 정차하는 기록을 포함할 수 있어 서울 행정경계 내부만의 수요라고 부르지 않습니다. 좌표 미확보로 행정경계 필터는 적용하지 않았습니다.

정책은 현행, 제한적 뒷문 승차, 전 문 확대, 피크 시간·수요 상위 셀의 선택적 시행을 비교합니다. 처리시간·혼잡·문 간 간섭·이동약자 추가시간과 시간당 정차횟수는 모두 **보정되지 않은 가정**입니다. 시나리오 명칭 Conservative/Base/Optimistic은 가정 묶음이며 모든 정류장에서 효과의 순서를 보장하지 않습니다. 손실을 0으로 잘라내지 않습니다.

월 집계를 달력 일수와 가정 운행횟수로 나눠 평균 이벤트 부하를 만듭니다. 평일·주말 차이, 차량 간 편차, 대기열, 만차에 따른 미승차는 추정하지 않습니다. 버스 1회/왕복 시간 절감과 승객 시간편익은 방향별 운행과 재차인원 없이는 계산하지 않습니다. 노선별 수치는 승객 활동이 관측된 셀에 대한 조건부 누적값입니다.

## 실제 정차 기록 추가 (Plan A/B)

`docs/data_dictionary.md`의 **내부 입력 계약**에 맞게 별도 확보한 이벤트를 변환합니다. 이는 공개 API의 실제 컬럼이라고 주장하는 형식이 아닙니다.

```bash
python -m src.pipeline --output outputs/with_events --events /path/to/normalized_events.csv
```

도착·출발 차이, 품질 격리, 체류시간 분포, 관측 배차간격을 계산합니다. 월 전체의 모든 운행이 포함되고 노선·정류장 ID 매핑 및 시간 정의를 확인한 경우에만 `--verified-complete-month-coverage`를 추가해 동일 집계 단위의 관계 회귀를 실행합니다. 결측/이상 이벤트가 제외된 경우에도 완전성이 성립하는지 다시 판단해야 합니다. 집계 관계는 인과적 정책 효과가 아닙니다. 고차원 고정효과 회귀는 범위를 먼저 제한하고 충분한 표본·노선 군집을 확보해야 합니다.

자료·모형·추가 조사 계획은 [데이터 출처](docs/data_sources.md), [자료사전](docs/data_dictionary.md), [방법론](docs/methodology.md), [한계](docs/limitations.md)를 참조하세요.
