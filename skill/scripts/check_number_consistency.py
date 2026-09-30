#!/usr/bin/env python3
"""
數字一致性檢查 — 找出同一指標在不同章節出現不同數值卻未說明原因的情形

實測背景（8 家台股樣本 × 4 家 LLM 評審，2026-09）：Multi-Agent 組正確性構面 32 筆評分
僅 1 筆滿分，失分原因中「跨章節同一指標數值不一致」佔 29%，且這類錯誤高度機械、
可程式化偵測。實際案例：
  - 鴻海：H1 EPS 正文寫 7.83、官方 7.84；營業利益率 3.72% 與 3.67% 並存於同一報告
  - 台達電：摘要寫淨利年增 86.3%、內文寫 EPS 年增 88.9%，未區分口徑
  - 勤誠：2025 全年營收三處寫 210.01 億，實際 220.01 億，且該數字被 DCF 引用
  - 川湖：宣稱目標價區間可回推自 60/40 加權公式，實算 10,567 對報告所載 12,000

本腳本不判斷「哪個數字才對」——那需要外部查證。它只負責把「同一指標名稱附近出現
多個不同數值」的位置全部列出來，交給人或 S7 逐一確認是口徑差異（需標註）還是錯誤（需修正）。

用法：
  python3 check_number_consistency.py --report [path]
  python3 check_number_consistency.py --report [path] --min-occurrences 2

已知殘留限制（2026-09，川湖2059/勤誠8210/鴻海2317/台達電2308測試批次實測後記錄，
已修正五類、刻意不追殺的一類）：
已修正：參考文獻編號 [19] 誤判為數值、月份「8月」誤判為數值、累計加總敘事
（「累計110.96元，再增50.24元，累計161.2元」）誤判為同期矛盾、LTM 未被辨識為期間
標記導致誤貼「單季」標籤、期間標記抓成整段上下文第一個而非離數字最近的那個、
DCF／估值章節裡 Bear/Base/Bull 情境分析並列數值（例：「Bear情境（…2027-29成長率
10%…）；Bull情境（…2027-29成長率28%…）」）因同句提及同一年份被誤判為同期矛盾
（見 SCENARIO_HINTS）、同一指標後方接續列出多個數值時（例：「FY2023至FY2025分別
約432.6億、394.6億、527.5億元」）僅抓到清單裡第一個數字、其餘全部漏抓（見
extract_number_list）——這個漏洞曾讓台達電2308一份報告裡「527.5億元」與DCF段落
誤寫的「52.75億元」（10倍單位錯誤）完全沒被本腳本比對到，屬本次修正動機最強的一類。
仍會殘留：公式／表格列裡「指標名稱)＝結果」這種寫法，「結果」有時會被誤判成該指標
本身的另一個數值（例：「14.16×15.21(LTM EPS)＝215.4元」，215.4 是算出來的股價不是
EPS，仍可能被誤抓）。這是刻意不修的取捨：唯一可靠的排除方式是「跳過緊接在＝號後面
的數字」，但這樣會連帶漏掉「毛利率＝24.8%」這種直接寫法的真實數值，兩害相權，選擇
保留少量誤報，而不是犧牲抓真錯誤的能力。

2026-09 新增第二種檢查（與數字一致性檢查互補，非取代）：公式覆算檢查
（check_arithmetic）。數字一致性檢查只能抓「同一指標出現不同數值」，但台達電2308
案例證明有一類更隱蔽的錯誤：報告內文直接寫出「A×B＝C」這類算式，且全篇只出現一次
（不構成「同一指標多個數值」的比對條件），但 A×B 實際上不等於 C。這類錯誤數字一致性
檢查天生抓不到，因為它比對的是「同一指標的不同數值」，不是「單一算式本身對不對」。
公式覆算檢查會掃描全文找出「運算式＝結果」的樣式（支援×÷+-與括號、單一運算元可帶%），
用 Python 自行重算一次，比對誤差是否超出容許範圍（預設 1%），抓出算式與結果不吻合的
情形。這只能覆核「報告有寫出算式」的部分——如果像台達電2308那次一樣，DCF五年折現的
中間步驟完全沒有攤開在正文只列輸入假設與最終數字，本檢查一樣抓不到，仍需要人工重算
（見 s7-synthesis.md 已新增之「多步驟公式須攤開關鍵過渡算式」規則，從源頭要求寫出來，
本檢查才有東西可以覆核）。
"""

import argparse
import re
import sys
from collections import defaultdict
from pathlib import Path

# 需要追蹤的指標關鍵詞。命中後往後抓一小段找數字。
METRICS = [
    "EPS", "每股盈餘", "營收", "毛利率", "營業利益率", "淨利率", "淨利",
    "目標價", "本益比", "股價淨值比", "ROE", "ROA", "自由現金流", "FCF",
    "資本支出", "市占率", "市佔率", "終值成長率", "WACC", "折現率",
    "市值",  # 2026-09 新增：台達電2308案例出現「市值4,740.5億元」與股本×股價
             # 換算之正確值（4.74兆元）相差10倍，2026-09 前未被追蹤
]

# 抓數字：支援 1,234.5 / 12.3% / 1.23億 / 3,800元 / 4.74兆元
# (?<![\d,.]) 確保不從逗號數字中間切入（否則 81,031 會被誤抓成 031）
# (?![\d]*\s*[月日]) 排除「8月」「15日」這類日期用數字，不是指標數值
# 「兆元」「兆」須排在「億元」「億」之前，避免「兆」被單獨截斷成不完整單位
NUM = re.compile(
    r"(?<![\d,.])(\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?)"
    r"(?!\s*[月日])\s*(%|％|兆元|兆|億元|億|元|倍|pp|個百分點)?"
)

# 同一指標接續列出多個數值時的分隔符（頓號/逗號），例：
# 「FY2023至FY2025自由現金流分別約432.6億、394.6億、527.5億元」
LIST_SEP = re.compile(r"^[、，,]\s*")

# 「[19]」「[19][20]」這類參考文獻編號，數字上下文若緊貼方括號，一律排除
CITATION = re.compile(r"\[\s*\d+(?:\]\s*\[\s*\d+)*\s*\]")

# 累計/加總語境關鍵詞：句子裡出現這些詞時，多個數值多半是「A+B=C」的敘事關係，
# 不是同一期間的矛盾版本（例：「累計110.96元，7月再增50.24元，累計前七月161.2元」）
CUMULATIVE_HINTS = ["累計", "再增", "自結", "加計", "合計", "加上", "累加", "計入"]

# 情境分析語境關鍵詞：DCF／估值章節常見「Bear情境（…）；Bull情境（…）」並列寫法，
# 這些數值本來就「設計上就該不同」，不是矛盾版本。句子裡常同時提到同一年份
# （例：「Bear情境（…2027-29成長率10%…）；Bull情境（…2027-29成長率28%…）」），
# 導致期間標記都抓到「2027」而被誤判為同期矛盾。
SCENARIO_HINTS = ["Bear", "Base", "Bull", "悲觀情境", "樂觀情境", "保守情境",
                  "基準情境", "情境（", "情境(", "情境一", "情境二", "情境三"]

# 這些章節本來就會並列多個版本或多家公司數字，屬於刻意揭露／合理並存，不列為衝突
EXEMPT_SECTIONS = ["資料完整性與查證紀錄", "時效稽核表", "紅隊挑戰清單",
                   "資料缺口與限制", "參考資料", "結論影響追蹤",
                   "同業比較", "競爭地位"]

# 期間標記：同一指標若分屬不同期間，數值不同屬正常
PERIOD = re.compile(r"(20\d{2}\s*年?(?:上半年|下半年|全年)?(?:第[一二三四]季)?|[1-4]H\d{2}|H[12]|Q[1-4]|20\d{2}Q[1-4]|TTM|LTM|近四季|單季|全年|上半年)")


def split_sections(text):
    """回傳 [(section_title, body_text, start_line), ...]"""
    lines = text.split("\n")
    out, cur, buf, start = [], "(前言)", [], 1
    for i, ln in enumerate(lines, 1):
        if ln.startswith("## "):
            out.append((cur, "\n".join(buf), start))
            cur, buf, start = ln.lstrip("#").strip(), [], i
        else:
            buf.append(ln)
    out.append((cur, "\n".join(buf), start))
    return out


def is_exempt(title):
    return any(k in title for k in EXEMPT_SECTIONS)


def _is_valid_candidate(val, unit):
    """跟主迴圈同一套過濾邏輯：排除年份（無單位、1900-2100之間）與無單位裸小數字
    （多半是誤抓，如「21位分析師」的21、「2308」股票代號）。共用同一函式，避免
    extract_number_list 用另一套（沒有這些過濾）而抓進雜訊。"""
    plain = val.replace(",", "")
    try:
        f = float(plain)
    except ValueError:
        return False
    if unit == "" and (1900 < f < 2100):
        return False
    if unit == "" and f < 100:
        return False
    return True


def extract_number_list(text, pos, limit=6):
    """從 pos（緊接在第一個數字之後）開始，嘗試延伸抓取以頓號/逗號分隔的同指標
    數值清單（例：「分別約432.6億、394.6億、527.5億元」中，第一個數字已由呼叫端
    抓到，這裡負責抓後面的394.6億、527.5億元）。

    中文慣例是只有清單最後一個成員帶單位，前面的成員共用它——因此若某成員自己
    沒有比對到單位，就套用清單裡最後一個有單位成員的單位；若該成員自己就寫了
    單位（不同於整份清單常態，但仍可能發生），則保留自己的，不覆蓋。

    每個成員在借用單位之前，先以自己當下的單位跑一次 _is_valid_candidate；不合格
    就視為清單已結束（停止延伸，不是跳過），避免把清單後面湊巧出現、跟原指標
    無關的數字（例如「21位分析師」的21）也吃進來。

    回傳 [[val, unit], ...]，最多 limit 筆，避免異常文字讓清單無限延伸。
    """
    items = []
    while len(items) < limit:
        sep = LIST_SEP.match(text[pos:pos + 3])
        if not sep:
            break
        after_sep = pos + sep.end()
        m = NUM.match(text, after_sep)
        if not m:
            break
        val, unit = m.group(1), m.group(2) or ""
        if not _is_valid_candidate(val, unit):
            break  # 清單到此為止，不繼續往後掃描不相關的數字
        items.append([val, unit])
        pos = m.end()
    if items:
        last_unit = next((it[1] for it in reversed(items) if it[1]), "")
        if last_unit:
            for it in items:
                if not it[1]:
                    it[1] = last_unit
    return items


def extract(text, window=40):
    """回傳 {(metric, unit): {value: [context, is_cumulative], ...}}"""
    # 先把所有引用括號位置標記出來，數字落在這個範圍內的一律不採用
    citation_spans = [(m.start(), m.end()) for m in CITATION.finditer(text)]

    def in_citation(pos):
        return any(s <= pos < e for s, e in citation_spans)

    found = defaultdict(lambda: defaultdict(list))
    for m in METRICS:
        for hit in re.finditer(re.escape(m), text):
            # +8 字元緩衝：window 剛好切在數字中間會把「2308」切成「230」這種
            # 半截數字誤判成獨立候選值（實測台達電2308案例：股票代號2308被切成
            # 230，混進「目標價」候選池）。緩衝區只用來讓數字比對本身不被切斷，
            # 不影響 window 原本控制「往後找多遠」的語意。
            seg = text[hit.end(): hit.end() + window + 8]
            for nm in NUM.finditer(seg):
                abs_pos = hit.end() + nm.start()
                if in_citation(abs_pos):
                    continue  # 跳過參考文獻編號，換下一個候選數字
                val, unit = nm.group(1), nm.group(2) or ""
                if not _is_valid_candidate(val, unit):
                    continue
                break  # 找到第一個有效候選就停止，不繼續掃描 seg 內其他數字
            else:
                continue
            ctx = text[max(0, hit.start() - 30): hit.end() + window].replace("\n", " ")
            # 期間標記要抓「離這個數字最近」的那一個，不是整段上下文裡第一個出現的。
            # 一句話常常橫跨好幾個年份（「2022年X億，2023年因...降至Y億」），若用整段
            # ctx 找第一個年份，Y 會被誤貼上 2022 年的標籤。改成只在數字前方一小段（同一
            # 分句範圍，遇到「，」「。」「；」就不再往前找）裡找最近的期間標記。
            before_num = text[max(0, abs_pos - 20): abs_pos]
            cut = max((before_num.rfind(c) for c in "，。；"), default=-1)
            local = before_num[cut + 1:]
            pm_local = PERIOD.findall(local)
            if pm_local:
                period = pm_local[-1]
            else:
                pm = PERIOD.findall(ctx)
                period = pm[0] if pm else "(未標期間)"
            # 正規化：裸年份「2025」跟「2025年」語意相同，但字串不同會被當成兩個
            # 不同期間、逃過同期矛盾偵測（例：「FY2025」裡的2025沒有「年」字，
            # 而清單展開指派的「2025年」有）。統一成「NNNN年」格式再比對。
            if re.fullmatch(r"20\d{2}", period):
                period += "年"
            # 累計／情境語境判斷不能用會往後延伸一整個 window 的 ctx——那樣會把
            # 「同一長句裡、這個數字之後才出現、描述另一件事」的詞也算進來。實測
            # 案例：「…Base案WACC設定為8.5%。以FY2025實際自由現金流52.75億元為
            # 基期，設定…：Bear情境（…）」，52.75億元其實是三個情境共用的基期，
            # 不是任何一個情境「本身」的數值，但因為「Bear情境」剛好出現在同一句
            # 稍後的位置，被 ctx 掃進來，導致這筆真錯誤被誤判成情境分析、整組
            # 降級成待確認。改成只看「往前 30 字＋這個數字本身」，不再往後延伸到
            # window 底，同時仍保留原本 ctx（往後完整延伸）供人類閱讀例句之用。
            # 往前也要在句界（。／；）處截斷，不能只靠固定 30 字——「Base案WACC
            # 設定為8.5%。以FY2025實際自由現金流52.75億元」這句裡，"Base" 在
            # 「。」之前，屬於上一句，固定 30 字視窗仍抓得到、造成誤判，改成
            # 遇到句界就不再往前找（情境子項之間常用「、」分隔，不當句界，
            # 「、」不在截斷字元清單內，同一情境子項內的其餘子項仍抓得到）。
            before_hit = text[max(0, hit.start() - 60): hit.start()]
            cut2 = max((before_hit.rfind(c) for c in "。；"), default=-1)
            scen_start = max(0, hit.start() - 60) + cut2 + 1
            scen_end = hit.end() + nm.end() + 5
            scen_ctx = text[scen_start: scen_end].replace("\n", " ")
            is_cum = any(k in scen_ctx for k in CUMULATIVE_HINTS)
            is_scen = any(k in scen_ctx for k in SCENARIO_HINTS)
            found[(m, unit)][val].append((ctx.strip(), period, is_cum, is_scen))

            # 同一指標接續列出多個數值的清單（例：「FY2023至FY2025分別約432.6億、
            # 394.6億、527.5億元」）——上面只抓到清單第一個數字，這裡把後面的
            # 也抓出來，避免像台達電2308案例那樣，清單裡的527.5億元完全沒進比對池。
            extra = extract_number_list(text, hit.end() + nm.end())
            if extra:
                # 若「本句」前段有「20xx至20xx」這類年份區間、且項數剛好對得上
                # （含第一個數字），依序把年份分別指派給清單各成員，比單一期間
                # 標記更精確；對不上就沿用第一個數字算出的期間，仍比完全漏抓好。
                yr_range = re.search(r"(20\d{2})\D{0,4}(?:至|到|[-~])\D{0,4}(20\d{2})", local) \
                    or re.search(r"(20\d{2})\D{0,4}(?:至|到|[-~])\D{0,4}(20\d{2})", ctx)
                seq_periods = None
                if yr_range:
                    y0, y1 = int(yr_range.group(1)), int(yr_range.group(2))
                    if 0 < y1 - y0 < 10 and (y1 - y0 + 1) == len(extra) + 1:
                        seq_periods = [f"{y}年" for y in range(y0, y1 + 1)]
                # 清單延伸出來的成員，累計／情境語境旗標不沿用第一個數字的判斷——
                # 「本季累計減上季累計」這種方法論說明句，跟它介紹的清單裡個別
                # 數字（分別為哪一年的數字）之間並非「A+B=C」關係，若沿用會連帶
                # 把清單其餘成員也一起降級，讓真錯誤被誤判成加總敘事而漏掉（實測
                # 案例：527.5億元因此被降級，跟52.75億元的同期矛盾被整組蓋過）。
                # 兩害相權，清單成員預設不繼承，寧可稍微擴大待查範圍。
                for i, (v2, u2) in enumerate(extra):
                    p2 = seq_periods[i + 1] if seq_periods else period
                    found[(m, u2)][v2].append((ctx.strip(), p2, False, False))
    return found


# 公式覆算檢查：找出正文裡「運算式＝結果」的樣式，自行重算一次比對誤差。
# 運算式允許：數字、逗號、小數點、× x X * ÷ / ％ % ＋ + － - 空白、括號，以及
# ＝／= 本身——後者刻意也算進允許字元，因為財報常見「A＝B＝C」鏈式寫法
# （例：「0.40×831+0.30×1,124.5+0.30×1,525＝332.40+337.35+457.50＝1,127.25元」，
# 先各自算出三個加權項、再相加、最後才是總數）。若把「＝」當成硬邊界只抓
# 第一段=第二段，會把「332.40」誤判成「整個算式的最終結果」而不是加總鏈的
# 中繼值，做出錯誤的「不吻合」判定——這是實測時抓到的真實誤報，比對象是
# 勤誠8210報告裡本身完全正確的算式。改成抓「整段連續的算式字元（含所有＝）」
# 再用 Python 自行切段、逐一比對相鄰兩段是否相等，而不是只比對頭尾。
CHAIN_CHARS = r"\d,\.\s×xX\*÷/％%\+\-＋－\(\)=＝"
CHAIN_RUN = re.compile(rf"\d[{CHAIN_CHARS}]*")


def _safe_eval_arith(expr):
    """把中文/全形運算子正規化後，用受限的 eval 算出算式的值。算不出來回傳 None。"""
    s = expr.strip()
    s = (s.replace("×", "*").replace("x", "*").replace("X", "*")
           .replace("÷", "/").replace("＋", "+").replace("－", "-")
           .replace("（", "(").replace("）", ")").replace(",", "")
           .replace("，", ""))
    # 「11.35%」這種帶百分比的運算元，換成 (11.35/100) 再算
    s = re.sub(r"(\d+(?:\.\d+)?)\s*[%％]", r"(\1/100)", s)
    s = s.replace(" ", "")
    if not s or not re.fullmatch(r"[\d\.\+\-\*/\(\)]+", s):
        return None
    if s.count("(") != s.count(")"):
        return None
    try:
        val = eval(s, {"__builtins__": {}}, {})  # noqa: S307 — 字元已白名單過濾，僅供算術
    except Exception:
        return None
    if not isinstance(val, (int, float)):
        return None
    return float(val)


def check_arithmetic(text, tolerance=0.02):
    """掃描全文找「運算式＝運算式（＝運算式...）」的連續片段，切成多段後逐一比對
    相鄰兩段是否相等（而非只比對頭尾，見上方 CHAIN_RUN 註解）。回傳不吻合的清單：
    [(前一段原文, 後一段原文, 前段算出值, 後段算出值, 相對誤差), ...]

    只能覆核「報告有寫出算式」的部分；若多步驟公式（例如五年期DCF逐年折現）只在
    正文列出輸入假設與最終數字、沒有攤開任何中間過渡算式，本函式無算式可覆核，
    仍需要人工重算（這正是台達電2308 DCF案例會漏掉的情況——S7應主動攤開至少
    關鍵過渡算式，見 s7-synthesis.md，本函式才有東西可查）。
    """
    text_norm = text.replace("新台幣", "")  # 「＝新台幣1,127.25元」會讓字元類斷在等號處
    citation_spans = [(m.start(), m.end()) for m in CITATION.finditer(text_norm)]

    def in_citation(pos):
        return any(s <= pos < e for s, e in citation_spans)

    mismatches = []
    for m in CHAIN_RUN.finditer(text_norm):
        span = m.group(0)
        if in_citation(m.start()):
            continue
        if "＝" not in span and "=" not in span:
            continue  # 沒有等號，只是段落裡湊巧出現的數字／百分比序列
        segments = re.split(r"[=＝]", span)
        if len(segments) < 2:
            continue
        if not re.search(r"[×xX\*÷/＋－\+\-]", span):
            continue  # 純數字接龍（不含任何運算子）不算算式，避免誤判
        values = [_safe_eval_arith(seg) for seg in segments]
        for i in range(len(values) - 1):
            a, b = values[i], values[i + 1]
            if a is None or b is None or b == 0:
                continue
            diff = abs(a - b) / abs(b)
            if diff > tolerance:
                mismatches.append((segments[i].strip(), segments[i + 1].strip(), a, b, diff))
    return mismatches


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--report", required=True)
    ap.add_argument("--min-occurrences", type=int, default=2,
                    help="同一指標出現幾種不同數值才視為需檢查（預設 2）")
    args = ap.parse_args()

    path = Path(args.report)
    if not path.exists():
        print(f"檔案不存在: {path}")
        sys.exit(1)
    text = path.read_text(encoding="utf-8")

    sections = [(t, b) for t, b, _ in split_sections(text) if not is_exempt(t)]
    body = "\n".join(b for _, b in sections)

    # 公式覆算檢查掃描全文（含查證紀錄章節），跟數字一致性檢查用的排除清單無關——
    # 一個算式對不對，不會因為它出現在哪個章節就不需要覆核。
    arith_mismatches = check_arithmetic(text)

    found = extract(body)
    issues = []
    for (metric, unit), vals in found.items():
        if len(vals) >= args.min_occurrences:
                issues.append((metric, unit, vals))

    print("=" * 66)
    print(f"數字一致性檢查: {path.name}")
    print("=" * 66)
    print(f"掃描章節數（已排除查證紀錄類）: {len(sections)}")
    print(f"追蹤指標數: {len(METRICS)}")
    print()

    print("─" * 66)
    print("公式覆算檢查（掃描全文「算式＝結果」樣式，自行重算比對）")
    print("─" * 66)
    if not arith_mismatches:
        print("✅ 未發現算式與結果不吻合的情形（僅能覆核報告有寫出算式的部分）")
    else:
        for seg_a, seg_b, val_a, val_b, diff in arith_mismatches:
            print(f"  ✗ 「{seg_a}」算出 {val_a:g}，但下一段「{seg_b}」寫的是 {val_b:g}"
                  f"（誤差 {diff*100:.1f}%）")
    print()

    if not issues:
        if not arith_mismatches:
            print("✅ 未發現同一指標出現多個不同數值")
            sys.exit(0)
        else:
            print("數字一致性檢查未發現同一指標多版本問題，但上方公式覆算檢查有不吻合項目，")
            print("請優先處理。")
            sys.exit(1)

    # 風險分級：同一指標＋同一期間卻出現不同數值 → 高風險（真正的矛盾）
    #           各數值分屬不同期間 → 待確認（多半是正常的期間差異）
    # 累計語境／情境分析語境豁免：若「同一期間、不同值」的那幾筆裡，任一筆的上下文含
    # 累計/再增等關鍵詞（CUMULATIVE_HINTS，A+B=C 加總敘事）或 Bear/Base/Bull 等情境
    # 關鍵詞（SCENARIO_HINTS，情境分析本來就該給不同數值），降級為待確認而非高風險。
    high, review = [], []
    for metric, unit, vals in issues:
        by_period = {}
        for v, items in vals.items():
            for _, per, is_cum, is_scen in items:
                by_period.setdefault(per, {}).setdefault(v, False)
                by_period[per][v] = by_period[per][v] or is_cum or is_scen

        clash = {}
        for p, vmap in by_period.items():
            if p == "(未標期間)" or len(vmap) <= 1:
                continue
            if any(vmap.values()):   # 這個期間內任一數值帶有累計語境提示 → 視為加總敘事，不算衝突
                continue
            clash[p] = set(vmap.keys())
        (high if clash else review).append((metric, unit, vals, clash))

    def dump(group, tag):
        for metric, unit, vals, clash in group:
            u = f"（單位：{unit}）" if unit else ""
            print(f"{tag} {metric}{u} — {len(vals)} 種數值")
            if clash:
                for per, vs in clash.items():
                    print(f"    ⚠ 同屬「{per}」卻有 {len(vs)} 個不同值：{'、'.join(sorted(vs))}{unit}")
            for v, items in sorted(vals.items(), key=lambda x: -len(x[1])):
                periods = sorted({p for _, p, _, _ in items})
                tags = []
                if any(c for _, _, c, _ in items):
                    tags.append("含累計語境")
                if any(s for _, _, _, s in items):
                    tags.append("含情境分析語境")
                cum = f"（{'、'.join(tags)}）" if tags else ""
                print(f"    {v}{unit}  出現 {len(items)} 次  期間：{'、'.join(periods)}{cum}")
                print(f"      例：…{items[0][0][:74]}…")
            print()

    print(f"高風險（同期間不同值）{len(high)} 項｜待確認（期間不同，多為正常）{len(review)} 項\n")
    if high:
        print("─" * 66)
        print("【高風險】同一指標在相同期間出現不同數值，極可能是錯誤或口徑未交代")
        print("─" * 66)
        dump(high, "●")
    if review:
        print("─" * 66)
        print("【待確認】各數值分屬不同期間或未標期間，多數為正常，仍請掃過一遍")
        print("─" * 66)
        dump(review, "○")

    print("註：本檢查只負責找出並列的不同數值，不判斷何者正確。")
    print("    合理情況（不同期間、不同公司、不同情境假設）請確認報告內已明確區分口徑。")
    sys.exit(1)


if __name__ == "__main__":
    main()
