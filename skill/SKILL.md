---
name: equity-research-tw
user-invocable: true
description: 為台股上市櫃公司產出高品質、數據可驗證的財報分析報告，輸出為 Markdown 文件。採 3-Agent + S1~S7 架構：Data Researcher／Evidence Curator（含時效性掃描）／Red Team Reviewer 三個底層 Agent，加上 S1 市場、S2 競爭、S3 同業、S4 財務、S5 估值、S6 論點風險、S7 綜合報告 七個分析階段。觸發時機：使用者要求台股個股財報分析、投資評等、估值分析、equity research report。
allowed-tools: Read, Write, Edit, Bash, WebFetch, WebSearch, Task, AskUserQuestion, Glob
---

# 台股財報分析 — 3-Agent + S1~S7

## 獨立性原則

本次分析為獨立任務。不得沿用先前對話中的公司假設、數字或結論。每次執行都從 Step 0 重新確認輸入。

## 架構總覽

```
使用者輸入 → 統籌者(你)
                │
                ├─ Agent 1: Data Researcher（見 reference/data-researcher.md）
                │   供 S1~S6 共用的質化檢索 + 台股量化數據交叉驗證
                │
                ├─ S1 Market → S2 Competitive → S3 Peer → S4 Financial → S5 Valuation → S6 Thesis/Risk
                │   （每個 S 各自輸出 reference/handoffs/ 對應的結構化 Handoff，不寫成品段落）
                │
                ├─ Agent 2: Evidence Curator（見 reference/evidence-curator.md）
                │   彙整六份 Handoff、去重、驗證數字與引用、跨模組衝突偵測（Step 1~3）
                │   ＋ 時效性掃描（Step 4）：目標價／共識 EPS／市占率等時效敏感數字逐筆二次
                │   查證是否已有更新版本——靜態一致驗證與時效追新是兩種不同檢查，皆為本
                │   agent 職責，缺一不可，但不需要拆成兩個獨立 agent 身份（詳見該檔案的
                │   設計沿革說明）
                │
                ├─ S7 Synthesis / Report 初稿（見 reference/s7-synthesis.md）
                │   漸進寫檔（每次 ≤5,000 字）
                │
                ├─ Agent 3: Red Team Reviewer（見 reference/red-team-agent.md）
                │   用 Task 工具 spawn 全新 context 審查初稿，找反向論證／矛盾／過度自信主張／
                │   情境測試四類弱點，S7 須逐項回應後才能定稿——這是三個 agent 中唯一必須用
                │   獨立 context 執行的，因為它的價值建立在「不知道生成過程、沒有確認偏誤」
                │   之上，其餘兩個 agent 是分工職責不同，不是需要獨立視角
                │
                └─ S7 品質把關 → 轉存 Markdown
```

**鐵律**：S1～S6 只產出 `reference/handoffs/` 定義的結構化 Handoff（表格、條列、附來源標籤），**不得**在這個階段寫成品散文段落。只有 S7 允許寫完整敘事報告。

---

## Step 0：輸入確認

用 AskUserQuestion 或直接詢問使用者：
- 公司名稱與股票代號（例如：台積電 2330）
- 市場：預設台股（上市/上櫃），如非台股需另行確認資料來源
- 深度模式：Quick／Standard／Deep（決定 S1~S6 字數預算與 S7 目標字數，見下表）
- 輸出語言：預設繁體中文
- 是否需要完整估值模型（DCF），或只需要可比乘數估值

| 模式 | S1+S2+S3 合計 | S4+S5+S6 合計 | S7 目標字數 |
|---|---|---|---|
| Quick | 500-800 字 | 600-900 字 | 2,500-4,000 字 |
| Standard（預設） | 800-1,200 字 | 1,000-1,500 字 | 4,000-8,000 字 |
| Deep | 1,200-1,800 字 | 1,500-2,200 字 | 8,000-15,000 字 |

任何模式都不得因為字數大就省略章節，或用「...(內容過長省略)」「<!-- CONTINUE -->」之類的佔位符中斷交付。

**2026-09 變更**：原「S7 超過 18,000 字觸發自動續寫」機制已移除（8 家樣本實測 0/8 觸發、且唯一一次作動是額度耗盡時被誤用為逃生口，產出殘缺報告，詳見 s7-synthesis.md Step 2）。現行規則為：S7 若寫到接近 18,000 字，代表 S1～S6 字數預算失控，應退回檢查各階段 Handoff 是否超出上表預算。

---

## Step 1：S1～S6 依序執行

依序執行 S1 → S6。每個模組開始前：

1. 讀取 `reference/handoffs/{對應檔名}.md` 取得該階段的欄位結構與 Source Notes 標籤前綴
2. 需要質化資訊（產業新聞、競爭者動態、法說會重點）→ 依 `reference/data-researcher.md` 的質化檢索方法
3. 需要數字（營收、EPS、毛利率、估值乘數等)→ 依 `reference/data-researcher.md` 的台股量化數據交叉驗證流程，**每個關鍵數字都要走過交叉驗證，不可直接用單一來源的網頁摘要當數字**
4. 輸出**只填 Handoff 格式**，控制在該模式的字數預算內
5. 每個 Source Note 都要有唯一 ID（前綴對應模組：MKT/COMP/PEER/FIN/VAL/THESIS + 流水號）

模組與參考人格（若需要方法論深度，可讀取，非必要不讀）：

| S | 主要檢查點 | 可選人格參考（僅在該面向資訊不足時讀取） |
|---|---|---|
| S1 Market | `handoffs/market-handoff.md` | — |
| S2 Competitive | `handoffs/competitive-handoff.md` | `reference/personas/competitive-analyst.md` |
| S3 Peer/Comps | `handoffs/peer-handoff.md` | — |
| S4 Financial | `handoffs/financial-handoff.md` | — |
| S5 Valuation | `handoffs/valuation-handoff.md` | — |
| S6 Thesis/Risk | `handoffs/thesis-handoff.md` | — |

**一次只讀取當下模組需要的那一份 Handoff 定義檔**，用完即進入下一模組，不要一次把 6 份都載入。

---

## Step 2：Agent 2 — Evidence Curator（含時效性掃描）

S1～S6 全部完成後，讀取 `reference/evidence-curator.md` 執行，內部依序跑完 Step 1~5（不可只做前半段就交給 S7）：
1. 彙整六份 Handoff 的 Source Notes 為單一 Evidence Pool
2. 去重、驗證每個數字是否已交叉驗證（未驗證的標記 `[待驗證]`）
3. 跨模組衝突偵測（三種情況，見 evidence-curator.md），若觸發則產出「代理人交鋒」段落
4. **時效性掃描**：從 Evidence Pool 篩出所有「時效敏感數字」（分析師目標價、共識 EPS、市占率排名等），逐筆二次查證是否有更新版本取代，取最新版本作為最終採用值；無法確認是否為最新的數字標記 `[版本時效未完全確認]`，不得靜默流入 S7；輸出時效稽核表
5. 輸出：合併後的 Evidence Pool（時效敏感數字已更新）＋ 衝突裁決清單 ＋ 時效稽核表，交給 S7

**第 4 點不可省略、也不可跳過直接交給 S7**——靜態一致性查核（第 2、3 點）跟時效性掃描（第 4 點）是不同性質的檢查，一致不代表最新，兩者都要做完才算完成本階段。

---

## Step 3：S7 — Synthesis / Report

讀取 `reference/s7-synthesis.md` 執行：
1. 用 `templates/final_report_template.md` 為骨架，逐段 Write/Edit 寫入檔案（每次 ≤5,000 字），寫出**初稿**
2. 不使用續寫接力機制；若字數逼近 18,000 字，退回檢查 S1～S6 的 Handoff 是否超出字數預算

---

## Step 3.5：Agent 3 — Red Team Reviewer

初稿完成後，讀取 `reference/red-team-agent.md` 執行：
1. 用 Task 工具 spawn 全新 agent（不可用同一個 context 自己審自己——這是本階段存在的唯一理由：同一個 context 自我審查有確認偏誤，獨立全新 context 沒有這個包袱），只提供「初稿全文＋Evidence Pool（含時效稽核表）」，不提供生成過程
2. 該 agent 依四類攻擊框架（反向論證／未解釋矛盾／過度自信主張／情境測試）輸出「紅隊挑戰清單」
3. S7 對清單逐項回應：挑戰成立就修改報告，不成立就在報告內加反駁與理由，不可略過任何一項
4. 紅隊挑戰清單（含每項最終處理結果）附入「資料完整性與查證紀錄」章節，公開揭露給讀者

---

## Step 4：S7 品質把關與交付

1. 跑品質檢查清單（s7-synthesis.md Step 3 內，含 Step 2 時效稽核表、Step 3.5 紅隊清單是否已附入報告的檢查項）
2. **輸出格式：Markdown**——完稿並通過品質檢查後即為最終交付檔案，不再轉換成其他格式
3. 檔名：`{公司}_{代號}_equity_research_{YYYYMMDD}.md`，存到使用者當前工作目錄下的 `outputs/` 資料夾（不存在則建立）

---

## 輸出交付

只回傳最終 Markdown 檔案路徑與一段 執行摘要給使用者，除非使用者要求看中間各階段的 Handoff 內容。
