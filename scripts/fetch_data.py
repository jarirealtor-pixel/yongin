"""
용인시 실거래가 자동 수집 스크립트
- 국토교통부 공장창고 매매 + 상업업무용 매매 API 호출
- 최근 3년치 데이터를 용인시 3개구(처인/기흥/수지)에 대해 수집
- 동별 집계 + 좌표 매핑 + 개별 거래 내역을 data.json으로 저장
"""

import os
import sys
import json
import time
from datetime import datetime
from dateutil.relativedelta import relativedelta
import pandas as pd
from PublicDataReader import TransactionPrice

# ============================================================
# 설정
# ============================================================
SERVICE_KEY = os.environ.get('MOLIT_API_KEY')
if not SERVICE_KEY:
    print('❌ MOLIT_API_KEY 환경변수가 없습니다. GitHub Secrets에 등록하세요.')
    sys.exit(1)

# 용인시 시군구코드 (행정표준코드 앞5자리)
SIGUNGU = {
    '41461': '처인구',
    '41463': '기흥구',
    '41465': '수지구',
}

# 수집 기간: 최근 3년 (오늘 기준)
END = datetime.now()
START = END - relativedelta(years=3)

def month_range(start, end):
    cur = start.replace(day=1)
    out = []
    while cur <= end:
        out.append(cur.strftime('%Y%m'))
        cur += relativedelta(months=1)
    return out

MONTHS = month_range(START, END)
print(f'📅 수집 기간: {MONTHS[0]} ~ {MONTHS[-1]} ({len(MONTHS)}개월)')

# 용인시 동/리 좌표 (대시보드 지도용)
COORDS = {
    # 기흥구
    '영덕동':(37.2862,127.1038),'중동':(37.2745,127.1162),'농서동':(37.2705,127.0875),
    '구갈동':(37.2759,127.1142),'청덕동':(37.3017,127.1114),'고매동':(37.2356,127.0931),
    '상하동':(37.2480,127.1128),'공세동':(37.2412,127.0886),'보라동':(37.2597,127.1135),
    '언남동':(37.2824,127.1224),'마북동':(37.2930,127.1279),'신갈동':(37.2836,127.1105),
    '하갈동':(37.2585,127.1042),'상갈동':(37.2690,127.0992),'지곡동':(37.2350,127.1070),
    '서천동':(37.2540,127.0750),'보정동':(37.3207,127.1104),'동백동':(37.2730,127.1535),
    '기흥동':(37.2820,127.1154),
    # 수지구
    '상현동':(37.3124,127.0944),'동천동':(37.3350,127.0785),'죽전동':(37.3244,127.1076),
    '풍덕천동':(37.3221,127.0970),'성복동':(37.3180,127.0823),'신봉동':(37.3260,127.0710),
    '고기동':(37.3410,127.0650),
    # 처인구 동
    '유방동':(37.2480,127.1910),'삼가동':(37.2197,127.1830),'역북동':(37.2340,127.2020),
    '남동':(37.2180,127.2230),'마평동':(37.2280,127.2100),'김량장동':(37.2365,127.2095),
    '고림동':(37.2500,127.2150),'운학동':(37.2200,127.2400),
    # 처인구 양지면
    '주북리':(37.2335,127.2790),'남곡리':(37.2280,127.2850),'양지리':(37.2460,127.2800),
    '평창리':(37.2670,127.2910),'대대리':(37.2550,127.2700),'식금리':(37.2500,127.2920),
    '추계리':(37.2350,127.2650),
    # 모현읍
    '초부리':(37.3080,127.2260),'일산리':(37.2760,127.2540),'능원리':(37.3050,127.2170),
    '왕산리':(37.3160,127.2380),'오산리':(37.3230,127.2700),'동림리':(37.3100,127.2300),
    # 포곡읍
    '금어리':(37.2850,127.2400),'삼계리':(37.3000,127.2500),'신원리':(37.2900,127.2350),
    '영문리':(37.2950,127.2280),'유운리':(37.2820,127.2450),
    # 원삼면
    '가재월리':(37.1950,127.3100),'고당리':(37.1850,127.3200),'두창리':(37.1900,127.3350),
    '맹리':(37.1750,127.3250),'문촌리':(37.2000,127.3150),'학일리':(37.1800,127.3400),
    '창리':(37.1900,127.3350),
    # 백암면
    '가좌리':(37.1650,127.3900),'가창리':(37.1700,127.4000),'고안리':(37.1550,127.3950),
    '근곡리':(37.1600,127.4100),'박곡리':(37.1500,127.4000),'백암리':(37.1630,127.4050),
    '석천리':(37.1680,127.3850),'옥산리':(37.1720,127.3950),'장평리':(37.1550,127.4150),
    # 이동읍
    '근삼리':(37.1250,127.2960),'근창리':(37.1320,127.3010),'백봉리':(37.0990,127.3070),
    '미평리':(37.1170,127.3420),'북리':(37.1850,127.3540),'방아리':(37.2020,127.3220),
    '사암리':(37.1750,127.3140),'매산리':(37.2040,127.3150),'제일리':(37.1350,127.2580),
    '덕성리':(37.1400,127.2400),'묘봉리':(37.1300,127.2500),'묵리':(37.1450,127.2550),
    '서리':(37.1550,127.2300),'송전리':(37.1200,127.2350),'천리':(37.1380,127.2450),
    '어비리':(37.1780,127.3300),'목신리':(37.1700,127.3600),'월곡리':(37.1550,127.3680),
    '갈담리':(37.1600,127.2700),'상미리':(37.1920,127.2920),'좌항리':(37.2560,127.2960),
    # 남사읍
    '봉명리':(37.1050,127.1600),'봉무리':(37.1100,127.1700),'완장리':(37.1000,127.1550),
    '통삼리':(37.0950,127.1650),
}

# ============================================================
# API 호출
# ============================================================
api = TransactionPrice(SERVICE_KEY)

def fetch_property(prop_type, label):
    """특정 부동산 유형의 모든 시군구 × 모든 월 데이터 수집"""
    print(f'\n🔄 [{label}] 수집 시작')
    all_dfs = []
    total_calls = len(SIGUNGU) * len(MONTHS)
    done = 0
    for code, gu_name in SIGUNGU.items():
        for ym in MONTHS:
            done += 1
            try:
                df = api.get_data(
                    property_type=prop_type,
                    trade_type='매매',
                    sigungu_code=code,
                    year_month=ym,
                )
                if df is not None and len(df) > 0:
                    df['_category'] = label
                    df['_gu'] = gu_name
                    all_dfs.append(df)
                if done % 20 == 0:
                    print(f'  진행 {done}/{total_calls} … 누적 {sum(len(d) for d in all_dfs)}건')
            except Exception as e:
                print(f'  ⚠️ {gu_name} {ym} 실패: {e}')
            time.sleep(0.05)  # rate limit 안전장치
    if not all_dfs:
        print(f'  ℹ️ [{label}] 수집된 데이터 없음')
        return pd.DataFrame()
    out = pd.concat(all_dfs, ignore_index=True)
    print(f'  ✅ [{label}] 총 {len(out)}건')
    return out

df_factory = fetch_property('공장창고등', '공장창고')
df_commerce = fetch_property('상업업무용', '상업업무용')

# ============================================================
# 컬럼 정규화 (PublicDataReader는 한글/영문 컬럼을 다양하게 반환)
# ============================================================
def normalize(df):
    if df.empty:
        return df
    # 가능한 컬럼명 매핑 (PublicDataReader / API 응답 변형 대응)
    rename_map = {}
    cols = df.columns.tolist()
    
    def find_col(*candidates):
        for c in candidates:
            if c in cols:
                return c
        return None
    
    mapping = {
        '시군구': find_col('시군구', 'sggNm'),
        '법정동': find_col('법정동', 'umdNm'),
        '도로명': find_col('도로명', 'roadNm'),
        '지번': find_col('지번', 'jibun'),
        '건축물주용도': find_col('건축물주용도', '건물주용도', 'bldUsg', 'buildingUse'),
        '용도지역': find_col('용도지역', 'landUsg'),
        '유형': find_col('유형', 'buildingType'),
        '연면적': find_col('전용면적', '연면적', '전용/연면적', 'buildingAr', 'excluUseAr'),
        '대지면적': find_col('대지면적', 'plottageAr'),
        '거래금액': find_col('거래금액', 'dealAmount'),
        '계약년도': find_col('계약년도', 'dealYear'),
        '계약월': find_col('계약월', 'dealMonth'),
        '계약일': find_col('계약일', 'dealDay'),
        '건축년도': find_col('건축년도', 'buildYear'),
        '도로조건': find_col('도로조건', 'roadCond'),
    }
    out = pd.DataFrame()
    for tgt, src in mapping.items():
        if src and src in df.columns:
            out[tgt] = df[src]
        else:
            out[tgt] = None
    out['_category'] = df.get('_category')
    out['_gu'] = df.get('_gu')
    return out

n_factory = normalize(df_factory)
n_commerce = normalize(df_commerce)

# ============================================================
# 상업업무용에서 "근생 제조업소 후보"만 추출
#  - 건축물주용도: 제2종근린생활시설 또는 제1종근린생활시설
#  - (필터링은 대시보드에서 추가로 수행)
# ============================================================
if not n_commerce.empty:
    mask = n_commerce['건축물주용도'].astype(str).str.contains('근린생활', na=False)
    n_commerce = n_commerce[mask].copy()
    print(f'\n🏪 상업업무용 → 근린생활시설만: {len(n_commerce)}건')

# 병합
df = pd.concat([n_factory, n_commerce], ignore_index=True)
print(f'\n📦 총 병합 데이터: {len(df)}건')

if df.empty:
    print('❌ 수집된 데이터가 없습니다. API 키 또는 설정을 확인하세요.')
    sys.exit(1)

# ============================================================
# 정제
# ============================================================
df['거래금액'] = pd.to_numeric(df['거래금액'].astype(str).str.replace(',', '').str.strip(), errors='coerce')
df['연면적'] = pd.to_numeric(df['연면적'], errors='coerce')
df['대지면적'] = pd.to_numeric(df['대지면적'], errors='coerce')
df['단가'] = df['거래금액'] / df['연면적']
df['계약년월'] = df['계약년도'].astype(str).str.zfill(4) + df['계약월'].astype(str).str.zfill(2)
df['년'] = df['계약년월'].str[:4]

# 동 추출
def get_dong(row):
    # API의 법정동 컬럼 우선, 없으면 시군구 마지막 토큰
    d = row.get('법정동')
    if d and str(d).strip() and str(d) != 'nan':
        return str(d).strip()
    s = str(row.get('시군구', ''))
    parts = s.split()
    return parts[-1] if parts else ''

df['동'] = df.apply(get_dong, axis=1)
df['구'] = df['_gu']

# 중복 제거
df = df.drop_duplicates(subset=['시군구','동','지번','거래금액','계약년월','연면적'], keep='first')
print(f'중복 제거 후: {len(df)}건')

# ============================================================
# 동별 집계 (좌표 포함)
# ============================================================
agg = df.groupby(['구','동']).agg(
    count=('거래금액','size'),
    avg_price=('거래금액','mean'),
    median_price=('거래금액','median'),
    avg_area=('연면적','mean'),
    avg_unit=('단가','median'),
    total=('거래금액','sum'),
    ilban=('유형', lambda s: (s.astype(str)=='일반').sum()),
    jiphap=('유형', lambda s: (s.astype(str)=='집합').sum()),
    factory=('_category', lambda s: (s=='공장창고').sum()),
    commerce=('_category', lambda s: (s=='상업업무용').sum()),
).reset_index()
agg['lat'] = agg['동'].map(lambda d: COORDS.get(d, (None, None))[0])
agg['lng'] = agg['동'].map(lambda d: COORDS.get(d, (None, None))[1])

# 좌표 없는 동 경고
missing = agg[agg['lat'].isna()]['동'].tolist()
if missing:
    print(f'⚠️ 좌표 누락 동/리: {missing}')

agg_c = agg.dropna(subset=['lat']).sort_values('count', ascending=False)
covered = df[df['동'].isin(agg_c['동'])].shape[0]
print(f'지도 커버리지: {covered}/{len(df)} ({covered/max(len(df),1)*100:.1f}%)')

# ============================================================
# JSON 직렬화
# ============================================================
def clean_record(r):
    out = {}
    for k, v in r.items():
        if pd.isna(v):
            out[k] = None
        elif isinstance(v, float):
            out[k] = round(v, 2)
        else:
            out[k] = v
    return out

year_dict = df.groupby('년').size().astype(int).to_dict()
gu_dict = {}
for g, sub in df.groupby('구'):
    gu_dict[g] = {
        '건수': int(len(sub)),
        '평균가': round(sub['거래금액'].mean(), 1) if len(sub) else 0,
        '중위가': round(sub['거래금액'].median(), 1) if len(sub) else 0,
        '평균면적': round(sub['연면적'].mean(), 1) if len(sub) else 0,
    }
use_dict = df['건축물주용도'].fillna('미상').value_counts().astype(int).to_dict()
type_dict = df['유형'].fillna('미상').value_counts().astype(int).to_dict()
cat_dict = df['_category'].value_counts().astype(int).to_dict()

tx_cols = ['구','동','유형','건축물주용도','용도지역','연면적','대지면적','거래금액','계약년월','건축년도','도로명','_category']
tx_records = [clean_record(r) for r in df[tx_cols].to_dict(orient='records')]

# 필드명 _category → category로
for r in tx_records:
    r['category'] = r.pop('_category', None)

dong_records = [clean_record(r) for r in agg_c.to_dict(orient='records')]

data = {
    'updated_at': datetime.now().strftime('%Y-%m-%d %H:%M'),
    'period': f'{MONTHS[0]} ~ {MONTHS[-1]}',
    'total': int(len(df)),
    'covered': int(covered),
    'dong': dong_records,
    'year': {k: int(v) for k, v in year_dict.items()},
    'gu': gu_dict,
    'use': use_dict,
    'type': type_dict,
    'category': cat_dict,
    'tx': tx_records,
}

with open('data.json', 'w', encoding='utf-8') as f:
    json.dump(data, f, ensure_ascii=False, default=str)

print(f'\n✅ data.json 저장 완료 ({len(tx_records)}건, {len(dong_records)}동)')
