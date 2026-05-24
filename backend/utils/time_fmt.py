"""utils/time_fmt.py"""


def fmt_duration(seconds: float | None) -> str:
    if not seconds:
        return ""
    s = int(seconds)
    m, s = divmod(s, 60)
    h, m = divmod(m, 60)
    if h:
        return f"{h}h {m}m {s}s"
    return f"{m}m {s}s"
