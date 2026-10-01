# google_health_api_get_data

用 **Google Health API v4** 抓取自己 Fitbit / Pixel Watch 的健康資料，每天一列，輸出 CSV 與 JSON。
只抓三種資料：

| 欄位 | 中文 | 一句話定義 |
|---|---|---|
| `steps` | 單日步數 | 當地日期 00:00 到 23:59 的步數加總 |
| `activity_type` / `activity_minutes` / `activity_avg_hr` | 單日最長活動 | 當天「活動時長最長的那一次運動」的名稱、分鐘數、以及**該次運動期間**的平均心率 |
| `sleep_minutes` | 單日睡眠時長 | 醒來日期落在當天的所有睡眠段，實際睡著的分鐘數加總 |

執行結果長這樣：

```
      date   steps  activity   min  avgHR  sleepMin
2026-09-25   16110  步行         168    100       322
2026-09-26    7834  步行          53    111       436
2026-09-27   10172  步行          54    111       338
```

---

## 目錄

1. [前置條件](#1-前置條件)
2. [Google Cloud 設定（只做一次）](#2-google-cloud-設定只做一次)
3. [安裝](#3-安裝)
4. [執行](#4-執行)
5. [輸出檔案與欄位定義](#5-輸出檔案與欄位定義)
6. [每個欄位是怎麼算出來的](#6-每個欄位是怎麼算出來的)
7. [授權與 token 行為](#7-授權與-token-行為)
8. [程式結構](#8-程式結構)
9. [Google Health API 實測筆記](#9-google-health-api-實測筆記)
10. [常見錯誤排除](#10-常見錯誤排除)
11. [安全性：哪些檔案不能外流](#11-安全性哪些檔案不能外流)
12. [參考資料](#12-參考資料)

---

## 1. 前置條件

- **Python 3.10 以上**（開發時用 3.14）。
- 一個 **Google 帳號**，而且是 Fitbit 已經遷移過去的那個帳號。Fitbit 帳號在 2026-05-19 之後必須遷移到 Google 帳號，資料才會進 Google Health API。
- 該帳號底下有 Fitbit 或 Pixel Watch 的同步資料。
- 一個 **Google Cloud 專案**，並且已經可以啟用 Google Health API。
  官方文件寫「目前暫不接受新專案」，但實際上有些帳號可以直接啟用。啟用後能不能用，以第 2 節最後的測試為準。

---

## 2. Google Cloud 設定（只做一次）

全程在瀏覽器操作 Google Cloud Console，大約 10 分鐘。

### 2.1 建立專案並啟用 API

1. 開 https://console.cloud.google.com/ ，右上角專案選單 → **New Project**，取名後 Create。
2. 開 https://console.developers.google.com/apis/library/health.googleapis.com ，確認右上角是剛建的專案，按 **Enable**。

### 2.2 設定 OAuth 同意畫面

1. 開 https://console.cloud.google.com/auth/overview ，按 **Get started**。
2. App name 隨意填，User support email 選自己的信箱。
3. Audience 選 **External**。
4. Contact information 填自己的信箱，同意條款後 **Create**。

### 2.3 加入測試使用者

Testing 狀態的 app 只有名單上的帳號能授權。

1. 左側 **Audience**。
2. 確認 Publishing status 是 **Testing**。
3. Test users → **Add users** → 填你的 Google 帳號 → Save。

### 2.4 加入三個 scope

1. 左側 **Data Access** → **Add or remove scopes**。
2. 在 Filter 搜尋 `googlehealth`，勾下面三個。找不到就捲到最底下的 **Manually add scopes**，整段貼進去：

```
https://www.googleapis.com/auth/googlehealth.activity_and_fitness.readonly
https://www.googleapis.com/auth/googlehealth.health_metrics_and_measurements.readonly
https://www.googleapis.com/auth/googlehealth.sleep.readonly
```

3. **Update** → **Save**。

| scope | 本專案用它拿什麼 |
|---|---|
| `activity_and_fitness.readonly` | 步數、運動紀錄 |
| `health_metrics_and_measurements.readonly` | 心率 |
| `sleep.readonly` | 睡眠 |

### 2.5 建立 OAuth client 並下載 JSON

1. 左側 **Clients** → **Create client**。
2. Application type 選 **Desktop app**。
   不要選 Web application。Desktop app 不需要事先登記 redirect URI，程式會自己在本機開一個隨機 port 接授權回呼。
3. 取名後 **Create**。
4. 在彈出視窗按 **Download JSON**，把檔案改名成 `client_secret.json`，放到本專案根目錄。

### 2.6 確認專案真的有存取權（選做）

開 https://developers.google.com/health/reference/rest/v4/users.dataTypes.dataPoints/list ，右側 APIs Explorer：

- `parent` 填 `users/me/dataTypes/steps`
- `pageSize` 填 `5`
- 勾 Google OAuth 2.0 → **Execute** → 用你的 Google 帳號登入同意

回 200 且有 `dataPoints` 代表通了。回 403 代表這個專案沒有被 Google 允許使用 Health API。

---

## 3. 安裝

```bash
cd ~/code/google_health_api_get_data

python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

cp .env.example .env     # 內容只有一行，指到 client_secret.json，通常不用改
```

套件只有四個：`requests`、`python-dotenv`、`google-auth`、`google-auth-oauthlib`。

安裝完成後根目錄應該有這些檔案：

```
client_secret.json   ← 你從 Cloud Console 下載的
.env
config.py  google_auth.py  health_api.py  main.py  models.py
requirements.txt  README.md
```

---

## 4. 執行

```bash
source venv/bin/activate

python main.py                            # 最近 7 天（含今天），沿用上次的授權
python main.py --reauth                   # 重新開瀏覽器授權後再抓（demo 時用）
python main.py --days 14                  # 最近 14 天
python main.py --days 7 --end 2026-09-30  # 2026-09-24 ~ 2026-09-30
```

| 參數 | 預設 | 說明 |
|---|---|---|
| `--days N` | 7 | 抓幾天，結束日往前數 |
| `--end YYYY-MM-DD` | 今天 | 結束日（含） |
| `--reauth` | 關 | 忽略已存的 token，重新開瀏覽器走一次 Google 授權 |

### 第一次執行會發生什麼

1. 終端機印出一個 `https://accounts.google.com/o/oauth2/auth?...` 的網址，瀏覽器會自動打開。
2. 選你的 Google 帳號。因為 app 是 Testing 狀態，會出現「Google hasn't verified this app」，按 **Continue**。
3. 勾選三個權限，按 **Continue**。
4. 瀏覽器顯示授權完成，回到終端機就會開始抓資料。
5. 授權結果存到 `google_tokens.json`，之後執行不會再開瀏覽器。

### 執行時終端機會印什麼

```
range=2026-09-25 ~ 2026-10-01 (7 days)
  POST steps:dailyRollUp -> 200
  GET exercise:list -> 200
  GET sleep:list -> 200
  POST heart-rate:rollUp -> 200      ← 每一天如果需要補算活動平均心率就會多一行
  ...
      date   steps  activity   min  avgHR  sleepMin
2026-09-25   16110  步行         168    100       322
...
CSV : .../output/health_2026-09-25_2026-10-01_20261001_150411.csv
JSON: .../output/health_2026-09-25_2026-10-01_20261001_150411.json
```

每一行 API 呼叫都會印出來，看到非 200 就知道是哪一步出問題。

---

## 5. 輸出檔案與欄位定義

每次執行在 `output/` 產生一組 CSV 和 JSON，檔名格式：

```
health_{起始日}_{結束日}_{執行時間}.csv
health_{起始日}_{結束日}_{執行時間}.json
```

### CSV

```csv
date,steps,activity_type,activity_minutes,activity_avg_hr,sleep_minutes
2026-09-25,16110,步行,168,100,322
2026-09-26,7834,步行,53,111,436
```

### JSON

```json
{
  "start": "2026-09-25",
  "end": "2026-10-01",
  "fetched_at": "2026-10-01T15:04:11",
  "records": [
    {
      "date": "2026-09-25",
      "steps": 16110,
      "activity_type": "步行",
      "activity_minutes": 168,
      "activity_avg_hr": 100,
      "sleep_minutes": 322
    }
  ]
}
```

### 欄位

| 欄位 | 型別 | 單位 | 說明 | 沒有資料時 |
|---|---|---|---|---|
| `date` | string | — | 當地日期 `YYYY-MM-DD` | 一定有 |
| `steps` | int | 步 | 當天步數總和 | `null` / 空 |
| `activity_type` | string | — | 當天最長一次運動的名稱，用 Fitbit 給的顯示名稱（例：`步行`、`跑步`） | `null` / 空 |
| `activity_minutes` | int | 分鐘 | 該次運動的 active duration，四捨五入到整數分鐘 | `null` / 空 |
| `activity_avg_hr` | int | bpm | **該次運動期間**的平均心率，不是整天 | `null` / 空 |
| `sleep_minutes` | int | 分鐘 | 當天實際睡著的分鐘數（不含醒著的時間） | `null` / 空 |

CSV 裡的 `null` 會變成空字串。

---

## 6. 每個欄位是怎麼算出來的

### 6.1 日期與時區

Google Health API 回傳的都是 UTC 時間加上一個 `utcOffset`（台灣是 `28800s`）。
程式一律用 **`endTime + endUtcOffset` 換成當地日期**，所以：

- 9/30 晚上 11 點睡、10/1 早上 7 點醒的睡眠，算在 **10/1**。
- 跨午夜的運動，算在結束那天。

這和 Fitbit app 自己的歸日方式一致。

### 6.2 步數

```
POST https://health.googleapis.com/v4/users/me/dataTypes/steps/dataPoints:dailyRollUp
{
  "range": {
    "start": {"date": {"year": 2026, "month": 9, "day": 25}, "time": {"hours": 0, "minutes": 0, "seconds": 0}},
    "end":   {"date": {"year": 2026, "month": 10, "day": 1}, "time": {"hours": 23, "minutes": 59, "seconds": 59}}
  },
  "windowSizeDays": 1
}
```

回來每天一個 `rollupDataPoints`，取 `steps.countSum`。這是 Google 已經依當地日期彙總好的數字，和 Fitbit app 首頁顯示的步數相同。

注意：今天的步數會隨手錶同步一直增加，今天抓到的數字只是「到目前為止」。

### 6.3 單日最長活動

1. 呼叫 `GET .../dataTypes/exercise/dataPoints?pageSize=25`，**不帶 filter**（原因見第 9 節）。
2. 回傳是新到舊，程式一頁一頁翻，翻到有運動的結束日期早於起始日就停。
3. 每一筆運動用 `endTime + endUtcOffset` 歸到當地日期。
4. 同一天有多筆時，取 **`activeDuration` 最長**的那筆。
5. `activity_type` 取 `displayName`（Fitbit 給的在地化名稱），沒有就退回 `exerciseType` 的英文代碼。
6. `activity_minutes` = `activeDuration` 秒數 ÷ 60，四捨五入。

運動有兩種來源，兩種都會被納入比較：

| 來源 | 特徵 | 有平均心率欄位嗎 |
|---|---|---|
| 手動在手錶上按開始的運動 | `exerciseEvents` 有 START / STOP，時間是整秒 | 有 `metricsSummary.averageHeartRateBeatsPerMinute` |
| 手錶自動偵測到的運動（SmartTrack） | 時間有毫秒，沒有 `exerciseEvents` | 沒有 |

同一段時間可能同時有手動和自動偵測兩筆，程式只看時長，不去重。

### 6.4 該活動的平均心率

```
如果 最長那筆運動有 metricsSummary.averageHeartRateBeatsPerMinute：
    直接用它
否則：
    POST .../dataTypes/heart-rate/dataPoints:rollUp
    {
      "range": {"startTime": "<運動開始 UTC>", "endTime": "<運動結束 UTC>"},
      "windowSize": "<運動總秒數>s"
    }
    取回傳的 heartRate.beatsPerMinuteAvg，四捨五入成整數
```

兩條路算的都是**該次運動期間**的平均。前者由 Fitbit 算，後者由 Google 對同一時段的心率樣本算，意義相同。
如果那段時間手錶沒有心率樣本（例如沒戴），會是 `null`。

### 6.5 睡眠時長

1. `GET .../dataTypes/sleep/dataPoints?pageSize=25&filter=sleep.interval.end_time >= "<起始日前一天 00:00Z>"`。
   多抓一天是為了避免時區邊界漏掉。
2. 每一筆睡眠用 `endTime + endUtcOffset` 歸到當地日期，範圍外的丟掉。
3. 同一天的所有睡眠段（主睡眠加小睡）把 `summary.minutesAsleep` 加總。

`minutesAsleep` 是扣掉睡眠期間醒著時段後的實際睡著分鐘，和 Fitbit app 顯示的「睡眠時間」相同。
如果要「躺在床上的總時間」，API 的欄位是 `summary.minutesInSleepPeriod`，本專案沒有輸出。

---

## 7. 授權與 token 行為

| 情況 | 程式做什麼 |
|---|---|
| 沒有 `google_tokens.json` | 開瀏覽器走完整授權，存檔 |
| 有 token 且未過期 | 直接用 |
| 有 token 但 access token 過期（約 1 小時） | 用 refresh token 靜默換新，存檔，不開瀏覽器 |
| 加 `--reauth` | 忽略現有 token，開瀏覽器重新授權，覆寫存檔 |

Testing 狀態的 OAuth app，refresh token **7 天會失效**。失效後程式會自動退回開瀏覽器授權，不需要手動刪檔。
想要每次 demo 都讓對方看到授權畫面，就用 `--reauth`。

授權流程是標準的 OAuth 2.0 Authorization Code + PKCE，由 `google-auth-oauthlib` 處理：程式在本機開一個隨機 port 的 HTTP server，Google 授權完成後把 code 導回這個 port，程式再拿 code 換 token。全程不經過任何第三方伺服器。

---

## 8. 程式結構

```
main.py          解析參數 → HealthApi().fetch_daily() → 印表格 → 寫 CSV / JSON
health_api.py    所有 Google Health API 呼叫與資料整理（本專案的核心）
google_auth.py   取得 access token（含 token 快取與 --reauth）
models.py        DailyRecord：一天一列的資料結構，也定義 CSV 欄位順序
config.py        讀 .env、scope 清單、檔案路徑、API base URL
```

`health_api.py` 的流程：

```
fetch_daily(start, end)
 ├─ _steps()             steps dailyRollUp              → {date: steps}
 ├─ _longest_exercise()  exercise list（翻頁）           → {date: 最長的那筆運動}
 ├─ _sleep()             sleep list（filter >=）         → {date: 睡著分鐘加總}
 └─ 逐日組 DailyRecord；運動沒有平均心率的話呼叫 _avg_hr() 用 heart-rate rollUp 補算
```

所有 HTTP 都走 `_request()`：印出方法、端點、狀態碼；遇到 5xx 自動重試 3 次（間隔 2、4、8 秒）；其他非 200 直接丟錯。

7 天的資料大約 10 到 15 次 API 呼叫，幾秒內跑完。

---

## 9. Google Health API 實測筆記

以下是 2026-10-01 用真實帳號打出來的行為，有幾項和官方文件不一致，程式都已經繞過：

| 項目 | 文件說法 | 實際行為 | 程式怎麼處理 |
|---|---|---|---|
| `list` 的 `filter` | 支援 AIP-160 語法 | 只接受**單一 `>=`**。`>`、`=`、`<=`、`AND` 都回 400 `INVALID_DATA_POINT_FILTER_RESTRICTION_COMPARATOR` | 只用 filter 設下界，上界在程式端過濾 |
| `exercise` 的 `filter` | 同上 | 連 `>=` 都回 400 | 不帶 filter，從新到舊翻頁到範圍外為止 |
| 回傳順序 | 未說明 | 新到舊 | 翻頁時看到比起始日早的點就停 |
| `civilEndTime` | DataPoint 有這個欄位 | `list` 回傳沒有，只有 `endTime` + `endUtcOffset` | 自己換算當地日期 |
| `pageSize` | 預設 1440、上限 10000 | `exercise`、`sleep` 上限 25 | 這兩種固定帶 25 |
| `dailyRollUp` 範圍上限 | heart-rate / active-minutes 14 天，其餘 90 天 | 同文件 | `--days` 超過 90 會失敗 |
| 數值型別 | — | int64 一律是**字串**（`"countSum": "3822"`），float 是數字 | 全部轉型 |
| 穩定性 | — | 偶爾回 503 `UNAVAILABLE`，重試就好 | 5xx 自動重試 3 次 |
| 自動偵測的運動 | — | 沒有 `averageHeartRateBeatsPerMinute` | 用 heart-rate rollUp 補算 |

---

## 10. 常見錯誤排除

| 畫面上看到 | 原因 | 怎麼解 |
|---|---|---|
| `找不到 .../client_secret.json` | 還沒下載 OAuth client JSON，或檔名不對 | 回第 2.5 節，檔名必須是 `client_secret.json`，放在專案根目錄 |
| 瀏覽器：**Error 403: access_denied** | 你的帳號不在測試使用者名單 | 第 2.3 節加入帳號 |
| 瀏覽器：**Error 400: redirect_uri_mismatch** | OAuth client 建成 Web application | 第 2.5 節重建一個 **Desktop app** 類型的 client |
| 瀏覽器：**Google hasn't verified this app** | 正常，Testing 狀態都會出現 | 按 Continue |
| `Google Health API 403` | 專案沒有 Health API 存取權，或 API 沒啟用 | 第 2.1 節確認已 Enable；仍 403 就是 Google 尚未開放給這個專案 |
| `Google Health API 403` 且訊息提到 `insufficient scope` | Data Access 少加 scope，或 token 是舊的 scope 組合 | 第 2.4 節補齊，然後 `--reauth` |
| `Google Health API 400 ... INVALID_DATA_POINT_FILTER` | filter 語法被拒 | 不應該發生，若發生代表 API 行為又變了，見第 9 節 |
| `Google Health API 503` 重試三次仍失敗 | Google 端暫時故障 | 等幾分鐘再跑 |
| 某天 `steps` 是空的 | 那天手錶沒同步，或還沒戴 | 手機開 Fitbit app 同步後再抓 |
| 某天 `activity_*` 是空的 | 那天沒有任何運動紀錄（手動或自動偵測） | 正常 |
| 某天 `activity_avg_hr` 是空的，但有 `activity_minutes` | 該運動期間沒有心率樣本 | 正常，通常是沒戴錶的手動紀錄 |
| 某天 `sleep_minutes` 是空的 | 那天沒有醒來的睡眠段，或還沒同步 | 正常 |
| `invalid_grant` / 直接跳出瀏覽器授權 | refresh token 過期（Testing app 7 天） | 正常，重新授權即可 |

---

## 11. 安全性：哪些檔案不能外流

| 檔案 | 內容 | 已在 .gitignore |
|---|---|---|
| `client_secret.json` | OAuth client ID 與 secret，拿到可以冒充你的 app | 是 |
| `google_tokens.json` | 你的 access / refresh token，拿到可以讀你的健康資料 | 是 |
| `.env` | 指向 client_secret.json 的路徑 | 是 |
| `output/` | 你的健康資料 | 是 |

要撤銷授權：到 https://myaccount.google.com/permissions 找到這個 app 移除，然後刪掉 `google_tokens.json`。

本專案只要求三個 **readonly** scope，無法寫入或刪除任何資料。

---

## 12. 參考資料

- Google Health API 首頁 https://developers.google.com/health
- Cloud 專案與 OAuth 設定 https://developers.google.com/health/setup
- 端點總覽 https://developers.google.com/health/endpoints
- Scope 清單 https://developers.google.com/health/scopes
- REST 參考（含 APIs Explorer） https://developers.google.com/health/reference/rest
- `dailyRollUp` https://developers.google.com/health/reference/rest/v4/users.dataTypes.dataPoints/dailyRollUp
- `list` https://developers.google.com/health/reference/rest/v4/users.dataTypes.dataPoints/list
- 運動資料型別 https://developers.google.com/health/data-types/workouts
- 睡眠資料型別 https://developers.google.com/health/data-types/sleep
- 從 Fitbit Web API 遷移 https://developers.google.com/health/migration
