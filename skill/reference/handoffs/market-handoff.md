# S1 Market Handoff 格式定義

用途：S1 完成後產出，交給 S2 及後續模組參考。**只填以下結構，不寫散文段落。**

字數預算：與 S2、S3 合計 800-1,200 字（Standard 模式，見 SKILL.md 字數表）。

```text
S1 MARKET HANDOFF

1. Sector Snapshot（產業概況）
- 產業別／子產業：
- 產業所處週期階段（成長／成熟／衰退）：

2. Market Size & Growth（市場規模與成長，若有數據）
- 市場規模：[數字] [MKT-x]
- 年成長率：[數字] [MKT-x]

3. Market Drivers（需求驅動因素）
- ...

4. Supply Constraints / Regulatory / Macro（供給限制、法規、總經因素）
- ...

5. Market Risks（市場風險）
- ...

6. Source Notes
- [MKT-1] 來源名稱, 發布/申報日期, 引用的數字或說法。
- [MKT-2] ...
（格式：[ID] Source name, date, claim or metric used — 與 evidence-curator 的 Evidence Pool 對齊）

7. What Next Stage Should Use（S2 應該接手的重點）
- ...
```

## 品質規則
- 每一個數字（市場規模、成長率）都必須有 Source Notes 對應，且該數字必須經過 `reference/data-researcher.md` 的交叉驗證流程（若為質化資訊如產業趨勢，至少 1 個可信來源即可，不需數字交叉驗證）。
- 不確定的項目寫「[不確定]」，不要編造。
- Section 4「Peer Set」不在本階段填——同業比較交給 S3，避免重複。
