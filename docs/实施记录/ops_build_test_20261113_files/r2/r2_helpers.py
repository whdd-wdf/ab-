from datetime import datetime, timezone, timedelta
try:
    from zoneinfo import ZoneInfo
    TZ = ZoneInfo("Asia/Shanghai")
except Exception:
    TZ = timezone(timedelta(hours=8))
def now():
    return datetime.now(TZ)
def today_str():
    return now().strftime("%Y-%m-%d")
def now_str():
    return now().strftime("%Y-%m-%d %H:%M:%S")
def round_tick(price, tick):
    from decimal import Decimal, ROUND_HALF_UP
    return float(Decimal(str(price)).quantize(Decimal(str(tick)), rounding=ROUND_HALF_UP))