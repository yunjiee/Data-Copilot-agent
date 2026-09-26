"""my_agent/tools/cache_tools.py
管理 analytics、rag、reports 的本地快取儲存與讀取工具
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any
from ..config import config

VALID_CATEGORIES = ("analytics", "rag", "reports")


def _get_category_dir(category: str) -> Path:
    cat = category.strip().lower()
    if cat not in VALID_CATEGORIES:
        raise ValueError(
            f"不合法的快取分類 '{category}'，必須為 {VALID_CATEGORIES} 之一"
        )
    target_dir = Path(config.mas_project_root) / "cache" / cat
    target_dir.mkdir(parents=True, exist_ok=True)
    return target_dir


def save_cache_data(category: str, filename: str, data: Any) -> str:
    """將中途產出的查詢數據、RAG 檢索內容或報告整合資料保存至本地快取目錄。

    Args:
        category: 快取類別，可填入 'analytics' (量化數據), 'rag' (知識庫名詞規範), 或 'reports' (報告快照)。
        filename: 檔案名稱，例如 'bq_q1_sales.json' 或 'rag_metric_defs.json'。
        data: 欲快取的資料結構（dict, list 或 json 格式字串）。

    Returns:
        儲存成功之檔案絕對路徑字串。
    """
    target_dir = _get_category_dir(category)
    if not filename.endswith(".json"):
        filename = f"{filename}.json"

    target_path = target_dir / filename

    payload = {
        "saved_at": datetime.now().isoformat(),
        "category": category,
        "filename": filename,
        "data": data,
    }

    with open(target_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    return str(target_path.resolve())


def load_cache_data(category: str, filename: str = "latest") -> str:
    """讀取指定分類下的本地快取檔案內容。

    Args:
        category: 快取類別 ('analytics', 'rag', 'reports')。
        filename: 檔案名稱，若傳入 'latest' 則自動載入該分類下最新修改的檔案。

    Returns:
        快取內容的 JSON 字串，若無資料則回傳提示訊息。
    """
    target_dir = _get_category_dir(category)

    if filename == "latest":
        files = sorted(
            target_dir.glob("*.json"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        if not files:
            return f"[{category}] 目錄下查無任何快取檔案。"
        target_path = files[0]
    else:
        if not filename.endswith(".json"):
            filename = f"{filename}.json"
        target_path = target_dir / filename
        if not target_path.exists():
            return f"查無快取檔案: {target_path}"

    with open(target_path, "r", encoding="utf-8") as f:
        return f.read()


def list_cache_files() -> str:
    """列出 mas_output/cache/ 下所有已保存的快取檔案清單 (包含 analytics, rag, reports)。"""
    cache_root = Path(config.mas_project_root) / "cache"
    result = ["### 📁 本地快取檔案清單"]
    for cat in VALID_CATEGORIES:
        cat_dir = cache_root / cat
        files = sorted(cat_dir.glob("*.json")) if cat_dir.exists() else []
        result.append(f"\n#### 📂 {cat}/ ({len(files)} 個檔案):")
        for file in files:
            mtime = datetime.fromtimestamp(file.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")
            size_kb = round(file.stat().st_size / 1024, 2)
            result.append(f"- `{file.name}` ({size_kb} KB, 修改時間: {mtime})")
    return "\n".join(result)