#!/usr/bin/env python3
"""
TW Data Cross-Validator — Agent 1 (Data Researcher) 的量化數據交叉驗證工具

CLI subcommands:
  fetch     從 FinMind 免費 API 抓一個 dataset 的原始資料
  finlab    從 finlab 套件抓同一指標（需要本機已 pip install finlab 且已設定 API token；
            沒有 token 時直接跳過，不報錯中斷，回傳 skipped 狀態）
  compare   比對兩個數值，回傳 一致 / 不一致，附誤差百分比

不需要任何 API key 即可使用 fetch（FinMind 免註冊額度 600 次/hr）。
finlab 是可選的第二來源，沒有設定時不會擋住流程——這對應「先用免費方案」的決定。

範例：
  python3 cross_validate_tw_data.py fetch --stock_id 2330 --dataset TaiwanStockMonthRevenue --start_date 2024-01-01
  python3 cross_validate_tw_data.py compare --value_a 225221263000 --value_b 225200000000 --tolerance 0.005
"""

import argparse
import json
import sys
import urllib.request
import urllib.parse
import urllib.error

FINMIND_URL = "https://api.finmindtrade.com/api/v4/data"

# 常用 dataset 對照，方便 Agent 1 查閱，不代表僅限這些
KNOWN_DATASETS = {
    "TaiwanStockFinancialStatements": "財務報表（損益/資產負債/現金流項目）",
    "TaiwanStockMonthRevenue": "月營收",
    "TaiwanStockPrice": "股價（日）",
    "TaiwanStockDividend": "股利政策",
    "TaiwanStockPER": "本益比/股價淨值比/殖利率",
}


def fetch_finmind(dataset: str, stock_id: str, start_date: str, end_date: str = None,
                   user_id: str = None, password: str = None, timeout: int = 15) -> dict:
    """呼叫 FinMind 公開 API，回傳 (success, data_or_error)"""
    params = {"dataset": dataset, "data_id": stock_id, "start_date": start_date}
    if end_date:
        params["end_date"] = end_date
    if user_id:
        params["user_id"] = user_id
    if password:
        params["password"] = password

    url = f"{FINMIND_URL}?{urllib.parse.urlencode(params)}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "equity-research-tw/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = json.loads(resp.read().decode("utf-8"))
            return {"success": True, "source": "FinMind", "dataset": dataset,
                     "stock_id": stock_id, "data": body.get("data", []),
                     "row_count": len(body.get("data", []))}
    except urllib.error.HTTPError as e:
        return {"success": False, "source": "FinMind", "error": f"HTTP {e.code}"}
    except urllib.error.URLError as e:
        return {"success": False, "source": "FinMind", "error": str(e.reason)}
    except Exception as e:
        return {"success": False, "source": "FinMind", "error": str(e)}


def fetch_finlab(dataset_hint: str, stock_id: str) -> dict:
    """
    嘗試用 finlab 套件抓資料。沒有安裝套件或沒有設定 token 時回傳 skipped，
    不視為錯誤——finlab 是可選的第二驗證來源。
    """
    try:
        import finlab  # noqa: F401
        from finlab import data as finlab_data
    except ImportError:
        return {"success": False, "skipped": True, "source": "finlab",
                 "reason": "finlab 套件未安裝（免費方案下為預期狀態，略過此來源）"}

    import os
    token = os.environ.get("FINLAB_API_TOKEN")
    if not token:
        return {"success": False, "skipped": True, "source": "finlab",
                 "reason": "未偵測到 FINLAB_API_TOKEN，略過此來源（免費方案下為預期狀態）"}

    try:
        finlab.login(token)
        df = finlab_data.get(dataset_hint)
        if stock_id in df.columns:
            series = df[stock_id].dropna()
            latest = series.iloc[-1] if len(series) else None
            return {"success": True, "source": "finlab", "dataset": dataset_hint,
                     "stock_id": stock_id, "latest_value": latest}
        return {"success": False, "source": "finlab", "error": f"{stock_id} 不在資料集欄位中"}
    except Exception as e:
        return {"success": False, "source": "finlab", "error": str(e)}


def compare_values(value_a: float, value_b: float, tolerance: float = 0.02) -> dict:
    """
    比對兩個數值。tolerance 為相對誤差容許範圍（預設 2%）。
    財報數字建議收緊到 0.005（0.5%），股價等即時數據可放寬到 0.02-0.05。
    """
    if value_a is None or value_b is None:
        return {"verdict": "單一來源，未交叉驗證", "reason": "其中一個數值缺失"}

    if value_a == 0 and value_b == 0:
        return {"verdict": "一致", "diff_pct": 0.0}

    base = max(abs(value_a), abs(value_b), 1e-9)
    diff_pct = abs(value_a - value_b) / base

    if diff_pct <= tolerance:
        return {"verdict": "一致", "diff_pct": round(diff_pct, 6), "value_a": value_a, "value_b": value_b}
    return {"verdict": "不一致，需 MOPS 仲裁", "diff_pct": round(diff_pct, 6),
             "value_a": value_a, "value_b": value_b, "tolerance": tolerance}


def main():
    parser = argparse.ArgumentParser(description="TW equity data cross-validator")
    sub = parser.add_subparsers(dest="command", required=True)

    p_fetch = sub.add_parser("fetch", help="從 FinMind 抓資料")
    p_fetch.add_argument("--stock_id", required=True)
    p_fetch.add_argument("--dataset", required=True, help=f"可用: {', '.join(KNOWN_DATASETS)}（或其他 FinMind 支援的 dataset）")
    p_fetch.add_argument("--start_date", required=True)
    p_fetch.add_argument("--end_date")
    p_fetch.add_argument("--user_id")
    p_fetch.add_argument("--password")

    p_finlab = sub.add_parser("finlab", help="嘗試從 finlab 抓同一指標（可選來源）")
    p_finlab.add_argument("--stock_id", required=True)
    p_finlab.add_argument("--dataset_hint", required=True, help="finlab data.get() 的資料集名稱")

    p_compare = sub.add_parser("compare", help="比對兩個數值")
    p_compare.add_argument("--value_a", required=True, type=float)
    p_compare.add_argument("--value_b", required=True, type=float)
    p_compare.add_argument("--tolerance", type=float, default=0.02)

    args = parser.parse_args()

    if args.command == "fetch":
        result = fetch_finmind(args.dataset, args.stock_id, args.start_date,
                                 args.end_date, args.user_id, args.password)
    elif args.command == "finlab":
        result = fetch_finlab(args.dataset_hint, args.stock_id)
    elif args.command == "compare":
        result = compare_values(args.value_a, args.value_b, args.tolerance)
    else:
        parser.error("unknown command")
        return

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
