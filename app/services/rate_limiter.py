import time
from collections import defaultdict, deque
from app.core.config import settings

_windows: dict[int, deque] = defaultdict(deque)
WINDOW_SECONDS = 60

def check_rate_limit(user_id: int) -> bool:
    now = time.monotonic()
    window = _windows[user_id]

    while window and now - window[0] > WINDOW_SECONDS:
        window.popleft()

    if len(window) >= settings.MAX_SUBMISSIONS_PER_MINUTE:
        return False

    window.append(now)
    return True

def seconds_until_retry(user_id: int) -> int:
    window = _windows[user_id]
    if not window:
        return 0
    return max(0, int(WINDOW_SECONDS - (time.monotonic() - window[0])))