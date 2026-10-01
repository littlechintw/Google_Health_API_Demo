"""用 Google Health API 抓最近 N 天的 單日步數 / 單日最長活動與平均心率 / 單日睡眠時長。

  python main.py                      # 最近 7 天，沿用上次的授權
  python main.py --reauth             # 重新開瀏覽器授權（demo 用）
  python main.py --days 7 --end 2026-09-30
"""
import argparse
import csv
import json
import sys
from datetime import date, datetime, timedelta

import config
from health_api import HealthApi
from models import CSV_COLUMNS


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--days", type=int, default=7)
    ap.add_argument("--end", type=date.fromisoformat, default=date.today(), help="結束日 YYYY-MM-DD，預設今天")
    ap.add_argument("--reauth", action="store_true", help="忽略已存的 token，重新開瀏覽器授權")
    args = ap.parse_args()

    start = args.end - timedelta(days=args.days - 1)
    print(f"range={start} ~ {args.end} ({args.days} days)")

    try:
        records = HealthApi(reauth=args.reauth).fetch_daily(start, args.end)
    except Exception as e:  # noqa: BLE001
        sys.exit(f"\n抓取失敗：{e}")

    print(f"\n{'date':>10}  {'steps':>6}  {'activity':<8}  {'min':>4}  {'avgHR':>5}  {'sleepMin':>8}")
    for r in records:
        print(f"{r.date:>10}  {r.steps if r.steps is not None else '-':>6}  {r.activity_type or '-':<8}  "
              f"{r.activity_minutes if r.activity_minutes is not None else '-':>4}  "
              f"{r.activity_avg_hr if r.activity_avg_hr is not None else '-':>5}  "
              f"{r.sleep_minutes if r.sleep_minutes is not None else '-':>8}")
    print()

    config.OUTPUT_DIR.mkdir(exist_ok=True)
    stem = f"health_{start}_{args.end}_{datetime.now():%Y%m%d_%H%M%S}"
    csv_path, json_path = config.OUTPUT_DIR / f"{stem}.csv", config.OUTPUT_DIR / f"{stem}.json"
    with csv_path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        w.writeheader()
        w.writerows(r.to_dict() for r in records)
    json_path.write_text(json.dumps({"start": str(start), "end": str(args.end),
                                     "fetched_at": datetime.now().isoformat(timespec="seconds"),
                                     "records": [r.to_dict() for r in records]}, ensure_ascii=False, indent=2))
    print(f"CSV : {csv_path}\nJSON: {json_path}")


if __name__ == "__main__":
    main()
