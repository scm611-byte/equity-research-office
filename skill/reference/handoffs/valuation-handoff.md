# S5 Valuation Handoff 格式定義

用途：S5 完成後產出，交給 S6（論點）與 S7（最終報告的估值章節）。**只填以下結構，不寫散文段落。**

字數預算：與 S4、S6 合計 1,000-1,500 字（Standard 模式）。

```text
S5 VALUATION HANDOFF

1. Current Valuation Snapshot（目前估值快照）
- 現價：
- 目前 P/E ／ P/B ／ EV/EBITDA：[VAL-x]

2. Comparable Multiple Valuation（可比乘數估值，引用 S3 Peer Handoff 數據）
| 乘數 | 本公司現值 | 同業中位數 | 隱含價值 |
|---|---|---|---|

3. DCF / 簡化內在價值（僅在假設可明確列出時才做，否則寫「本次不做 DCF，理由：X」）
- WACC 假設：
- 營收成長假設（近期／長期）：
- 終值成長率假設：
- 隱含每股價值：

4. Bull / Base / Bear Cases
| 情境 | 關鍵假設 | 隱含價值 |
|---|---|---|
| Bear | | |
| Base | | |
| Bull | | |

5. Target Price / Valuation Range
- 目標價區間：

6. Source Notes
- [VAL-1] 來源, 日期, 引用內容。

7. What Next Stage Should Use（S6／S7 應該接手的重點）
- ...
```

## 品質規則
- **所有假設必須明列**（WACC、成長率、終值成長率），不得只給結論數字不給假設——這是 anti-hallucination 的核心要求。
- Comparable Multiple Valuation 的「同業中位數」必須直接來自 S3 Peer Handoff 的表格，不得重新估計或引用其他來源，避免同一個數字在不同模組出現兩個版本。
- 若 S3 交叉驗證狀態標記「單一來源，未交叉驗證」的同業數據，本階段使用時要在 Source Notes 加註警語。
