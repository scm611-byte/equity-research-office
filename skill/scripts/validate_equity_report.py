#!/usr/bin/env python3
"""
Equity Report Validator — 專屬台股財報分析報告的結構檢查

跟 deep-research 的 validate_report.py 不同：那支腳本是為一般研究報告寫的
（Introduction/Main Analysis/Synthesis/Limitations/Recommendations），套用在
equity-research-tw 產出的報告上，「Required Sections」一定會 FAIL——不是報告有問題，
是檢查項目對不上。這支腳本改用 templates/final_report_template.md 的實際章節結構檢查。

用法：
  python3 validate_equity_report.py --report [path]
"""

import argparse
import re
import sys
from pathlib import Path

REQUIRED_SECTIONS = [
    "評等摘要",
    "執行摘要",
    "公司概況",
    "市場與產業展望",
    "競爭地位",
    "同業比較",
    "財務分析",
    "估值分析",
    "投資論點",
    "主要風險",
    "資料完整性與查證紀錄",
    "資料缺口與限制",
    "參考資料",
]

PLACEHOLDER_PATTERNS = [
    r"\bTBD\b", r"\bTODO\b", r"內容過長省略", r"\.\.\.\(略\)", r"\[待補\]",
    r"\[\d+-\d+\]\s*其餘略",
    r"待.{0,12}填入", r"待.{0,15}完成後", r"待.{0,15}審查完成", r"待.{0,15}複核完成",
]

# 2330 案例（第三批財報，2026-08）實測發現的漏洞：check_freshness_and_redteam() 舊版只檢查
# 「紅隊挑戰清單」「時效稽核表」這兩個標題字串是否存在，但空殼版本的標題本身就完整寫著
# 「### 紅隊挑戰清單（Agent 3 Red Team Reviewer）」，底下只接一句「（待Agent 3獨立審查完成後
# 填入...）」——字串比對照樣 PASS，完全沒抓到「有標題、沒內容」這種半成品。新增
# MIN_SECTION_BODY_CHARS 門檻與 check_section_has_substance()，強制檢查標題後面的內文長度與
# 結構性內容是否存在，不能只憑標題字串出現就判定過關。
MIN_SECTION_BODY_CHARS = 150


def read_report(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def check_sections(text: str):
    missing = [s for s in REQUIRED_SECTIONS if s not in text]
    return missing


def check_placeholders(text: str):
    hits = []
    for pat in PLACEHOLDER_PATTERNS:
        if re.search(pat, text):
            hits.append(pat)
    return hits


def check_citation_bibliography_match(text: str):
    """正文引用編號集合，跟參考資料條目編號集合是否一致（無缺漏、無多餘）"""
    body_split = text.split("## 參考資料")
    if len(body_split) < 2:
        return None, None, "找不到 '## 參考資料' 標題（注意：標題必須是這個字，不是 '## Bibliography' 或 '## Sources'）"
    body, biblio = body_split[0], body_split[1]

    cited = set(int(n) for n in re.findall(r"\[(\d+)\]", body))
    biblio_entries = set(int(n) for n in re.findall(r"^\[(\d+)\]", biblio, re.MULTILINE))

    missing_in_biblio = cited - biblio_entries
    extra_in_biblio = biblio_entries - cited
    return missing_in_biblio, extra_in_biblio, None


def check_bibliography_urls(text: str):
    """每條參考資料條目是否都附了真實 URL（http/https），不是只有文字來源名稱"""
    body_split = text.split("## 參考資料")
    if len(body_split) < 2:
        return []
    biblio_section = body_split[1].split("## ")[0]  # 到下一個 ## 標題前
    entries = re.findall(r"^\[(\d+)\][^\n]*", biblio_section, re.MULTILINE)
    no_url = []
    for entry_num_match in re.finditer(r"^\[(\d+)\](.*?)(?=^\[\d+\]|\Z)", biblio_section, re.MULTILINE | re.DOTALL):
        num, content = entry_num_match.group(1), entry_num_match.group(2)
        if not re.search(r"https?://", content):
            no_url.append(num)
    return no_url


def _section_body_after(text: str, heading_substr: str) -> str:
    """抓出包含 heading_substr 的那一行標題之後、到下一個同級或更高級標題之前的內文。"""
    lines = text.split("\n")
    start = None
    start_level = None
    for i, line in enumerate(lines):
        if line.lstrip().startswith("#") and heading_substr in line:
            start = i
            start_level = len(line) - len(line.lstrip("#"))
            break
    if start is None:
        return ""
    body_lines = []
    for line in lines[start + 1:]:
        if line.lstrip().startswith("#"):
            level = len(line) - len(line.lstrip("#"))
            if level <= start_level:
                break
        body_lines.append(line)
    return "\n".join(body_lines)


def check_freshness_and_redteam(text: str):
    """Agent 2（時效稽核表，Evidence Curator Step 4）與 Agent 3（紅隊挑戰清單）的產出是否確實附入報告，
    且底下要有真正的內容，不能只有標題字串本身就判定過關（見上方 2330 案例說明）。"""
    missing = []

    freshness_body = _section_body_after(text, "時效稽核表")
    if "時效稽核表" not in text:
        missing.append("時效稽核表（Agent 2 Evidence Curator · Step 4 時效性掃描產出，應在「資料完整性與查證紀錄」章節）")
    elif len(freshness_body.strip()) < MIN_SECTION_BODY_CHARS or "|" not in freshness_body:
        missing.append(
            f"時效稽核表標題存在，但底下內文過短或缺少表格（{len(freshness_body.strip())} 字，"
            f"需 ≥{MIN_SECTION_BODY_CHARS} 字且含 markdown 表格），疑似空殼／未真正執行時效性掃描"
        )

    redteam_body = _section_body_after(text, "紅隊挑戰清單")
    if "紅隊挑戰清單" not in text:
        missing.append("紅隊挑戰清單（Agent 3 Red Team Reviewer 產出，應在「資料完整性與查證紀錄」章節）")
    elif len(redteam_body.strip()) < MIN_SECTION_BODY_CHARS:
        missing.append(
            f"紅隊挑戰清單標題存在，但底下內文過短（{len(redteam_body.strip())} 字，需 ≥{MIN_SECTION_BODY_CHARS} 字），"
            f"疑似空殼佔位（例如「待Agent 3...填入」）、Red Team 步驟實際上未真正執行"
        )
    elif not re.search(r"挑戰\s*1|未發現需列入挑戰的項目", redteam_body):
        missing.append(
            "紅隊挑戰清單有內文但找不到「挑戰1」或「未發現需列入挑戰的項目」——"
            "不符合 reference/red-team-agent.md 規定的輸出格式，可能不是真正跑出來的清單"
        )

    return missing


PROCESS_LANGUAGE_PATTERNS = [
    r"Red Team", r"紅隊複核", r"紅隊挑戰", r"跨模組", r"代理人交鋒",
    r"Evidence Curator", r"Data Researcher", r"Agent\s*[123]", r"模組初判",
    r"複核後(?:更新|補充|調整|最終版本|裁決)", r"經.{0,4}複核.{0,4}指出",
    r"S[1-7][^\s，。、」\n]{0,6}模組",
]


def check_process_language_leakage(text: str):
    """S7 最終定稿的讀者導向章節（評等摘要～主要風險、資料缺口與限制）不應出現生成/複核過程的
    內部用語（Red Team、代理人交鋒、Agent N、S6模組初判…）。這類用語只該出現在「資料完整性與
    查證紀錄」這個專屬章節內——那裡本來就是記錄查證與複核過程的地方，出現不算違規。

    2308 案例（台達電，2026-08）實測發現：即使紅隊複核真的有執行、內容也扎實，S7 仍可能習慣性
    把「經Red Team複核後…」「【Red Team複核後更新】」這類標記直接留在評等摘要、估值分析、投資
    論點、主要風險等正文段落，讀起來像帶審閱註記的工作稿。評分提示詞 v4.1 於「整體品質」構面
    明文對此扣分（並規定不在邏輯連貫性重複計分），且明講「不可用『這代表報告透明』當作理由不扣分」——透明度該用乾淨
    的分析語言呈現（例如「本益成長法之估值權重下修，因其關鍁輸入之EPS來源時效未確認」），不是
    保留「複核後更新」這類流程標籤。
    """
    body_split = text.split("## 資料完整性與查證紀錄")
    if len(body_split) < 2:
        # 這個章節本身缺失是 check_freshness_and_redteam 的檢查範圍，這裡不重複報錯
        reader_facing_text = text
    else:
        before = body_split[1].split("## 資料缺口與限制")
        # 章節內部（含紅隊挑戰清單、時效稽核表）允許出現這些用語；只檢查此章節「之前」
        # 與「之後」（資料缺口與限制、參考資料）的讀者導向內容
        reader_facing_text = body_split[0] + (before[1] if len(before) > 1 else "")

    # 「結論影響追蹤」子節已於 2026-09 自投資論點移入「資料完整性與查證紀錄」章節
    # （見 s7-synthesis.md Step 2.5 變更說明），因此它已落在上方 body_split 的排除範圍內，
    # 不需要、也不應該再有獨立的豁免邏輯。先前版本曾為它開特例放行，那是因為舊模板規定
    # 其措辭必須含「跨模組交叉檢驗」；現已同時改掉模板措辭並移動章節位置，特例取消。

    hits = {}
    for pat in PROCESS_LANGUAGE_PATTERNS:
        matches = re.findall(pat, reader_facing_text)
        if matches:
            hits[pat] = len(matches)
    return hits


def check_word_count(text: str):
    cjk = len(re.findall(r"[一-鿿]", text))
    latin = len(re.findall(r"[A-Za-z0-9]+", text))
    return cjk + latin


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", required=True)
    args = parser.parse_args()

    path = Path(args.report)
    if not path.exists():
        print(f"檔案不存在: {path}")
        sys.exit(1)

    text = read_report(path)
    errors = []
    warnings = []

    missing_sections = check_sections(text)
    if missing_sections:
        errors.append(f"缺少必要章節: {', '.join(missing_sections)}")

    placeholder_hits = check_placeholders(text)
    if placeholder_hits:
        errors.append(f"發現佔位符樣式: {placeholder_hits}")

    missing_biblio, extra_biblio, biblio_err = check_citation_bibliography_match(text)
    if biblio_err:
        errors.append(biblio_err)
    else:
        if missing_biblio:
            errors.append(f"正文引用了但參考資料沒有對應條目: {sorted(missing_biblio)}")
        if extra_biblio:
            warnings.append(f"參考資料有但正文沒引用到的條目（非必然錯誤，但檢查一下）: {sorted(extra_biblio)}")

    no_url = check_bibliography_urls(text)
    if no_url:
        errors.append(f"以下參考資料條目沒有附真實 URL: {no_url}")

    freshness_redteam_missing = check_freshness_and_redteam(text)
    if freshness_redteam_missing:
        errors.append(f"缺少 Agent 2／Agent 3 產出章節: {'; '.join(freshness_redteam_missing)}")

    process_leakage = check_process_language_leakage(text)
    if process_leakage:
        detail = "; ".join(f"{pat}×{n}" for pat, n in process_leakage.items())
        errors.append(
            f"讀者導向正文（非「資料完整性與查證紀錄」章節內）夾雜內部生成/複核過程用語，"
            f"應改寫成乾淨的分析語言並把過程細節移入該專屬章節: {detail}"
        )

    word_count = check_word_count(text)

    print("=" * 60)
    print(f"VALIDATING EQUITY REPORT: {path.name}")
    print("=" * 60)
    print(f"約字數: {word_count}")
    print(f"章節檢查: {'PASS' if not missing_sections else 'FAIL'}")
    print(f"佔位符檢查: {'PASS' if not placeholder_hits else 'FAIL'}")
    print(f"引用/參考資料對應: {'PASS' if not (biblio_err or missing_biblio) else 'FAIL'}")
    print(f"參考資料 URL 完整性: {'PASS' if not no_url else 'FAIL'}")
    print(f"時效稽核表／紅隊挑戰清單: {'PASS' if not freshness_redteam_missing else 'FAIL'}")
    print(f"正文流程用語洩漏檢查: {'PASS' if not process_leakage else 'FAIL'}")

    if word_count > 18000:
        warnings.append("字數超過 18,000，代表 S1~S6 字數預算可能失控（Deep 模式 S7 目標為 8,000-15,000 字），"
                        "請退回檢查各階段 Handoff 是否超出預算；自動續寫機制已於 2026-09 移除，不應出現 CONTINUE 標記")

    print()
    if errors:
        print(f"❌ ERRORS ({len(errors)}):")
        for e in errors:
            print(f"   • {e}")
    if warnings:
        print(f"⚠️  WARNINGS ({len(warnings)}):")
        for w in warnings:
            print(f"   • {w}")

    if not errors:
        print("\n✅ VALIDATION PASSED")
        sys.exit(0)
    else:
        print("\n❌ VALIDATION FAILED - 請修正上述錯誤後再交付")
        sys.exit(1)


if __name__ == "__main__":
    main()
