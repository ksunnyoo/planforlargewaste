"""지자체별 자료 이용 조건(공공누리 유형) 확인 결과. 근거는 docs/research/data_license_log.md에 있다.

확인하지 못한 지자체는 '확인 중'으로 표시한다. 확인 일시 이후에 바뀔 수 있으므로 해당 지자체 안내를 다시 확인해야 한다.
이 표시는 법률 판단이 아니라 지자체 페이지에 표시된 내용을 옮긴 것이다.
"""
from typing import Dict, Optional

CONFIRMED = "confirmed"      # 상업적 이용·변경이 가능한 유형으로 표시됨(출처 표시 필요)
RESTRICTED = "restricted"    # 상업적 이용 또는 변경이 제한되는 유형으로 표시됨
UNVERIFIED = "unverified"    # 아직 확인하지 못함

_CHECKED = "2026-11-16"

_KNOWN: Dict[str, dict] = {
    "3780000": {
        "status": CONFIRMED, "kogl_type": 1,
        "label": "공공누리 제1유형(출처표시)",
        "summary": "출처를 표시하면 상업적 이용과 변경이 가능한 유형으로 표시되어 있습니다.",
        "source_name": "성남시 자원순환과 · 성남시 자원순환 통합 플랫폼",
        "source_url": "https://recycle.seongnam.go.kr/platformservice/waste/intro",
        "checked_at": _CHECKED,
    },
    "3220000": {
        "status": RESTRICTED, "kogl_type": 4,
        "label": "공공누리 제4유형(출처표시+상업적 이용금지+변경금지)",
        "summary": "상업적 이용과 변경이 금지된 유형으로 표시되어 있습니다. 이 화면의 수수료는 참고용이며 영업 목적으로 쓰지 마십시오.",
        "source_name": "서울특별시 강남구 대형생활폐기물 배출안내",
        "source_url": "https://www.gangnam.go.kr/board/waste/1/view.do?mid=ID02_011109",
        "checked_at": _CHECKED,
    },
    "3330000": {
        "status": RESTRICTED, "kogl_type": None,
        "label": "공공누리 표시 불일치(아이콘은 제4유형 모양, 문구는 출처표시)",
        "summary": "표시가 서로 달라 제한이 있는 것으로 보고 다룹니다. 이 화면의 수수료는 참고용이며 영업 목적으로 쓰지 마십시오.",
        "source_name": "부산광역시 해운대구 대형폐기물 안내",
        "source_url": None,
        "checked_at": _CHECKED,
    },
    "3460000": {
        "status": UNVERIFIED, "kogl_type": None,
        "label": "이용 조건 확인 중(제4유형일 가능성)",
        "summary": "대형폐기물 페이지의 공공누리 표시를 확인하지 못했습니다. 이 화면의 수수료는 참고용이며 영업 목적으로 쓰지 마십시오.",
        "source_name": "대구광역시 수성구 대형폐기물 안내",
        "source_url": "https://www.suseong.kr/index.do?menu_id=00000370",
        "checked_at": _CHECKED,
    },
    "3740000": {
        "status": UNVERIFIED, "kogl_type": None,
        "label": "이용 조건 확인 중",
        "summary": "대형폐기물 페이지에서 공공누리 표시를 확인하지 못했습니다. 이 화면의 수수료는 참고용이며 영업 목적으로 쓰지 마십시오.",
        "source_name": "경기도 수원시 대형폐기물 안내",
        "source_url": "https://waste.suwon.go.kr/lmth/01_intro/intro_0401.asp",
        "checked_at": _CHECKED,
    },
}

_DEFAULT = {
    "status": UNVERIFIED, "kogl_type": None,
    "label": "이용 조건 확인 중",
    "summary": "이 지자체 자료의 이용 조건을 확인하지 못했습니다. 이 화면의 수수료는 참고용이며 영업 목적으로 쓰지 마십시오.",
    "source_name": "공공데이터포털 전국대형폐기물수거수수료정보표준데이터",
    "source_url": "https://www.data.go.kr/data/15114146/standard.do",
    "checked_at": None,
}


def get_license(code: str) -> dict:
    """지자체 코드에 대한 이용 조건 정보. 없으면 '확인 중' 기본값."""
    return dict(_KNOWN.get(code, _DEFAULT))


def license_status(code: str) -> str:
    return get_license(code)["status"]


def known_codes():
    return set(_KNOWN)


def source_url(code: str) -> Optional[str]:
    return get_license(code)["source_url"]
