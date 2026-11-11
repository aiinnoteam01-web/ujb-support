import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "collector"))

from filters import targets  # noqa: E402


def item(**kw):
    base = {"title": "", "target_text": "", "user_type": "", "age_min": None, "age_max": None,
            "youth_hint": False, "target_hints": []}
    base.update(kw)
    return base


def test_youth_by_word():
    assert "청년" in targets(item(title="청년 월세 지원"))


def test_youth_by_age():
    assert "청년" in targets(item(title="주거 지원", age_min=19, age_max=34))


def test_senior():
    assert targets(item(title="어르신 일자리 사업")) == ["시니어"]


def test_senior_by_age():
    assert "시니어" in targets(item(title="일자리", age_min=65))


def test_disabled():
    assert "장애인" in targets(item(target_text="등록 장애인"))


def test_pregnancy():
    assert "임산부·출산" in targets(item(title="임산부 교통비 지원"))


def test_small_business_and_company():
    t = targets(item(title="소상공인 경영안정자금", target_text="중소기업"))
    assert "소상공인" in t and "중소기업" in t


def test_startup_hint():
    assert targets(item(title="사업화 지원", target_hints=["창업"])) == ["창업"]


def test_corporation_from_user_type():
    assert "법인·단체" in targets(item(title="시설 개선", user_type="법인/시설/단체"))


def test_youth_and_startup():
    t = targets(item(title="청년 창업 지원"))
    assert "청년" in t and "창업" in t


def test_no_target():
    assert targets(item(title="근로·자녀장려금", target_text="가구")) == []
