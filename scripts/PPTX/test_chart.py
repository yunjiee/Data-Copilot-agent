from pathlib import Path
import sys

# 確保能引用到 my_agent 套件
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from my_agent.tools.chart_tools import render_vegalite_chart


def test_chart_generation():
    print("🚀 開始測試 Vega-Lite 圖表渲染...")

    sample_spec = {
        "width": 650,
        "height": 360,
        "data": {
            "values": [
                {"類別": "男裝 (Men)", "營收": 125000},
                {"類別": "女裝 (Women)", "營收": 185000},
                {"類別": "配件 (Accessories)", "營收": 64000},
                {"類別": "鞋類 (Footwear)", "營收": 98000},
            ]
        },
        "mark": {"type": "bar", "cornerRadiusEnd": 4},
        "encoding": {
            "x": {
                "field": "類別",
                "type": "nominal",
                "axis": {
                    "labelAngle": 0,
                    "titlePadding": 14,
                    "labelPadding": 10
                }
            },
            "y": {
                "field": "營收",
                "type": "quantitative",
                "title": "營收 (NTD)"
            },
            "color": {"value": "#1E2761"},  # 採用 SKILL.md 中的 Midnight Executive 主色
        },
    }

    result_path = render_vegalite_chart(spec=sample_spec, filename="test_sales_chart.png")
    print(f"回傳結果：{result_path}")

    if Path(result_path).exists():
        print(f"✅ 測試成功！圖檔已正確生成於：{result_path}")
    else:
        print(f"❌ 測試失敗：檔案未生成，錯誤訊息：{result_path}")

if __name__ == "__main__":
    test_chart_generation()