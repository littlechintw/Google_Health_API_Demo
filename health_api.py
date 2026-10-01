"""Google Health API v4：單日步數、單日最長活動與其平均心率、單日睡眠時長。

  steps      -> POST .../steps/dataPoints:dailyRollUp
  exercise   -> GET  .../exercise/dataPoints（不帶 filter，新到舊翻頁到範圍外為止）
  heart-rate -> POST .../heart-rate/dataPoints:rollUp（活動本身沒有平均心率時的備援）
  sleep      -> GET  .../sleep/dataPoints?filter=sleep.interval.end_time >= ...

實測（2026-10-01）：
- list filter 只接受單一 `>=`；exercise 連 `>=` 都回 400，所以 exercise 不帶 filter
- 回傳順序新到舊；exercise / sleep 的 pageSize 上限 25
- 回應沒有 civil time，當地日期用 endTime + endUtcOffset 自己算
- 自動偵測的運動沒有 averageHeartRateBeatsPerMinute，手動開始的才有
"""
import time
from datetime import date, datetime, timedelta, timezone

import requests

import config
from google_auth import get_access_token
from models import DailyRecord


def _local_date(ts: str, utc_offset: str | None) -> str:
    t = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    return (t + timedelta(seconds=int((utc_offset or "0s").rstrip("s")))).date().isoformat()


def _seconds(duration: str | None) -> float:
    return float((duration or "0s").rstrip("s"))


class HealthApi:
    def __init__(self, reauth: bool = False):
        token = get_access_token(config.CLIENT_SECRET_FILE, config.TOKEN_FILE, config.SCOPES, force=reauth)
        self._headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}

    # ── HTTP ──────────────────────────────────────────────────────
    def _request(self, method: str, url: str, what: str, **kw) -> dict:
        """5xx 自動重試 3 次（2s / 4s / 8s）。"""
        for attempt in range(1, 4):
            r = requests.request(method, url, headers=self._headers, timeout=60, **kw)
            print(f"  {method} {what} -> {r.status_code}")
            if r.status_code == 200:
                return r.json()
            if r.status_code >= 500 and attempt < 3:
                time.sleep(2 ** attempt)
                continue
            raise RuntimeError(f"Google Health API {r.status_code} on {what}: {r.text[:500]}")
        raise AssertionError("unreachable")

    def _post(self, data_type: str, method: str, body: dict) -> dict:
        url = f"{config.BASE_URL}/users/me/dataTypes/{data_type}/dataPoints:{method}"
        return self._request("POST", url, f"{data_type}:{method}", json=body)

    def _list(self, data_type: str, params: dict, stop_before: date | None = None) -> list[dict]:
        """翻頁列出 dataPoints；回傳是新到舊，遇到比 stop_before 更早的點就停。"""
        url = f"{config.BASE_URL}/users/me/dataTypes/{data_type}/dataPoints"
        points: list[dict] = []
        while True:
            data = self._request("GET", url, f"{data_type}:list", params=params)
            page = data.get("dataPoints", [])
            points += page
            if stop_before and page:
                iv = page[-1][data_type]["interval"]
                if _local_date(iv["endTime"], iv.get("endUtcOffset")) < stop_before.isoformat():
                    return points
            if not data.get("nextPageToken"):
                return points
            params["pageToken"] = data["nextPageToken"]

    # ── 各資料 ────────────────────────────────────────────────────
    def _steps(self, start: date, end: date) -> dict[str, int]:
        body = {"range": {"start": {"date": {"year": start.year, "month": start.month, "day": start.day},
                                    "time": {"hours": 0, "minutes": 0, "seconds": 0}},
                          "end": {"date": {"year": end.year, "month": end.month, "day": end.day},
                                  "time": {"hours": 23, "minutes": 59, "seconds": 59}}},
                "windowSizeDays": 1}
        out = {}
        for p in self._post("steps", "dailyRollUp", body).get("rollupDataPoints", []):
            d = p["civilStartTime"]["date"]
            out[f"{d['year']:04d}-{d['month']:02d}-{d['day']:02d}"] = int(p.get("steps", {}).get("countSum", 0))
        return out

    def _longest_exercise(self, start: date, end: date) -> dict[str, dict]:
        """每天 activeDuration 最長的一次運動。"""
        best: dict[str, dict] = {}
        for p in self._list("exercise", {"pageSize": 25}, stop_before=start):
            e = p["exercise"]
            iv = e["interval"]
            day = _local_date(iv["endTime"], iv.get("endUtcOffset"))
            if not (start.isoformat() <= day <= end.isoformat()):
                continue
            if day not in best or _seconds(e.get("activeDuration")) > _seconds(best[day].get("activeDuration")):
                best[day] = e
        return best

    def _avg_hr(self, start_ts: str, end_ts: str) -> int | None:
        """用 heart-rate rollUp 算某段時間的平均心率。"""
        secs = int((datetime.fromisoformat(end_ts.replace("Z", "+00:00"))
                    - datetime.fromisoformat(start_ts.replace("Z", "+00:00"))).total_seconds())
        if secs <= 0:
            return None
        body = {"range": {"startTime": start_ts, "endTime": end_ts}, "windowSize": f"{secs}s"}
        pts = self._post("heart-rate", "rollUp", body).get("rollupDataPoints", [])
        vals = [p["heartRate"]["beatsPerMinuteAvg"] for p in pts if "heartRate" in p and "beatsPerMinuteAvg" in p["heartRate"]]
        return round(sum(vals) / len(vals)) if vals else None

    def _sleep(self, start: date, end: date) -> dict[str, int]:
        since = datetime.combine(start - timedelta(days=1), datetime.min.time(), tzinfo=timezone.utc)
        out: dict[str, int] = {}
        for p in self._list("sleep", {"pageSize": 25, "filter": f'sleep.interval.end_time >= "{since:%Y-%m-%dT%H:%M:%SZ}"'}):
            s = p["sleep"]
            day = _local_date(s["interval"]["endTime"], s["interval"].get("endUtcOffset"))
            if start.isoformat() <= day <= end.isoformat():
                out[day] = out.get(day, 0) + int(s.get("summary", {}).get("minutesAsleep", 0))
        return out

    # ── public ────────────────────────────────────────────────────
    def fetch_daily(self, start: date, end: date) -> list[DailyRecord]:
        steps = self._steps(start, end)
        exercises = self._longest_exercise(start, end)
        sleep = self._sleep(start, end)

        records = []
        for i in range((end - start).days + 1):
            day = (start + timedelta(days=i)).isoformat()
            rec = DailyRecord(date=day, steps=steps.get(day), sleep_minutes=sleep.get(day))
            e = exercises.get(day)
            if e:
                rec.activity_type = e.get("displayName") or e.get("exerciseType")
                rec.activity_minutes = round(_seconds(e.get("activeDuration")) / 60)
                avg = e.get("metricsSummary", {}).get("averageHeartRateBeatsPerMinute")
                rec.activity_avg_hr = int(avg) if avg else self._avg_hr(e["interval"]["startTime"], e["interval"]["endTime"])
            records.append(rec)
        return records
