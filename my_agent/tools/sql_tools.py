from google.cloud import bigquery
from my_agent.config import config

def check_sql_syntax(query: str) -> str:
    """
    在正式執行 SQL 之前，用來檢查語法是否正確，並預估查詢成本 (Dry Run)。
    如果語法錯誤，會回報錯誤原因。
    """
    client = bigquery.Client()
    
    # 設定 dry_run 為 True
    job_config = bigquery.QueryJobConfig(dry_run=True, use_query_cache=False)
    
    try:
        query_job = client.query(query, job_config=job_config)
        bytes_processed = query_job.total_bytes_processed or 0
        mb_processed = bytes_processed / (1024 * 1024)
        
        # 防護機制：讀取 config 設定的掃描量上限
        if mb_processed > config.max_query_size_mb:
            return f"⚠️ 警告：語法正確，但預估將掃描 {mb_processed:.2f} MB 的資料，超過 {config.max_query_size_mb} MB 限制。請加入適當的 WHERE 條件 (如日期範圍) 或 LIMIT 來減少掃描量。"
            
        return f"✅ 語法檢查通過！預估將掃描 {mb_processed:.2f} MB 的資料。"
    except Exception as e:
        return f"❌ 語法錯誤：\n{str(e)}\n請參考您的 SQL 專家技能進行修正。"