#!/usr/bin/env python3
"""
국토부 실거래가 API → data/complexes.json + data/transactions.json
수지구(41465) 전용 | 최근 6개월
"""
import os, json, time, requests
from datetime import datetime, timedelta
from collections import defaultdict

API_KEY   = os.environ.get("MOLIT_API_KEY", "")
TRADE_URL = "http://openapi.molit.go.kr/OpenAPI_ToolInstallPackage/service/rest/RTMSOBJSvc/getRTMSDataSvcAptTrade"
RENT_URL  = "http://openapi.molit.go.kr/OpenAPI_ToolInstallPackage/service/rest/RTMSOBJSvc/getRTMSDataSvcAptRent"
DIST_CODE = "41465"   # 수지구
DIST_NAME = "수지구"

def get_months(n=6):
    months, d = [], datetime.now()
    for _ in range(n):
        months.append(d.strftime("%Y%m"))
        d = d.replace(day=1) - timedelta(days=1)
    return months

def area_bin(a):
    try:
        f = float(str(a).strip())
        if f < 50:   return "40"
        elif f < 66: return "59"
        elif f < 80: return "74"
        elif f < 96: return "84"
        elif f < 130:return "114"
        else:        return "135"
    except: return "84"

def fetch_xml(url, params, retries=3):
    for i in range(retries):
        try:
            r = requests.get(url, params=params, timeout=30)
            r.raise_for_status()
            return r.content
        except Exception as e:
            print(f"  재시도 {i+1}: {e}")
            time.sleep(2)
    return None

def parse_items(content):
    import xml.etree.ElementTree as ET
    try:
        root = ET.fromstring(content)
        return root.findall(".//item")
    except: return []

def get(item, tag):
    el = item.find(tag)
    return el.text.strip() if el is not None and el.text else ""

def collect_trades():
    trades, rents = [], []
    months = get_months(6)
    for ym in months:
        print(f"  매매 {ym}...")
        content = fetch_xml(TRADE_URL, {
            "serviceKey": API_KEY, "LAWD_CD": DIST_CODE,
            "DEAL_YMD": ym, "numOfRows": 1000, "pageNo": 1
        })
        if content:
            for item in parse_items(content):
                price_raw = get(item,"거래금액").replace(",","").replace(" ","")
                try:    price = int(price_raw) * 10000
                except: continue
                trades.append({
                    "name":    get(item,"아파트"),
                    "dong":    get(item,"법정동"),
                    "year":    get(item,"년"),
                    "month":   get(item,"월"),
                    "floor":   get(item,"층"),
                    "area":    get(item,"전용면적"),
                    "areaBin": area_bin(get(item,"전용면적")),
                    "price":   price,
                    "builtYear":get(item,"건축년도"),
                    "ym":      ym,
                })
        print(f"  전월세 {ym}...")
        content = fetch_xml(RENT_URL, {
            "serviceKey": API_KEY, "LAWD_CD": DIST_CODE,
            "DEAL_YMD": ym, "numOfRows": 1000, "pageNo": 1
        })
        if content:
            for item in parse_items(content):
                dep_raw = get(item,"보증금액").replace(",","").replace(" ","")
                mon_raw = get(item,"월세금액").replace(",","").replace(" ","")
                try:    dep = int(dep_raw)*10000
                except: continue
                try:    mon = int(mon_raw)*10000 if mon_raw and mon_raw!="0" else 0
                except: mon = 0
                rents.append({
                    "name":    get(item,"아파트"),
                    "dong":    get(item,"법정동"),
                    "year":    get(item,"년"),
                    "month":   get(item,"월"),
                    "floor":   get(item,"층"),
                    "area":    get(item,"전용면적"),
                    "areaBin": area_bin(get(item,"전용면적")),
                    "deposit": dep,
                    "monthly": mon,
                    "type":    "월세" if mon>0 else "전세",
                    "ym":      ym,
                })
        time.sleep(0.3)
    return trades, rents

def build_complexes(trades, rents):
    cx_map = defaultdict(lambda: {
        "dong":"","builtYear":"",
        "trades":defaultdict(list),
        "rents_j":defaultdict(list),
        "rents_w":defaultdict(list),
    })
    for t in trades:
        c = cx_map[t["name"]]
        c["dong"] = t["dong"]
        if t["builtYear"]: c["builtYear"] = t["builtYear"]
        c["trades"][t["areaBin"]].append(t["price"])
    for r in rents:
        c = cx_map[r["name"]]
        if not c["dong"]: c["dong"] = r["dong"]
        if r["type"]=="전세":
            c["rents_j"][r["areaBin"]].append(r["deposit"])
        else:
            c["rents_w"][r["areaBin"]].append((r["deposit"],r["monthly"]))

    # 읍면동별 그룹 (단순히 수지구 하나로)
    dong_map = defaultdict(list)
    for name, c in cx_map.items():
        total = sum(len(v) for v in c["trades"].values())
        if total < 2: continue

        types, bp, rr_map = [], {}, {}
        for ab, prices in c["trades"].items():
            if not prices: continue
            types.append(ab)
            bp[int(ab)] = round(sum(prices)/len(prices)/100)*100

        # 전세가율
        rr = 0.63
        bp84 = bp.get(84, list(bp.values())[0] if bp else 70000)
        j84 = c["rents_j"].get("84",[])
        if j84 and bp84:
            avg_j = sum(j84)/len(j84)
            rr = min(0.82, max(0.40, round(avg_j/bp84,2)))

        dong = c["dong"] or "기타"
        dong_map[dong].append({
            "name":       name,
            "year":       int(c["builtYear"]) if c["builtYear"] else None,
            "types":      sorted(types, key=lambda x:int(x)),
            "bp":         bp,
            "rr":         rr,
            "tradeCount": total,
        })

    # 거래건수 내림차순
    for dong in dong_map:
        dong_map[dong].sort(key=lambda x: -x["tradeCount"])

    return {"수지구": dict(dong_map)}

def build_transactions(trades, rents):
    data, rent = defaultdict(list), defaultdict(list)
    for t in trades:
        data[t["name"]].append({
            "year":    t["year"],
            "month":   t["month"],
            "floor":   t["floor"],
            "areaBin": t["areaBin"],
            "price":   t["price"],
            "ym":      t["ym"],
        })
    for r in rents:
        rent[r["name"]].append({
            "year":    r["year"],
            "month":   r["month"],
            "areaBin": r["areaBin"],
            "deposit": r["deposit"],
            "monthly": r["monthly"],
            "type":    r["type"],
            "ym":      r["ym"],
        })
    return dict(data), dict(rent)

def write_demo():
    """API 키 없을 때 — 기존 파일 유지, source만 demo로 표시"""
    now = datetime.now().isoformat()
    demo_cx = {"source":"demo","updated":now,"districts":{"수지구":{"죽전동":[
        {"name":"죽전 힐스테이트","year":2006,"types":["59","74","84"],"bp":{59:63000,74:72000,84:85000},"rr":0.62,"tradeCount":48},
        {"name":"수지 래미안 이스트파크","year":2019,"types":["59","84"],"bp":{59:69000,84:92000},"rr":0.58,"tradeCount":56},
        {"name":"동천디이스트","year":2007,"types":["84"],"bp":{84:93000},"rr":0.62,"tradeCount":35},
        {"name":"성복역롯데캐슬골드타운","year":2019,"types":["84","114"],"bp":{84:138000,114:160000},"rr":0.57,"tradeCount":22},
    ]}}}
    demo_tx = {"source":"demo","updated":now,"data":{},"rent":{}}
    os.makedirs("data", exist_ok=True)
    with open("data/complexes.json","w",encoding="utf-8") as f:
        json.dump(demo_cx,f,ensure_ascii=False,indent=2)
    with open("data/transactions.json","w",encoding="utf-8") as f:
        json.dump(demo_tx,f,ensure_ascii=False,indent=2)
    print("✓ 데모 데이터 저장")

def main():
    if not API_KEY:
        print("⚠️  MOLIT_API_KEY 없음 → 데모 데이터")
        write_demo()
        return

    print(f"수지구 실거래가 수집 시작 (최근 6개월)")
    trades, rents = collect_trades()
    print(f"\n수집 완료: 매매 {len(trades)}건 / 전월세 {len(rents)}건")

    districts  = build_complexes(trades, rents)
    tx_data, tx_rent = build_transactions(trades, rents)

    now = datetime.now().isoformat()
    total_cx = sum(len(v) for d in districts.values() for v in d.values())

    os.makedirs("data", exist_ok=True)
    with open("data/complexes.json","w",encoding="utf-8") as f:
        json.dump({"source":"molit_api","updated":now,"districts":districts},
                  f, ensure_ascii=False, indent=2)
    with open("data/transactions.json","w",encoding="utf-8") as f:
        json.dump({"source":"molit_api","updated":now,
                   "data":tx_data,"rent":tx_rent},
                  f, ensure_ascii=False, indent=2)

    print(f"✓ complexes.json: {total_cx}개 단지")
    tx_cnt = sum(len(v) for v in tx_data.values())
    rt_cnt = sum(len(v) for v in tx_rent.values())
    print(f"✓ transactions.json: 매매 {tx_cnt}건 / 전월세 {rt_cnt}건")

if __name__ == "__main__":
    main()
