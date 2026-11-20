"""인허가 API 원본 한 건을 공통 형식 한 건으로 바꿉니다.

공통 형식 (data/records.json 의 한 줄)
  {"source", "name", "uptae", "type", "open", "close", "lotno", "road", "lat", "lng"}
필드명이 API 버전에 따라 다를 수 있어 후보 이름을 앞에서부터 찾습니다.
처음 연결할 때는 `python collect.py --inspect` 로 실제 필드명을 확인하세요.
"""
from __future__ import annotations

import re
from datetime import date
from pathlib import Path

import yaml

RULES = Path(__file__).resolve().parent.parent / "rules"
TYPES: dict[str, list[str]] = yaml.safe_load((RULES / "types.yaml").read_text(encoding="utf-8"))

FIELDS = {
    "name":   ["BPLC_NM", "bplcNm"],
    "uptae":  ["BZSTAT_SE_NM", "SNTTN_BZSTAT_NM", "UPTAE_NM", "uptaeNm"],
    "open":   ["LCPMT_YMD", "apvPermYmd"],
    "close":  ["CLSBIZ_YMD", "dcbYmd"],
    "status": ["SALS_STTS_NM", "trdStateNm"],
    "lotno":  ["LOTNO_ADDR", "siteWhlAddr"],
    "road":   ["ROAD_NM_ADDR", "rdnWhlAddr"],
    "x":      ["CRD_INFO_X", "x"],
    "y":      ["CRD_INFO_Y", "y"],
}

_transformer = None


def _to_wgs84(x, y):
    """EPSG:5174(보정계수 없는 Bessel 중부원점TM) → 위경도. pyproj 가 없으면 생략."""
    global _transformer
    try:
        if _transformer is None:
            from pyproj import Transformer
            _transformer = Transformer.from_crs("EPSG:5174", "EPSG:4326", always_xy=True)
        lng, lat = _transformer.transform(float(x), float(y))
        return round(lat, 6), round(lng, 6)
    except Exception:
        return None, None


def pick(rec: dict, names: list[str]):
    for n in names:
        v = rec.get(n)
        if v not in (None, "", " "):
            return str(v).strip()
    return None


def to_date(s) -> str | None:
    """'20190305', '2019-03-05', '2019.03.05' → '2019-03-05'"""
    if not s:
        return None
    digits = re.sub(r"\D", "", str(s))[:8]
    if len(digits) != 8:
        return None
    try:
        return date(int(digits[:4]), int(digits[4:6]), int(digits[6:])).isoformat()
    except ValueError:
        return None


def type_of(uptae: str | None, category: str) -> str:
    text = uptae or ""
    for t, words in TYPES.items():
        if any(w in text for w in words):
            return t
    return "베이커리" if category == "제과점" else "기타"


LOT_RE = re.compile(r"([가-힣0-9]+동)\s*(산?\s*\d+(?:-\d+)?)")
FLOOR_RE = re.compile(r"(지하\s*\d+|\d+)\s*층")
HO_RE = re.compile(r"(\d+)\s*호")


def site_key(lotno: str | None, road: str | None) -> tuple[str | None, str | None, bool]:
    """같은 '점포 자리'를 묶는 키 = 법정동 + 번지 (+ 층·호가 있으면).
    층·호가 없으면 건물 단위로 묶이므로 세 번째 값(unit)이 False."""
    m = LOT_RE.search(lotno or "") or LOT_RE.search(road or "")
    if not m:
        return None, None, False
    dong, lot = m.group(1), m.group(2).replace(" ", "")
    detail = f"{road or ''} {lotno or ''}"
    fl, ho = FLOOR_RE.search(detail), HO_RE.search(detail)
    unit = (fl.group(1).replace(" ", "") + "층" if fl else "") + (ho.group(1) + "호" if ho else "")
    return f"{dong} {lot}" + (f" {unit}" if unit else ""), dong, bool(unit)


def is_temporary(name: str) -> bool:
    """백화점 팝업처럼 '(한시적)' 영업은 자리 내력에서 뺍니다 (몇 주 단위로 바뀌어 '자주 바뀐 자리'를 왜곡)."""
    return "한시적" in (name or "")


def normalize(source: str, category: str, rec: dict) -> dict:
    lat = lng = None
    x, y = pick(rec, FIELDS["x"]), pick(rec, FIELDS["y"])
    if x and y:
        lat, lng = _to_wgs84(x, y)
    uptae = pick(rec, FIELDS["uptae"])
    return {
        "source": source,
        "name": pick(rec, FIELDS["name"]) or "(상호 미상)",
        "uptae": uptae or "",
        "type": type_of(uptae, category),
        "open": to_date(pick(rec, FIELDS["open"])),
        "close": to_date(pick(rec, FIELDS["close"])),
        "lotno": pick(rec, FIELDS["lotno"]) or "",
        "road": pick(rec, FIELDS["road"]) or "",
        "lat": lat,
        "lng": lng,
    }
