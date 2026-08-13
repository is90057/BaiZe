def fmt_timecode(seconds: float, fps: float = 30.0, compact: bool = False) -> str:
    seconds = max(seconds, 0.0)
    frames = int(round(seconds * fps))
    fr = frames % int(round(fps))
    total = frames // int(round(fps))
    h, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)
    if compact:
        return f"{h:02d}:{m:02d}:{s:02d}"

    def f_pad(n: int) -> str:
        return f"{n:02d}"

    return f"{h:02d}:{m:02d}:{s:02d}:{f_pad(fr)}"


def parse_timecode(text: str, fps: float = 30.0) -> float | None:
    parts = text.replace(",", ":").strip().split(":")
    try:
        nums = [float(p) for p in parts]
    except ValueError:
        return None
    if len(nums) == 4:
        h, m, s, f = nums
        return h * 3600 + m * 60 + s + f / max(fps, 1.0)
    if len(nums) == 3:
        h, m, s = nums
        return h * 3600 + m * 60 + s
    if len(nums) == 2:
        m, s = nums
        return m * 60 + s
    if len(nums) == 1:
        return nums[0]
    return None