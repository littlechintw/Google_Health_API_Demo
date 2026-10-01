from dataclasses import asdict, dataclass
from typing import Optional


@dataclass
class DailyRecord:
    date: str                                   # YYYY-MM-DD（當地日期）
    steps: Optional[int] = None                 # 單日步數
    activity_type: Optional[str] = None         # 單日最長一次活動（例：步行）
    activity_minutes: Optional[int] = None      # 該活動時長（分鐘）
    activity_avg_hr: Optional[int] = None       # 該活動平均心率（bpm）
    sleep_minutes: Optional[int] = None         # 單日睡眠時長（實際睡著分鐘）

    def to_dict(self) -> dict:
        return asdict(self)


CSV_COLUMNS = list(DailyRecord("").to_dict().keys())
