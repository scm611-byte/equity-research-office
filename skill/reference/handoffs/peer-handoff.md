# S3 Peer / Comps Handoff 格式定義

用途：S3 完成後產出，是 S5 估值（可比乘數法）的主要輸入。**只填以下結構，不寫散文段落。**

字數預算：與 S1、S2 合計 800-1,200 字（Standard 模式）。

```text
S3 PEER / COMPS HANDOFF

1. Peer List & Selection Rationale（同業清單與篩選理由）
| 同業 | 代號 | 選入理由 | 與本公司的關鍵差異 |
|---|---|---|---|

2. Comparable Metrics（可比指標，每一格都要標數據來源與交叉驗證狀態）
| 指標 | 本公司 | Peer 1 | Peer 2 | Peer 3 | 來源／驗證狀態 |
|---|---|---|---|---|---|
| 營收成長率 | | | | | |
| 毛利率 | | | | | |
| EV/EBITDA | | | | | |
| P/E | | | | | |
| P/S | | | | | |
| ROE | | | | | |
| FCF Yield | | | | | |

3. Comparability Limits（可比性限制）
- ...

4. Source Notes
- [PEER-1] 來源, 日期, 引用內容。

5. What Next Stage Should Use（S5 應該接手的重點）
- ...
```

## 品質規則
- 「來源／驗證狀態」欄位固定填三選一：`FinMind+finlab 一致` / `FinMind+finlab 不一致，已用 MOPS 仲裁` / `單一來源，未交叉驗證`。第三種狀態禁止用於 S5 估值的關鍵輸入，除非在資料缺口與限制中揭露。
- 同業數量：Quick 模式至少 2 家，Standard/Deep 至少 3-5 家。
- 若某指標任何一家同業缺值，填「N/A」並在 Comparability Limits 說明原因，不得留空白造成表格錯位。
