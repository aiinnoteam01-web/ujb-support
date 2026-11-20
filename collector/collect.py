"""행정안전부 인허가 API(공공데이터포털)에서 의정부시 음식점·카페·제과점 기록을 받아
data/records.json(원본 정리본), data/sites.json(화면용), data/status.json(수집 현황)을 만듭니다.

- 인증키는 환경변수 DATA_GO_KR_KEY (GitHub Actions Secrets, 청년모아·지원모아와 같은 키)
- 한 출처가 실패하면 그 출처는 이전 records.json 의 자료를 그대로 쓰고 status.json 에 실패로 기록
- 처음 연결할 때:  python collect.py --inspect   (출처별 첫 건의 실제 필드명을 출력)
"""
from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import unquote

import requests
import yaml

import semas
from history import build
from normalize import is_temporary, normalize

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
KST = timezone(timedelta(hours=9))
UA = {"User-Agent": "ujb-ganpansa-collector/1.0"}
REGION = yaml.safe_load((ROOT / "rules" / "region.yaml").read_text(encoding="utf-8"))
PAGE_SIZE = 100          # 이 API 는 100 초과 요청을 100으로 자름
MAX_PAGES = 400          # 출처당 최대 4만 건

# 출처: (업종구분, 호출 주소)
# ※ 호출 주소는 공공데이터포털 '활용신청 → 상세보기'의 요청주소로 확인 후 고칩니다.
#   같은 시리즈 예: https://apis.data.go.kr/1741000/printing_shops/info
SOURCES = {
    "restaurant": ("일반음식점", "https://apis.data.go.kr/1741000/general_restaurants/info"),
    "rest":       ("휴게음식점", "https://apis.data.go.kr/1741000/rest_cafes/info"),
    "bakery":     ("제과점",     "https://apis.data.go.kr/1741000/bakeries/info"),
}
SOURCE_NAMES = {"restaurant": "일반음식점", "rest": "휴게음식점(카페·편의점)", "bakery": "제과점"}


def key() -> str:
    value = os.environ.get("DATA_GO_KR_KEY", "").strip()
    if not value:
        raise RuntimeError("환경변수 DATA_GO_KR_KEY 가 없습니다")
    return unquote(value) if "%" in value else value


def safe(e: Exception) -> str:
    """오류 문장에서 인증키를 지움 (로그·status.json 은 공개되므로)."""
    import re
    return re.sub(r"(serviceKey|key)=[^&\s')]+", r"\1=***", str(e))


def get(url: str, params: dict) -> requests.Response:
    for attempt in range(3):
        try:
            r = requests.get(url, params=params, headers=UA, timeout=40)
            r.raise_for_status()
            return r
        except requests.RequestException:
            if attempt == 2:
                raise
            time.sleep(3 * (attempt + 1))
    raise AssertionError


def _items(body: dict) -> tuple[list[dict], int]:
    """응답 모양이 조금 달라도 목록과 전체 건수를 찾아냄."""
    b = body.get("response", body)
    b = b.get("body", b)
    items = b.get("items", b.get("data", []))
    if isinstance(items, dict):
        items = items.get("item", items.get("row", []))
    if isinstance(items, dict):
        items = [items]
    if "header" in body.get("response", {}) and body["response"]["header"].get("resultCode") not in (None, "00", "0"):
        h = body["response"]["header"]
        raise RuntimeError(f"[{h.get('resultCode')}] {h.get('resultMsg')}")
    return items or [], int(b.get("totalCount") or 0)


def fetch(sid: str, inspect: bool = False) -> list[dict]:
    _, url = SOURCES[sid]
    rows, page = [], 1
    while page <= MAX_PAGES:
        body = get(url, {"serviceKey": key(), "pageNo": page, "numOfRows": PAGE_SIZE, "returnType": "json",
                         "cond[LOTNO_ADDR::LIKE]": REGION["lotno_like"]}).json()
        data, total = _items(body)
        if inspect:
            print(f"--- {sid}: 전체 {total}건, 첫 건 ---")
            print(json.dumps(data[:1], ensure_ascii=False, indent=1))
            return []
        rows.extend(data)
        if not data or len(rows) >= total:
            break
        page += 1
        time.sleep(0.15)
    return rows


def fetch_semas(inspect: bool = False) -> list[dict]:
    rows, page = [], 1
    while page <= 60:
        body = get(semas.URL, {"serviceKey": key(), **semas.params(page)}).json()
        data, total = _items(body)
        if inspect:
            print(f"--- 상가정보: 전체 {total}건, 첫 건 ---")
            print(json.dumps(data[:1], ensure_ascii=False, indent=1))
            return []
        rows.extend(data)
        if not data or len(rows) >= total:
            break
        page += 1
        time.sleep(0.15)
    return rows


def main() -> int:
    if "--inspect" in sys.argv:
        ok = True
        for sid, (category, url) in SOURCES.items():
            print(f"=== {category} ({url})")
            try:
                fetch(sid, inspect=True)
            except Exception as e:  # 주소·키·활용신청 문제를 알아보기 쉽게 출력
                ok = False
                print(f"!! 실패: {safe(e)[:300]}")
                print("   → 공공데이터포털 마이페이지의 '요청주소'와 SOURCES 주소가 같은지, 활용신청이 승인됐는지 확인하세요.")
        print(f"=== 상가정보(소상공인시장진흥공단) ({semas.URL})")
        try:
            fetch_semas(inspect=True)
        except Exception as e:
            ok = False
            print(f"!! 실패: {safe(e)[:300]}")
            print("   → '소상공인시장진흥공단_상가(상권)정보' 활용신청이 승인됐는지 확인하세요.")
        return 0 if ok else 1

    DATA.mkdir(exist_ok=True)
    rec_path = DATA / "records.json"
    previous = json.loads(rec_path.read_text(encoding="utf-8")).get("records", []) if rec_path.exists() else []
    records, status = [], {}

    for sid, (category, _) in SOURCES.items():
        started = time.time()
        try:
            raw = fetch(sid)
            rows = [normalize(sid, category, r) for r in raw]
            temp = sum(is_temporary(r["name"]) for r in rows)
            rows = [r for r in rows if not is_temporary(r["name"])]
            if not rows:
                raise RuntimeError("0건 (필터·주소 확인 필요)")
            records.extend(rows)
            status[sid] = {"name": SOURCE_NAMES[sid], "ok": True, "fetched": len(rows), "temporary_skipped": temp,
                           "seconds": round(time.time() - started, 1)}
        except Exception as e:  # 한 출처 실패가 전체를 멈추지 않게
            old = [r for r in previous if r.get("source") == sid]
            records.extend(old)
            status[sid] = {"name": SOURCE_NAMES[sid], "ok": False, "error": safe(e)[:200], "kept": len(old)}

    # 상가정보(선택 보강): 실패하면 이전 자료, 그것도 없으면 보강 없이 진행
    st_path = DATA / "stores.json"
    started = time.time()
    try:
        stores = [semas.normalize(r) for r in fetch_semas()]
        if not stores:
            raise RuntimeError("0건")
        st_path.write_text(json.dumps({"stores": stores}, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        status["semas"] = {"name": "상가정보(소상공인)", "ok": True, "fetched": len(stores), "seconds": round(time.time() - started, 1)}
    except Exception as e:
        stores = json.loads(st_path.read_text(encoding="utf-8")).get("stores", []) if st_path.exists() else []
        status["semas"] = {"name": "상가정보(소상공인)", "ok": False, "error": safe(e)[:200], "kept": len(stores)}

    now = datetime.now(KST)
    sites = build(records, today=now.date(), source_label="행정안전부 지방행정 인허가 데이터·소상공인시장진흥공단 상가(상권)정보(공공데이터포털)", stores=stores)
    stamp = now.isoformat(timespec="minutes")
    rec_path.write_text(json.dumps({"updated_at": stamp, "records": records}, ensure_ascii=False,
                                   separators=(",", ":")), encoding="utf-8")
    (DATA / "sites.json").write_text(json.dumps({"updated_at": stamp, **sites}, ensure_ascii=False,
                                                separators=(",", ":")), encoding="utf-8")
    (DATA / "status.json").write_text(json.dumps({"updated_at": stamp, "sources": status}, ensure_ascii=False,
                                                 indent=1), encoding="utf-8")
    print(json.dumps(status, ensure_ascii=False, indent=1))
    print(f"점포 자리 {sites['meta']['site_count']}곳, 기록 {sites['meta']['record_count']}건")
    return 0 if any(v["ok"] for k, v in status.items() if k != "semas") else 1


if __name__ == "__main__":
    sys.exit(main())
