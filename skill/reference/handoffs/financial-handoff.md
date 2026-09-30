# S4 Financial Handoff 格式定義

用途：S4 完成後產出，交給 S5（估值）與 S6（論點）。**只填以下結構，不寫散文段落。**

字數預算：與 S5、S6 合計 1,000-1,500 字（Standard 模式）。使用近 3-5 年歷史數據。

```text
S4 FINANCIAL HANDOFF

1. Revenue Trend（營收趨勢，近 3-5 年 + 最近月營收年增率）
| 年度/月份 | 營收 | YoY | 來源／驗證狀態 |
|---|---|---|---|

2. Margin / Profitability（毛利率／營業利益率／淨利率）
| 年度 | 毛利率 | 營業利益率 | 淨利率 | 來源／驗證狀態 |
|---|---|---|---|---|

3. EPS / Net Income Trend
| 年度 | EPS | 淨利 | 來源／驗證狀態 |
|---|---|---|---|

4. Cash Flow & Capex（營運現金流、資本支出、自由現金流）
- ...

5. Balance Sheet Leverage & Liquidity（負債比率、流動比率、速動比率）
- ...

6. Segment Performance（分部績效，若有揭露）
- ...

7. Source Notes
- [FIN-1] 來源, 日期, 引用內容。

8. What Next Stage Should Use（S5／S6 應該接手的重點）
- ...
```

## 品質規則
- 每一列數字都要標「來源／驗證狀態」（同 S3 的三選一）。**財報數字（營收/EPS/毛利率）一律要走交叉驗證，不接受單一來源。**
- 數字若與前次公布數字（例如財報更正）不同，需在該列註明「已更正，原始值 X，更正後 Y」。
- 若某年度數字缺失（如新上市公司），填 N/A 並說明。
