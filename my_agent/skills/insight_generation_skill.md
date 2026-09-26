---
name: insight_generation_skill
description: 深度電商商業洞察與行銷策略分析框架。負責整合量化數據 (BigQuery) 與企業質化知識 (RAG)，執行現象歸因、指標口徑對齊、商業衝擊評估與行動方案推導，並輸出結構化 Storyline 簡報規劃。
version: 1.1.0
tags:
  - analytics
  - ecommerce
  - marketing-strategy
  - pptx-planning
---

# 深度電商商業洞察與策略提煉規範 (Insight Generation Skill)

本技能手冊指導 Agent 作為資深電商策略顧問，將零散的量化數據與質化政策規範轉化為具備商業價值、邏輯嚴密且可落地的深度商業洞察 (Actionable Business Insights)。

---

## 🎯 核心分析目標與 SSOT 原則

1. **拒絕單純複述數據**：不能只回報「A 類別營收增加 20%」，必須深入探討「為什麼會發生（Why）」以及「這對整體商業目標意味著什麼（So What）」。
2. **單一真相來源 (SSOT) 交叉驗證**：嚴格將 BigQuery 撈取的數字與 RAG 檢索出的內部指標定義口徑進行比對，杜絕指標混淆與幻覺。
3. **金字塔結構表達 (Storyline)**：採用結論先行（Executive Summary）架構，層層支撐關鍵洞察與行動建議。

---

## 📥 輸入資料要求 (Prerequisites & Input Data)

在進行商業洞察提煉前，必須確保已具備以下兩大類快取資料：

| 資料類型 | 快取類別與來源 | 檢驗指標 / 欄位 | 遺漏時處理機制 |
| :--- | :--- | :--- | :--- |
| **量化數據** | `category="analytics"`<br>`filename="latest"` | 日期區間、每日營收趨勢、Top N 商品銷量、銷售金額、退貨件數/退貨率 | 若查無資料，提示呼叫 `analytics_agent` 查詢特定期間 |
| **質化規範** | `category="rag"`<br>`filename="latest"` | 指標口徑定義（如商品退貨率 vs 訂單退貨率）、高價值商品門檻、促銷政策 | 若查無資料，提示呼叫 `knowledge_agent` 查詢定義 |

---

## 🧠 四階段深度商業分析框架 (4-Stage Analysis Framework)

### 階段一：現象辨識 (Observation & Anomalies)
- **總體表現評估**：計算週期內整體 GMV、訂單量及客單價（AOV = GMV / 訂單數）波動。
- **異動與集中度分析**：
  - 識別帕雷托現象（Pareto 80/20）：前三大品類或商品佔整體營收之比重。
  - 標註極端值（Outliers）：零退貨商品群、異常高退貨品類、突增/驟減之日期節點。

### 階段二：根因分析與交叉歸因 (Root-Cause Attribution)
對比內部政策手冊與產業背景，從以下維度進行深度歸因：
1. **指標口徑審查**：
   - 審視退貨率計算基準是「件數基準（Returned Units / Total Units）」還是「訂單基準（Returned Orders / Total Orders）」，避免口徑誤導管理決策。
2. **多維交叉下鑽 (Drill-Down)**：
   - **價格帶影響**：高退貨率商品是否集中在特定價格區間（如低單價商品衝動購買後退貨，或高單價商品尺寸不合）？
   - **品類屬性特性**：服飾配件類（Jeans, Outerwear）受尺碼與色差影響通常退貨率天然較高，需對比基準標準而非單看絕對值。
   - **熱銷效應與備貨時間**：觀察是否因促銷檔期結束後產生的遞延退貨效應。

### 階段三：商業意涵與營運衝擊 (Business Implications)
- **財務毛利衝擊**：退貨不僅損失營收，還涉及逆向物流成本（每件退貨約帶來額外運費與整新成本）。
- **顧客體驗與留存風險**：高退貨率品類可能隱含標示不清、尺寸表失真或品管問題，恐侵蝕顧客終身價值 (LTV)。
- **庫存與週轉壓力**：滯銷或高退貨商品是否造成倉儲資金積壓。

### 階段四：落地策略與行動方案 (Actionable Recommendations)
建議必須符合 **SMART 原則**，依優先權分為：
- **短期快贏方案 (Quick Wins, 1~2 週內)**：
  - 例如：調整商品詳情頁（PDP）尺寸標示、補充試穿報告、優化產品實拍色差。
- **中期優化策略 (Optimization, 1~2 個月內)**：
  - 例如：針對零退貨且高評價品類加大廣告投放預算；對高退貨品類設計組合促銷降低退貨風險。
- **長期策略調整 (Strategic Pivot, 1 季以上)**：
  - 例如：調整供應商採購配額、檢討商品退換貨補貼條款。

---

## 📊 商業簡報逐頁架構輸出規範 (Storyline Spec)

當輸出供 PPTX 生成時，必須產出標準的 3~4 頁結構化大綱，格式如下：

```json
{
  "theme": "Ocean Gradient",
  "total_slides": 4,
  "slides": [
    {
      "slide_number": 1,
      "page_type": "TITLE_SLIDE",
      "title": "精確主標題（例如：2022年7月核心品類營收與退貨率複盤洞察）",
      "subtitle": "副標題（例如：基於 Top 20 商品績效與內部口徑規範之策略分析）",
      "meta_info": "分析週期：2022-07-01 ~ 2022-07-05 ｜ 製作：SSOT Data Copilot"
    },
    {
      "slide_number": 2,
      "page_type": "DASHBOARD_CARDS",
      "title": "營運總體概況與關鍵指標表現",
      "cards": [
        {"metric_name": "總銷售營收", "value": "$XX,XXX", "trend": "優於基準/持平"},
        {"metric_name": "總訂單件數", "value": "XX 件", "trend": "Top 20 集中度 XX%"},
        {"metric_name": "平均商品退貨率", "value": "X.X%", "trend": "符合內部規範"}
      ],
      "key_takeaway": "核心結論（1~2 句話總結現況特徵）"
    },
    {
      "slide_number": 3,
      "page_type": "CHART_AND_INSIGHT",
      "title": "品類結構分佈與深層歸因分析",
      "chart_spec": {
        "required": true,
        "chart_type": "bar",
        "description": "品類銷售金額 vs 退貨率分佈圖",
        "data_focus": ["category", "revenue", "return_rate"]
      },
      "deep_insights": [
        {"title": "集中度觀察", "detail": "前三大品類佔總營收 XX%，動能主要來自..."},
        {"title": "現象歸因", "detail": "依據指標手冊定義，此退貨率表現良好主要因..."},
        {"title": "潛在風險", "detail": "特定品類庫存備貨比過高，需留意..."}
      ]
    },
    {
      "slide_number": 4,
      "page_type": "ACTION_PLAN",
      "title": "後續策略行動與優化落地建議",
      "actions": [
        {"phase": "短期 (Quick Win)", "action": "聚焦高轉化商品，調整數位廣告預算配置"},
        {"phase": "中期 (Optimization)", "action": "強化服飾類商品尺碼指引，維持低退貨率優勢"},
        {"phase": "長期 (Strategy)", "action": "建立高回購品類之忠誠度激勵計畫"}
      ]
    }
  ]
}
