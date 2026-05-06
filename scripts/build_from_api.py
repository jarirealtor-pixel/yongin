#!/usr/bin/env python3
"""국토부 실거래가 API 수집 스크립트"""

import os, json, requests, time
from datetime import datetime, timedelta
from urllib.parse import quote

API_KEY = os.environ.get("MOLIT_API_KEY", "")
TRADE_URL  = "http://openapi.molit.go.kr/OpenAPI_ToolInstallPackage/service/rest/RTMSOBJSvc/getRTMSDataSvcAptTrade"
RENT_URL   = "http://openapi.molit.go.kr/OpenAPI_ToolInstallPackage/service/rest/RTMSOBJSvc/getRTMSDataSvcAptRent"

# 수지구만 수집
DISTRICTS = {
    "수지구": "41465",
}

# 조회 기간 (최근 6개월)
def get_months(n=6):
    months = []
    d = datetime.now()
    for _ in range(n):
        months.append(d.strftime("%Y%m"))
        d = d.replace(day=1) - timedelta(days=1)
    return months

def fetch(url, params, retries=3):
    for i in range(retries):
        try:
            r = requests.get(url, params=params, timeout=30)
            r.raise_for_status()
            return r
        except Exception as e:
            print(f"  재시도 {i+1}/{retries}: {e}")
            time.sleep(2)
    return None

def area_bin(area_str):
    """전용면적 → 타입 분류"""
    try:
        a = float(str(area_str).strip())
        if a < 50:   return "40"
        elif a < 66: return "59"
        elif a < 80: return "74"
        elif a < 96: return "84"
        elif a < 130:return "114"
        else:        return "135"
    except:
        return "84"

def collect_trades(dist_name, dist_code, months):
    trades = []
    for ym in months:
        params = {
            "serviceKey": API_KEY,
            "LAWD_CD": dist_code,
            "DEAL_YMD": ym,
            "numOfRows": 1000,
            "pageNo": 1,
        }
        r = fetch(TRADE_URL, params)
        if not r:
            continue
        try:
            import xml.etree.ElementTree as ET
            root = ET.fromstring(r.content)
            items = root.findall(".//item")
            for item in items:
                def g(tag):
                    el = item.find(tag)
                    return el.text.strip() if el is not None and el.text else ""
                price_raw = g("거래금액").replace(",", "").replace(" ", "")
                try:
                    price = int(price_raw) * 10000  # 만원 → 원
                except:
                    continue
                trades.append({
                    "name":    g("아파트"),
                    "dong":    g("법정동"),
                    "year":    g("년"),
                    "month":   g("월"),
                    "day":     g("일"),
                    "floor":   g("층"),
                    "area":    g("전용면적"),
                    "areaBin": area_bin(g("전용면적")),
                    "price":   price,
                    "dist":    dist_name,
                    "distCode":dist_code,
                    "builtYear":g("건축년도"),
                })
        except Exception as e:
            print(f"  파싱 오류: {e}")
        time.sleep(0.3)
    return trades

def collect_rents(dist_name, dist_code, months):
    rents = []
    for ym in months:
        params = {
            "serviceKey": API_KEY,
            "LAWD_CD": dist_code,
            "DEAL_YMD": ym,
            "numOfRows": 1000,
            "pageNo": 1,
        }
        r = fetch(RENT_URL, params)
        if not r:
            continue
        try:
            import xml.etree.ElementTree as ET
            root = ET.fromstring(r.content)
            items = root.findall(".//item")
            for item in items:
                def g(tag):
                    el = item.find(tag)
                    return el.text.strip() if el is not None and el.text else ""
                dep_raw = g("보증금액").replace(",", "").replace(" ", "")
                mon_raw = g("월세금액").replace(",", "").replace(" ", "")
                try:
                    deposit = int(dep_raw) * 10000
                    monthly = int(mon_raw) * 10000 if mon_raw and mon_raw != "0" else 0
                except:
                    continue
                rtype = "월세" if monthly > 0 else "전세"
                rents.append({
                    "name":    g("아파트"),
                    "dong":    g("법정동"),
                    "year":    g("년"),
                    "month":   g("월"),
                    "floor":   g("층"),
                    "area":    g("전용면적"),
                    "areaBin": area_bin(g("전용면적")),
                    "deposit": deposit,
                    "monthly": monthly,
                    "type":    rtype,
                    "dist":    dist_name,
                })
        except Exception as e:
            print(f"  파싱 오류: {e}")
        time.sleep(0.3)
    return rents

def build_complexes(all_trades, all_rents):
    """단지 목록 생성 (3건 이상 거래된 단지만)"""
    from collections import defaultdict
    cx_map = defaultdict(lambda: {"trades": [], "rents": []})
    for t in all_trades:
        cx_map[t["name"]]["trades"].append(t)
        cx_map[t["name"]]["dist"] = t["dist"]
        cx_map[t["name"]]["dong"] = t["dong"]
        cx_map[t["name"]]["distCode"] = t["distCode"]
        cx_map[t["name"]]["builtYear"] = t.get("builtYear", "")
    for r in all_rents:
        cx_map[r["name"]]["rents"].append(r)

    districts = {}
    for name, v in cx_map.items():
        trades = v["trades"]
        if len(trades) < 2:
            continue
        dist = v.get("dist", "수지구")
        dong = v.get("dong", "")

        # 타입 목록
        types_set = sorted(set(t["areaBin"] for t in trades), key=lambda x: int(x))
        types = [t for t in types_set if types_set.count(t) or True]

        # 타입별 평균가 (bp)
        bp = {}
        for tp in types_set:
            t_prices = [t["price"] for t in trades if t["areaBin"] == tp]
            if t_prices:
                bp[int(tp)] = round(sum(t_prices) / len(t_prices) / 100) * 100

        # 전세가율
        rents_j = [r for r in v["rents"] if r["type"] == "전세"]
        rr = 0.65
        if rents_j and bp.get(84):
            avg_j = sum(r["deposit"] for r in rents_j) / len(rents_j)
            rr = round(avg_j / bp.get(84, avg_j) * 100) / 100

        if dist not in districts:
            districts[dist] = {}
        if dong not in districts[dist]:
            districts[dist][dong] = []

        districts[dist][dong].append({
            "id":         f"cx_{len(districts[dist][dong]):04d}",
            "name":       name,
            "year":       int(v.get("builtYear", 0)) or None,
            "types":      types_set,
            "bp":         bp,
            "rr":         rr,
            "tradeCount": len(trades),
        })

    # 각 동 내 거래건수 내림차순 정렬
    for dist in districts:
        for dong in districts[dist]:
            districts[dist][dong].sort(key=lambda x: -x["tradeCount"])

    return districts

def main():
    if not API_KEY:
        print("⚠️  MOLIT_API_KEY 없음 → 데모 데이터 사용")
        _write_demo()
        return

    months = get_months(6)
    print(f"수집 기간: {months[-1]} ~ {months[0]}")

    all_trades, all_rents = [], []
    trade_by_cx, rent_by_cx = {}, {}

    for dist_name, dist_code in DISTRICTS.items():
        print(f"\n[{dist_name}] 매매 수집 중...")
        trades = collect_trades(dist_name, dist_code, months)
        print(f"  매매 {len(trades)}건")
        all_trades.extend(trades)

        print(f"[{dist_name}] 전월세 수집 중...")
        rents = collect_rents(dist_name, dist_code, months)
        print(f"  전월세 {len(rents)}건")
        all_rents.extend(rents)

    # 단지별 인덱스
    for t in all_trades:
        trade_by_cx.setdefault(t["name"], []).append(t)
    for r in all_rents:
        rent_by_cx.setdefault(r["name"], []).append(r)

    # complexes.json
    districts = build_complexes(all_trades, all_rents)
    complexes_out = {
        "source":    "molit_api",
        "updated":   datetime.now().isoformat(),
        "districts": districts,
    }
    os.makedirs("data", exist_ok=True)
    with open("data/complexes.json", "w", encoding="utf-8") as f:
        json.dump(complexes_out, f, ensure_ascii=False, indent=2)
    print(f"\n✓ complexes.json: {sum(len(v) for d in districts.values() for v in d.values())}개 단지")

    # transactions.json
    tx_out = {
        "source":  "molit_api",
        "updated": datetime.now().isoformat(),
        "data":    trade_by_cx,
        "rent":    rent_by_cx,
    }
    with open("data/transactions.json", "w", encoding="utf-8") as f:
        json.dump(tx_out, f, ensure_ascii=False, indent=2)
    total_t = sum(len(v) for v in trade_by_cx.values())
    total_r = sum(len(v) for v in rent_by_cx.values())
    print(f"✓ transactions.json: 매매 {total_t}건 / 전월세 {total_r}건")


def _write_demo():
    """API 키 없을 때 수지구 전체 단지 데모 데이터"""
    demo = {
        "source": "demo",
        "updated": datetime.now().isoformat(),
        "districts": {
            "수지구": {
                "죽전동": [
                    {"id":"c001","name":"죽전 힐스테이트","year":2006,"types":["59","74","84"],"bp":{59:63000,74:72000,84:85000},"rr":0.62,"tradeCount":48},
                    {"id":"c002","name":"죽전 푸르지오","year":2004,"types":["59","84"],"bp":{59:59000,84:80000},"rr":0.64,"tradeCount":32},
                    {"id":"c003","name":"죽전역 두산위브","year":2008,"types":["59","84"],"bp":{59:61000,84:82000},"rr":0.63,"tradeCount":24},
                    {"id":"c004","name":"죽전 현대홈타운","year":2003,"types":["59","84"],"bp":{59:55000,84:74000},"rr":0.65,"tradeCount":20},
                    {"id":"c005","name":"죽전 삼성래미안","year":2002,"types":["84","114"],"bp":{84:79000,114:108000},"rr":0.64,"tradeCount":18},
                    {"id":"c006","name":"보정 센트럴파크","year":2005,"types":["59","84"],"bp":{59:58000,84:78000},"rr":0.63,"tradeCount":15},
                ],
                "성복동": [
                    {"id":"c010","name":"성복역 롯데캐슬 1단지","year":2019,"types":["59","84","114"],"bp":{59:78000,84:105000,114:138000},"rr":0.55,"tradeCount":22},
                    {"id":"c011","name":"성복역 롯데캐슬 2단지","year":2020,"types":["59","84","114"],"bp":{59:79000,84:107000,114:140000},"rr":0.54,"tradeCount":18},
                    {"id":"c012","name":"성복 힐스테이트","year":2009,"types":["59","84"],"bp":{59:65000,84:88000},"rr":0.60,"tradeCount":26},
                    {"id":"c013","name":"성복 아이파크","year":2011,"types":["59","84"],"bp":{59:64000,84:86000},"rr":0.61,"tradeCount":21},
                    {"id":"c014","name":"성복 e편한세상","year":2013,"types":["59","84"],"bp":{59:62000,84:84000},"rr":0.62,"tradeCount":17},
                ],
                "풍덕천동": [
                    {"id":"c020","name":"수지 래미안 이스트파크","year":2019,"types":["59","84"],"bp":{59:69000,84:92000},"rr":0.58,"tradeCount":56},
                    {"id":"c021","name":"LG자이 수지","year":2003,"types":["59","84"],"bp":{59:56000,84:75000},"rr":0.66,"tradeCount":28},
                    {"id":"c022","name":"수지 한신아파트","year":1997,"types":["59","84"],"bp":{59:48000,84:65000},"rr":0.69,"tradeCount":22},
                    {"id":"c023","name":"수지 삼성아파트","year":1998,"types":["84"],"bp":{84:64000},"rr":0.67,"tradeCount":16},
                    {"id":"c024","name":"풍덕천 현대아파트","year":1996,"types":["84"],"bp":{84:60000},"rr":0.70,"tradeCount":14},
                    {"id":"c025","name":"수지 포스빌","year":2007,"types":["59","84"],"bp":{59:58000,84:78000},"rr":0.64,"tradeCount":19},
                ],
                "동천동": [
                    {"id":"c030","name":"동천 자이","year":2016,"types":["59","74","84"],"bp":{59:68000,74:79000,84:92000},"rr":0.59,"tradeCount":38},
                    {"id":"c031","name":"동천 센트럴자이","year":2019,"types":["59","84"],"bp":{59:70000,84:95000},"rr":0.57,"tradeCount":24},
                    {"id":"c032","name":"동천역 롯데캐슬","year":2020,"types":["59","84","114"],"bp":{59:71000,84:96000,114:128000},"rr":0.57,"tradeCount":20},
                    {"id":"c033","name":"동천 힐스테이트","year":2009,"types":["59","84"],"bp":{59:62000,84:84000},"rr":0.61,"tradeCount":29},
                    {"id":"c034","name":"동천 금호어울림","year":2008,"types":["59","84"],"bp":{59:60000,84:81000},"rr":0.62,"tradeCount":18},
                    {"id":"c035","name":"동천 파크자이","year":2013,"types":["59","84"],"bp":{59:64000,84:86000},"rr":0.61,"tradeCount":22},
                ],
                "상현동": [
                    {"id":"c040","name":"상현 래미안","year":2009,"types":["59","84"],"bp":{59:56500,84:76000},"rr":0.63,"tradeCount":26},
                    {"id":"c041","name":"상현 아이파크","year":2011,"types":["59","84"],"bp":{59:58000,84:78000},"rr":0.62,"tradeCount":22},
                    {"id":"c042","name":"광교산 아이파크","year":2012,"types":["84","114"],"bp":{84:80000,114:108000},"rr":0.60,"tradeCount":18},
                    {"id":"c043","name":"상현 힐스테이트","year":2014,"types":["59","84"],"bp":{59:60000,84:81000},"rr":0.62,"tradeCount":20},
                    {"id":"c044","name":"상현역 롯데캐슬","year":2021,"types":["59","84"],"bp":{59:64000,84:86000},"rr":0.60,"tradeCount":15},
                    {"id":"c045","name":"상현 e편한세상","year":2010,"types":["59","84"],"bp":{59:57000,84:77000},"rr":0.63,"tradeCount":19},
                ],
                "신봉동": [
                    {"id":"c050","name":"신봉 자이","year":2007,"types":["59","84","114"],"bp":{59:60000,84:82000,114:112000},"rr":0.63,"tradeCount":30},
                    {"id":"c051","name":"신봉 래미안","year":2008,"types":["59","84"],"bp":{59:58000,84:79000},"rr":0.64,"tradeCount":24},
                    {"id":"c052","name":"신봉 힐스테이트","year":2010,"types":["59","84"],"bp":{59:59000,84:80000},"rr":0.63,"tradeCount":20},
                    {"id":"c053","name":"신봉 LG자이","year":2006,"types":["59","84"],"bp":{59:57000,84:77000},"rr":0.64,"tradeCount":17},
                ],
                "고기동": [
                    {"id":"c060","name":"수지 광교 힐스테이트","year":2016,"types":["84","114"],"bp":{84:90000,114:122000},"rr":0.58,"tradeCount":16},
                    {"id":"c061","name":"고기 동원로얄듀크","year":2017,"types":["84"],"bp":{84:86000},"rr":0.59,"tradeCount":12},
                ],
            }
        }
    }
    os.makedirs("data", exist_ok=True)
    with open("data/complexes.json", "w", encoding="utf-8") as f:
        json.dump(demo, f, ensure_ascii=False, indent=2)
    tx_demo = {"source":"demo","updated":datetime.now().isoformat(),"data":{},"rent":{}}
    with open("data/transactions.json", "w", encoding="utf-8") as f:
        json.dump(tx_demo, f, ensure_ascii=False, indent=2)
    print("✓ 데모 데이터 생성 완료")


if __name__ == "__main__":
    main()
