import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "collector"))

from filters import classify, is_youth  # noqa: E402


def item(**kw):
    base = {"agency": "", "region_code": None, "region_text": "", "title": "", "target_text": "", "age_min": None, "age_max": None}
    base.update(kw)
    return base


def test_uijeongbu_by_agency():
    assert classify(item(agency="경기도 의정부시")) == "uijeongbu"


def test_uijeongbu_by_code():
    assert classify(item(agency="청년정책과", region_code="41150")) == "uijeongbu"


def test_other_gyeonggi_city_excluded():
    assert classify(item(agency="경기도 양주시")) == "exclude"


def test_other_province_excluded():
    assert classify(item(agency="서울특별시")) == "exclude"


def test_gyeonggi_whole_province():
    assert classify(item(agency="경기도", region_text="경기도 전역")) == "gyeonggi"


def test_gyeonggi_listing_other_cities_only_excluded():
    assert classify(item(agency="경기도", region_text="수원, 화성, 오산")) == "exclude"


def test_gyeonggi_listing_includes_uijeongbu():
    assert classify(item(agency="경기도", region_text="양주, 의정부, 동두천")) == "gyeonggi"


def test_national():
    assert classify(item(agency="고용노동부", region_text="전국")) == "national"


def test_national_non_capital_only_excluded():
    assert classify(item(agency="행정안전부", region_text="비수도권 소재 청년")) == "exclude"


def test_other_province_region_excluded():
    assert classify(item(agency="한국OO원", region_text="강원")) == "exclude"


def test_kstartup_gyeonggi_region():
    assert classify(item(agency="한국외국어대학교연구산학협력단", region_text="경기", title="창업보육센터 입주기업 모집")) == "gyeonggi"


def test_kstartup_gyeonggi_other_city_excluded():
    assert classify(item(agency="OO대학교", region_text="경기", title="수원 창업지원센터 입주기업 모집")) == "exclude"


def test_no_region_words_is_national():
    assert classify(item(agency="중소벤처기업부", region_text="금융,창업,2026")) == "national"


def test_bizinfo_all_region_tags_is_national():
    tags = "인력,장학금,서울,부산,대구,인천,광주,대전,울산,세종,경기,강원,충북,충남,전북,전남,경북,경남,제주"
    assert classify(item(agency="중소벤처기업부", region_text=tags, title="2027년 중소기업 계약학과 신입생 모집")) == "national"


def test_bizinfo_gyeonggi_city_program_excluded():
    assert classify(item(agency="경기도", region_text="소상공인,남양주시", title="[경기] 남양주시 소상공인 지원")) == "exclude"


def test_youth_hint():
    assert is_youth(item(title="창업 지원", youth_hint=True))


def test_youth_by_age_overlap():
    assert is_youth(item(age_min=18, age_max=34))


def test_not_youth_children():
    assert not is_youth(item(title="청년 부모 아동수당", age_min=0, age_max=8))


def test_not_youth_senior():
    assert not is_youth(item(age_min=65, age_max=None))


def test_youth_by_keyword():
    assert is_youth(item(title="대학생 현장실습 지원"))
