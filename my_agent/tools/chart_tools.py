from pathlib import Path
from typing import Any, Dict
import vl_convert as vlc

# 動態取得專案根目錄 (my-adk-project)
PROJECT_ROOT = Path(__file__).resolve().parents[2]
OUTPUT_DIR = PROJECT_ROOT / "mas_output" / "workspace"


def render_vegalite_chart(spec: Dict[str, Any], filename: str) -> str:
    """
    使用 Vega-Lite 宣告式規格渲染高品質視覺化圖表，並輸出為高解析度 PNG 圖檔。

    Args:
        spec: Vega-Lite v5 規格字典 (JSON Object)，必須包含 data (例如 values 陣列)、
              mark (例如 "bar", "line", "arc", "area", "point")、
              以及 encoding (x, y, color 等欄位映射與 title 標題)。
        filename: 輸出的圖片檔名，必須以 .png 結尾 (例如 "sales_trend.png")。

    Returns:
        生成的圖片絕對路徑，可直接供後續簡報腳本 (pptxgenjs) 的 slide.addImage() 引用。
    """
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    if not filename.endswith(".png"):
        filename = f"{filename}.png"

    output_path = OUTPUT_DIR / filename

    # 自動補齊 Vega-Lite Schema
    if "$schema" not in spec:
        spec["$schema"] = "https://vega.github.io/schema/vega-lite/v5.json"

    # 提供預設寬高與版面配置，避免未指定尺寸時文字緊擠重疊
    spec.setdefault("width", 650)
    spec.setdefault("height", 360)

    # 自動設定全域字體與間距配置 (Padding)
    config = spec.setdefault("config", {})
    config.setdefault("font", "Microsoft JhengHei")
    
    axis_config = config.setdefault("axis", {})
    axis_config.setdefault("titlePadding", 14)
    axis_config.setdefault("labelPadding", 8)
    axis_config.setdefault("labelFontSize", 12)
    axis_config.setdefault("titleFontSize", 13)

    try:
        # 使用 Rust 核心將 Vega-Lite JSON 編譯為 2x 高解析度 PNG 二進位
        png_bytes = vlc.vegalite_to_png(vl_spec=spec, scale=2.0)
        output_path.write_bytes(png_bytes)
        return str(output_path.resolve())
    except Exception as e:
        return (
            f"❌ Vega-Lite 圖表渲染失敗：{str(e)}。"
            "請檢查 spec 格式是否符合 Vega-Lite v5 規範、欄位名稱是否吻合。"
        )