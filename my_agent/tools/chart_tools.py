import os
import matplotlib.pyplot as plt
from typing import List, Dict, Any

def generate_chart(chart_type: str, title: str, x_label: str, y_label: str, data: List[Dict[str, Any]], x_key: str, y_key: str, filename: str) -> str:
    """
    當你需要將數據視覺化成圖表時呼叫此工具。
    
    Args:
        chart_type: 圖表類型，請從 "bar" (長條圖), "hbar" (水平長條圖), "line" (折線圖), "pie" (圓餅圖), "doughnut" (甜甜圈圖), "scatter" (散佈圖), "area" (面積圖) 中選擇最適合的一種
        title: 圖表的主標題
        x_label: X軸的標籤名稱
        y_label: Y軸的標籤名稱
        data: 字典列表格式的數據，例如 [{"category": "A", "value": 100}, {"category": "B", "value": 150}]
        x_key: data 中對應到 X軸 的字典鍵名 (例如 "category")
        y_key: data 中對應到 Y軸 的字典鍵名 (例如 "value")
        filename: 輸出的圖片檔名，必須以 .png 結尾 (例如 "sales_chart.png")
    """
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    output_dir = os.path.join(project_root, "output")
    os.makedirs(output_dir, exist_ok=True)
    file_path = os.path.join(output_dir, filename)

    # 設定中文字型，防止圖表中文變成方塊亂碼 (依照系統微調，Windows 通常用 Microsoft JhengHei)
    plt.rcParams['font.sans-serif'] = ['Microsoft JhengHei', 'PingFang TC', 'SimHei', 'Arial']
    plt.rcParams['axes.unicode_minus'] = False

    x_values = [str(item[x_key]) for item in data]
    y_values = [float(item[y_key]) for item in data]

    plt.figure(figsize=(7, 4.5))
    
    # 根據 Agent 傳入的 chart_type 畫出對應的圖表
    if chart_type == "line":
        plt.plot(x_values, y_values, marker='o', color='#4A90E2', linewidth=2, markersize=8)
    elif chart_type == "pie":
        # 圓餅圖不需要設定 x, y 軸標籤
        plt.pie(y_values, labels=x_values, autopct='%1.1f%%', startangle=90, colors=['#4A90E2', '#50E3C2', '#B8E986', '#F5A623', '#F8E71C'])
    elif chart_type == "doughnut":
        # 甜甜圈圖 (設定 wedgeprops 挖空中心)
        plt.pie(y_values, labels=x_values, autopct='%1.1f%%', startangle=90, colors=['#4A90E2', '#50E3C2', '#B8E986', '#F5A623', '#F8E71C'], wedgeprops=dict(width=0.4, edgecolor='w'))
    elif chart_type == "scatter":
        # 散佈圖 (適合看分佈或異常值)
        plt.scatter(x_values, y_values, color='#4A90E2', alpha=0.7, s=100)
    elif chart_type == "area":
        # 面積圖 (適合看累積趨勢)
        # fill_between 對字串 X 軸支援較差，改用數字索引來避免 y_values 陣列運算錯誤
        x_indices = list(range(len(x_values)))
        plt.fill_between(x_indices, y_values, y2=0, color='#4A90E2', alpha=0.4)
        plt.plot(x_indices, y_values, color='#4A90E2', linewidth=2)
        plt.xticks(x_indices, x_values) # 最後再把字串標籤貼回 X 軸
    elif chart_type == "hbar":
        # 水平長條圖 (適合項目名稱很長的數據)
        plt.barh(x_values, y_values, color='#4A90E2')
        plt.gca().invert_yaxis() # 將最高的值排在最上方
    else:
        # 預設為長條圖 (bar)
        plt.bar(x_values, y_values, color='#4A90E2')
        
    plt.title(title, fontsize=14, fontweight='bold')
    
    if chart_type not in ["pie", "doughnut"]:
        plt.xlabel(x_label, fontsize=12)
        plt.ylabel(y_label, fontsize=12)
        
    plt.tight_layout()
    
    plt.savefig(file_path, dpi=150)
    plt.close()
    return file_path # 回傳圖片絕對路徑供後續 PPT 工具使用