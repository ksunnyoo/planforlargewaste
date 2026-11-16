"""요청 제한: IP별 분당 횟수, 하루 LLM 호출 상한. 메모리 기반이라 서버 재시작 시 초기화된다(무료 1 worker 전제)."""
import threading
import time
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from typing import Deque, Dict, Optional

_KST = timezone(timedelta(hours=9))
_lock = threading.Lock()
_hits: Dict[str, Deque[float]] = defaultdict(deque)
_llm_day: Optional[str] = None
_llm_count = 0


def check_rate(key: str, limit_per_minute: int, now: Optional[float] = None) -> Optional[int]:
    """허용이면 None, 초과면 재시도까지 남은 초(정수)."""
    now = time.time() if now is None else now
    with _lock:
        q = _hits[key]
        while q and now - q[0] >= 60:
            q.popleft()
        if len(q) >= limit_per_minute:
            return max(1, int(60 - (now - q[0])) + 1)
        q.append(now)
        return None


def try_use_llm(daily_limit: int) -> bool:
    """오늘(KST) LLM 호출 상한 이내이면 1회 사용으로 계산하고 True."""
    global _llm_day, _llm_count
    today = datetime.now(_KST).date().isoformat()
    with _lock:
        if _llm_day != today:
            _llm_day, _llm_count = today, 0
        if _llm_count >= daily_limit:
            return False
        _llm_count += 1
        return True


def reset_for_tests() -> None:
    global _llm_day, _llm_count
    with _lock:
        _hits.clear()
        _llm_day, _llm_count = None, 0
