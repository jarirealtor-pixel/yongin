#!/usr/bin/env python3
"""
국토부 실거래가 API → data/complexes.json + data/transactions.json
수지구(41465) | 최근 6개월
"""
import os, json, time, requests
from datetime import datetime, timedelta
from collections import defaultdict
from urllib.parse import unquote

# API 키 — URL 인코딩된 키도 자동 처리
_RAW_KEY = os.environ.get("MOLIT_API_KEY", "")
API_KEY  = unquote(_RAW_KEY)  # 이중 인코딩 방지

TRADE_URL = "http://openapi.molit.go.kr/OpenAPI_ToolInstallPackage/service/rest/RTMSOBJSvc/getRTMSDataSvcAptTrade"
RENT_URL  = "http://openapi.molit.go.kr/OpenAPI_ToolInstallPackage/service/rest/RTMSOBJSvc/getRTMSDataSvcAptRent"

# 수지구 읍면동 코드 (5자리)
SUJI_DONGS = {
    "풍덕천동": "4146510200",
    "죽전동":   "4146510300",
    "동천동":   "4146510400",
    "성복동":   "4146510500",
    "신봉동":   "4146510600",
    "상현동":   "4146510700",
}
# 시군구 코드 (5자리) — 전체 수지구
DIST_CODE = "41465"

def get_months(n=6):
    months, d = [], datetime.now()
    for _ in range(n):
        months.append(d.strftime("%Y%m"))
        d = d.replace(day=1) - timedelta(days=1)
    return months

def area_bin(a):
    try:
        f = float(str(a).strip())
        if f < 50:    return "40"
        elif f < 66:  return "59"
        elif f < 80:  return "74"
        elif f < 96:  return "84"
        elif f < 130: return "114"
        else:         return "135"
    except: return "84"

def fetch(url, params, retries=3):
    for i in range(retries):
        try:
            r = requests.get(url, params=params, timeout=30)
            print(f"    HTTP {r.status_code} ({len(r.content)}B)")
            if r.status_code == 200:
                return r.content
        except Exception as e:
            print(f"    오류: {e}")
        time.sleep(2)
    return None

def parse_items(content):
    import xml.etree.ElementTree as ET
    try:
        root = ET.fromstring(content)
        # 결과 코드 확인
        result_code = root.findtext(".//resultCode") or ""
        result_msg  = root.findtext(".//resultMsg") or ""
        if result_code not in ("00", "0000", ""):
            print(f"    API 오류: [{result_code}] {result_msg}")
        items = root.findall(".//item")
        return items
    except Exception as e:
        print(f"    XML 파싱 오류: {e}")
        return []

def g(item, tag):
    el = item.find(tag)
    return el.text.strip() if el is not None and el.text else ""

def collect():
    months = get_months(6)
    print(f"수집 기간: {months[-1]} ~ {months[0]}")
    trades, rents = [], []

    for ym in months:
        # 매매
        print(f"\n  [{ym}] 매매 수집...")
        content = fetch(TRADE_URL, {
            "serviceKey": API_KEY,
            "LAWD_CD":    DIST_CODE,
            "DEAL_YMD":   ym,
            "numOfRows":  1000,
            "pageNo":     1,
        })
        if content:
            items = parse_items(content)
            print(f"    → {len(items)}건")
            for item in items:
                price_raw = g(item,"거래금액").replace(",","").replace(" ","")
                try:    price = int(price_raw) * 10000
                except: continue
                trades.append({
                    "name":     g(item,"아파트"),
                    "dong":     g(item,"법정동"),
                    "year":     g(item,"년"),
                    "month":    g(item,"월"),
                    "day":      g(item,"일"),
                    "floor":    g(item,"층"),
                    "area":     g(item,"전용면적"),
                    "areaBin":  area_bin(g(item,"전용면적")),
                    "price":    price,
                    "builtYear":g(item,"건축년도"),
                    "ym":       ym,
                })

        # 전월세
        print(f"  [{ym}] 전월세 수집...")
        content = fetch(RENT_URL, {
            "serviceKey": API_KEY,
            "LAWD_CD":    DIST_CODE,
            "DEAL_YMD":   ym,
            "numOfRows":  1000,
            "pageNo":     1,
        })
        if content:
            items = parse_items(content)
            print(f"    → {len(items)}건")
            for item in items:
                dep_raw = g(item,"보증금액").replace(",","").replace(" ","")
                mon_raw = g(item,"월세금액").replace(",","").replace(" ","")
                try:    dep = int(dep_raw) * 10000
                except: continue
                try:    mon = int(mon_raw) * 10000 if mon_raw and mon_raw!="0" else 0
                except: mon = 0
                rents.append({
                    "name":    g(item,"아파트"),
                    "dong":    g(item,"법정동"),
                    "year":    g(item,"년"),
                    "month":   g(item,"월"),
                    "floor":   g(item,"층"),
                    "area":    g(item,"전용면적"),
                    "areaBin": area_bin(g(item,"전용면적")),
                    "deposit": dep,
                    "monthly": mon,
                    "type":    "월세" if mon > 0 else "전세",
                    "ym":      ym,
                })
        time.sleep(0.5)

    print(f"\n총 수집: 매매 {len(trades)}건 / 전월세 {len(rents)}건")
    return trades, rents

def build_complexes(trades, rents):
    cx = defaultdict(lambda: {
        "dong":"","builtYear":"",
        "sales":defaultdict(list),
        "jeons":defaultdict(list),
        "wolses":defaultdict(list),
    })
    for t in trades:
        c = cx[t["name"]]
        if t["dong"]: c["dong"] = t["dong"]
        if t["builtYear"]: c["builtYear"] = t["builtYear"]
        c["sales"][t["areaBin"]].append(t["price"])
    for r in rents:
        c = cx[r["name"]]
        if not c["dong"] and r["dong"]: c["dong"] = r["dong"]
        if r["type"] == "전세":
            c["jeons"][r["areaBin"]].append(r["deposit"])
        else:
            c["wolses"][r["areaBin"]].append((r["deposit"], r["monthly"]))

    # 읍면동별 그룹
    dong_groups = defaultdict(list)
    for name, c in cx.items():
        total = sum(len(v) for v in c["sales"].values())
        if total < 1: continue
        types, bp = [], {}
        for ab, prices in c["sales"].items():
            types.append(ab)
            bp[int(ab)] = round(sum(prices)/len(prices)/100)*100
        if not bp: continue

        # 전세가율
        rr = 0.63
        bp84 = bp.get(84, list(bp.values())[0])
        j84 = c["jeons"].get("84", [])
        if j84 and bp84:
            rr = round(min(0.85, max(0.40, (sum(j84)/len(j84))/bp84)), 2)

        dong = c["dong"] or "기타"
        dong_groups[dong].append({
            "name":       name,
            "year":       int(c["builtYear"]) if c["builtYear"] else None,
            "types":      sorted(types, key=lambda x: int(x)),
            "bp":         bp,
            "rr":         rr,
            "tradeCount": total,
        })

    # 거래건수 내림차순
    for d in dong_groups:
        dong_groups[d].sort(key=lambda x: -x["tradeCount"])

    return {"수지구": dict(dong_groups)}

def build_tx(trades, rents):
    data, rent = defaultdict(list), defaultdict(list)
    for t in trades:
        data[t["name"]].append({k:t[k] for k in ["year","month","floor","areaBin","price","ym"]})
    for r in rents:
        rent[r["name"]].append({k:r[k] for k in ["year","month","areaBin","deposit","monthly","type","ym"]})
    return dict(data), dict(rent)

def main():
    if not API_KEY:
        print("⚠️  API 키 없음")
        return

    print(f"API 키: {API_KEY[:8]}...{API_KEY[-4:]} (길이:{len(API_KEY)})")

    trades, rents = collect()

    if not trades and not rents:
        print("❌ 데이터 없음 — API 키 또는 코드 문제")
        return

    districts = build_complexes(trades, rents)
    tx_data, tx_rent = build_tx(trades, rents)

    total_cx = sum(len(v) for d in districts.values() for v in d.values())
    print(f"\n단지 수: {total_cx}개")

    now = datetime.now().isoformat()
    os.makedirs("data", exist_ok=True)

    with open("data/complexes.json","w",encoding="utf-8") as f:
        json.dump({"source":"molit_api","updated":now,"districts":districts},
                  f, ensure_ascii=False, indent=2)
    with open("data/transactions.json","w",encoding="utf-8") as f:
        json.dump({"source":"molit_api","updated":now,
                   "data":tx_data,"rent":tx_rent},
                  f, ensure_ascii=False, indent=2)

    tc = sum(len(v) for v in tx_data.values())
    rc = sum(len(v) for v in tx_rent.values())
    print(f"✓ complexes.json: {total_cx}개 단지")
    print(f"✓ transactions.json: 매매 {tc}건 / 전월세 {rc}건")

if __name__ == "__main__":
    main()
