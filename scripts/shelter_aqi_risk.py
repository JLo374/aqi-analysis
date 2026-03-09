"""
避難所與 AQI 測站風險分析
1. 抓取 AQI 測站資料（含情境模擬）
2. 計算每個避難所到最近 AQI 測站的距離
3. 新增風險標籤
4. 輸出 CSV 分析結果
5. 繪製 Folium 地圖
"""

import os
import sys
import subprocess
from pathlib import Path
from datetime import datetime
from math import radians, cos, sin, asin, sqrt

def install_requirements():
    """自動安裝所需套件"""
    requirements_file = Path(__file__).parent.parent / 'requirements.txt'
    
    if requirements_file.exists():
        print("正在檢查並安裝所需套件...")
        try:
            subprocess.check_call([
                sys.executable, '-m', 'pip', 'install', '-r', str(requirements_file), '--quiet'
            ])
            print("✓ 套件安裝完成\n")
        except subprocess.CalledProcessError as e:
            print(f"⚠ 套件安裝時發生錯誤: {e}")
            sys.exit(1)

# 自動安裝套件
install_requirements()

# 導入所需模組
import requests
from dotenv import load_dotenv
import folium
from folium import plugins
import pandas as pd
import numpy as np

# 載入環境變數
env_path = Path(__file__).parent.parent / '.env'
load_dotenv(env_path)

# API 設定
MOENV_API_KEY = os.getenv('MOENV_API_KEY')
API_BASE_URL = 'https://data.moenv.gov.tw/api/v2'
DATASET_ID = 'aqx_p_432'

# 情境模擬設定
SIMULATE_HIGH_AQI = True  # 是否啟用情境模擬
SIMULATION_THRESHOLD = 100  # 如果所有 AQI 都小於此值，則啟動模擬
SIMULATION_CITY = '高雄'   # 模擬高 AQI 的城市
SIMULATION_AQI = 150      # 模擬的 AQI 值

def haversine_distance(lat1, lon1, lat2, lon2):
    """
    使用 Haversine 公式計算兩點間的距離（公里）
    
    Parameters:
        lat1, lon1: 第一個點的緯度和經度
        lat2, lon2: 第二個點的緯度和經度
        
    Returns:
        float: 兩點間的距離（公里）
    """
    # 將十進位度數轉換為弧度
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    
    # Haversine 公式
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * asin(sqrt(a))
    
    # 地球半徑（公里）
    r = 6371
    
    return round(c * r, 2)

def fetch_aqi_data():
    """
    從 MOENV API 獲取 AQI 資料
    
    Returns:
        pd.DataFrame: AQI 資料
    """
    if not MOENV_API_KEY:
        raise ValueError("❌ 找不到 MOENV_API_KEY，請確認 .env 檔案中已設定 API Key")
    
    url = f"{API_BASE_URL}/{DATASET_ID}"
    params = {
        'api_key': MOENV_API_KEY,
        'limit': 1000,
        'format': 'json'
    }
    
    print("正在從 MOENV API 獲取 AQI 資料...")
    
    try:
        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()
        
        # 處理 API 回應
        if isinstance(data, list):
            records = data
        elif isinstance(data, dict) and 'records' in data:
            records = data['records']
        else:
            raise ValueError("API 回應格式不正確")
        
        df = pd.DataFrame(records)
        
        # 轉換數值型欄位
        numeric_columns = ['latitude', 'longitude', 'aqi']
        for col in numeric_columns:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
        
        # 移除無效的經緯度資料
        df = df.dropna(subset=['latitude', 'longitude'])
        df = df[(df['latitude'] != 0) & (df['longitude'] != 0)]
        
        print(f"✓ 成功獲取 {len(df)} 筆 AQI 測站資料\n")
        
        return df
    
    except requests.exceptions.RequestException as e:
        print(f"❌ API 請求失敗: {e}")
        sys.exit(1)

def simulate_high_aqi(df_aqi):
    """
    情境模擬：如果所有 AQI < 設定閾值，將指定城市的測站設為高 AQI

    Parameters:
        df_aqi: AQI 資料 DataFrame

    Returns:
        pd.DataFrame: 處理後的 AQI 資料
    """
    df = df_aqi.copy()

    # 檢查是否有 AQI >= 閾值的測站
    max_aqi = df['aqi'].max()

    print("AQI 情境檢查：")
    print(f"  目前最高 AQI: {max_aqi:.0f}")
    print(f"  模擬閾值: {SIMULATION_THRESHOLD}")

    if max_aqi < SIMULATION_THRESHOLD and SIMULATE_HIGH_AQI:
        print(f"  ⚠ 所有測站 AQI < {SIMULATION_THRESHOLD}，啟動情境模擬")
        print(f"  → 將「{SIMULATION_CITY}」相關測站 AQI 設為 {SIMULATION_AQI}\n")

        # 找到包含指定城市的測站
        city_mask = df['county'].str.contains(SIMULATION_CITY, na=False)

        if city_mask.sum() > 0:
            # 隨機選擇一個該城市的測站
            city_stations = df[city_mask]
            selected_idx = city_stations.sample(1).index[0]

            original_aqi = df.loc[selected_idx, 'aqi']
            df.loc[selected_idx, 'aqi'] = SIMULATION_AQI

            print(f"  ✓ 測站「{df.loc[selected_idx, 'sitename']}」")
            print(f"    AQI: {original_aqi:.0f} → {SIMULATION_AQI}")
            print(f"    位置: {df.loc[selected_idx, 'county']}")
            print(f"    座標: ({df.loc[selected_idx, 'latitude']:.4f}, {df.loc[selected_idx, 'longitude']:.4f})\n")
        else:
            print(f"  ⚠ 找不到「{SIMULATION_CITY}」相關測站，無法模擬\n")
    else:
        print(f"  ✓ 已有 AQI >= {SIMULATION_THRESHOLD} 的測站，無需模擬\n")

    return df

def load_shelter_data():
    """
    載入避難所分析資料
    
    Returns:
        pd.DataFrame: 避難所資料
    """
    project_root = Path(__file__).parent.parent
    output_dir = project_root / 'outputs'
    
    # 尋找最新的避難所分析檔案
    shelter_files = sorted(output_dir.glob('shelters_analyzed_*.csv'), reverse=True)
    
    if not shelter_files:
        print("❌ 找不到避難所分析檔案，請先執行 analyze_shelters.py")
        sys.exit(1)
    
    shelter_file = shelter_files[0]
    print(f"載入避難所資料: {shelter_file.name}")
    
    df = pd.read_csv(shelter_file, encoding='utf-8-sig')
    print(f"✓ 成功載入 {len(df)} 筆避難所資料\n")
    
    return df

def find_nearest_aqi_station(shelter_row, df_aqi):
    """
    找到距離避難所最近的 AQI 測站
    
    Parameters:
        shelter_row: 避難所資料列
        df_aqi: AQI 測站資料
        
    Returns:
        dict: 最近測站的資訊
    """
    shelter_lat = shelter_row['lat_wgs84']
    shelter_lon = shelter_row['lon_wgs84']
    
    if pd.isna(shelter_lat) or pd.isna(shelter_lon):
        return {
            'nearest_station_name': None,
            'nearest_station_distance': None,
            'nearest_station_aqi': None,
            'nearest_station_lat': None,
            'nearest_station_lon': None
        }
    
    # 計算到所有測站的距離
    distances = df_aqi.apply(
        lambda row: haversine_distance(
            shelter_lat, shelter_lon,
            row['latitude'], row['longitude']
        ),
        axis=1
    )
    
    # 找到最近的測站
    nearest_idx = distances.idxmin()
    nearest_distance = distances.min()
    
    nearest_station = df_aqi.loc[nearest_idx]
    
    return {
        'nearest_station_name': nearest_station['sitename'],
        'nearest_station_distance': nearest_distance,
        'nearest_station_aqi': nearest_station['aqi'],
        'nearest_station_lat': nearest_station['latitude'],
        'nearest_station_lon': nearest_station['longitude']
    }

def calculate_shelter_aqi_analysis(df_shelters, df_aqi):
    """
    計算每個避難所到最近 AQI 測站的距離並分析風險
    
    Parameters:
        df_shelters: 避難所資料
        df_aqi: AQI 測站資料
        
    Returns:
        pd.DataFrame: 包含風險分析的避難所資料
    """
    print("正在計算每個避難所到最近 AQI 測站的距離...")
    
    # 計算最近測站資訊
    nearest_info = df_shelters.apply(
        lambda row: find_nearest_aqi_station(row, df_aqi),
        axis=1
    )
    
    # 將結果轉換為 DataFrame 並合併
    nearest_df = pd.DataFrame(nearest_info.tolist())
    df_result = pd.concat([df_shelters, nearest_df], axis=1)
    
    print(f"✓ 距離計算完成\n")
    
    # 新增風險標籤
    print("正在評估風險等級...")
    
    def assess_risk(row):
        """評估風險等級"""
        aqi = row['nearest_station_aqi']
        is_indoor = row['is_indoor']
        
        if pd.isna(aqi):
            return 'Unknown'
        
        # High Risk: 最近 AQI > 100
        if aqi > 100:
            return 'High Risk'
        
        # Warning: 最近 AQI > 50 且為室外
        if aqi > 50 and is_indoor == False:
            return 'Warning'
        
        # Safe: 其他情況
        return 'Safe'
    
    df_result['risk_level'] = df_result.apply(assess_risk, axis=1)
    
    # 統計風險等級
    risk_counts = df_result['risk_level'].value_counts()
    print(f"\n風險等級統計：")
    for level, count in risk_counts.items():
        percentage = count / len(df_result) * 100
        print(f"  {level}: {count} 處 ({percentage:.1f}%)")
    
    print()
    
    return df_result

def get_aqi_color(aqi):
    """根據 AQI 值返回對應的顏色"""
    if pd.isna(aqi):
        return 'gray'
    
    aqi = float(aqi)
    
    if aqi <= 50:
        return 'green'
    elif aqi <= 100:
        return 'yellow'
    elif aqi <= 150:
        return 'orange'
    elif aqi <= 200:
        return 'red'
    else:
        return 'darkred'

def get_aqi_label(aqi):
    """根據 AQI 值返回標籤"""
    if pd.isna(aqi):
        return '無資料'
    
    aqi = float(aqi)
    
    if aqi <= 50:
        return '良好'
    elif aqi <= 100:
        return '普通'
    elif aqi <= 150:
        return '對敏感族群不健康'
    elif aqi <= 200:
        return '對所有族群不健康'
    else:
        return '非常不健康'

def get_risk_color(risk_level):
    """根據風險等級返回顏色"""
    colors = {
        'High Risk': 'red',
        'Warning': 'orange',
        'Safe': 'green',
        'Unknown': 'gray'
    }
    return colors.get(risk_level, 'gray')

def create_integrated_map(df_shelters, df_aqi, output_path):
    """
    建立整合 AQI 測站和避難所的地圖
    
    Parameters:
        df_shelters: 避難所資料（含風險分析）
        df_aqi: AQI 測站資料
        output_path: 輸出檔案路徑
    """
    print("正在繪製整合地圖...")
    
    # 計算地圖中心（台灣中心）
    taiwan_center = [23.5, 121.0]
    
    # 建立地圖
    m = folium.Map(
        location=taiwan_center,
        zoom_start=7,
        tiles='OpenStreetMap'
    )
    
    # 建立圖層群組
    aqi_layer = folium.FeatureGroup(name='AQI 測站', show=True)
    shelter_indoor_layer = folium.FeatureGroup(name='室內避難所', show=True)
    shelter_outdoor_layer = folium.FeatureGroup(name='室外避難所', show=True)
    
    # 1. 加入 AQI 測站標記
    for idx, row in df_aqi.iterrows():
        lat = row['latitude']
        lon = row['longitude']
        sitename = row.get('sitename', '未知測站')
        county = row.get('county', '')
        aqi = row.get('aqi', 'N/A')
        
        # 彈出視窗內容
        popup_html = f"""
        <div style="font-family: 'Microsoft JhengHei', Arial, sans-serif; width: 220px;">
            <h4 style="margin: 0 0 10px 0; color: #2c3e50;">🔬 {sitename}</h4>
            <table style="width: 100%; font-size: 13px;">
                <tr><td><b>縣市：</b></td><td>{county}</td></tr>
                <tr><td><b>AQI：</b></td>
                    <td style="color: {get_aqi_color(aqi)}; font-weight: bold; font-size: 16px;">{aqi}</td></tr>
                <tr><td><b>狀態：</b></td>
                    <td style="color: {get_aqi_color(aqi)}; font-weight: bold;">{get_aqi_label(aqi)}</td></tr>
            </table>
        </div>
        """
        
        # 加入測站標記（使用星形圖標）
        folium.Marker(
            location=[lat, lon],
            popup=folium.Popup(popup_html, max_width=250),
            tooltip=f"測站: {sitename} (AQI: {aqi})",
            icon=folium.Icon(
                color=get_aqi_color(aqi),
                icon='info-sign',
                prefix='glyphicon'
            )
        ).add_to(aqi_layer)
    
    # 2. 加入避難所標記
    for idx, row in df_shelters.iterrows():
        lat = row.get('lat_wgs84')
        lon = row.get('lon_wgs84')
        
        if pd.isna(lat) or pd.isna(lon):
            continue
        
        shelter_name = row.get('避難收容處所名稱', '未知避難所')
        county = row.get('縣市及鄉鎮市區', '')
        address = row.get('避難收容處所地址', '')
        is_indoor = row.get('is_indoor')
        risk_level = row.get('risk_level', 'Unknown')
        nearest_station = row.get('nearest_station_name', 'N/A')
        nearest_distance = row.get('nearest_station_distance', 'N/A')
        nearest_aqi = row.get('nearest_station_aqi', 'N/A')
        
        # 彈出視窗內容
        indoor_icon = '🏠' if is_indoor else '🌳'
        popup_html = f"""
        <div style="font-family: 'Microsoft JhengHei', Arial, sans-serif; width: 250px;">
            <h4 style="margin: 0 0 10px 0; color: #2c3e50;">{indoor_icon} {shelter_name}</h4>
            <table style="width: 100%; font-size: 12px;">
                <tr><td><b>縣市：</b></td><td>{county}</td></tr>
                <tr><td><b>地址：</b></td><td>{address}</td></tr>
                <tr><td><b>類型：</b></td><td>{'室內' if is_indoor else '室外'}</td></tr>
                <tr style="border-top: 1px solid #ddd;">
                    <td colspan="2" style="padding-top: 8px;"><b>風險評估</b></td>
                </tr>
                <tr><td><b>風險等級：</b></td>
                    <td style="color: {get_risk_color(risk_level)}; font-weight: bold;">{risk_level}</td></tr>
                <tr><td><b>最近測站：</b></td><td>{nearest_station}</td></tr>
                <tr><td><b>距離：</b></td><td>{nearest_distance:.2f} km</td></tr>
                <tr><td><b>該站 AQI：</b></td>
                    <td style="color: {get_aqi_color(nearest_aqi)}; font-weight: bold;">{nearest_aqi}</td></tr>
            </table>
        </div>
        """
        
        # 根據室內/室外選擇圖層和圖標
        if is_indoor:
            icon_name = 'home'
            layer = shelter_indoor_layer
        else:
            icon_name = 'tree-conifer'
            layer = shelter_outdoor_layer
        
        # 加入避難所標記
        folium.CircleMarker(
            location=[lat, lon],
            radius=6,
            popup=folium.Popup(popup_html, max_width=280),
            tooltip=f"{shelter_name} ({risk_level})",
            color='white',
            fill=True,
            fillColor=get_risk_color(risk_level),
            fillOpacity=0.7,
            weight=2
        ).add_to(layer)
    
    # 加入圖層到地圖
    aqi_layer.add_to(m)
    shelter_indoor_layer.add_to(m)
    shelter_outdoor_layer.add_to(m)
    
    # 加入圖層控制
    folium.LayerControl(position='topright', collapsed=False).add_to(m)
    
    # 加入圖例
    legend_html = '''
    <div style="position: fixed; 
                bottom: 50px; left: 50px; width: 280px; height: auto; 
                background-color: white; border: 2px solid #666; z-index: 9999; 
                font-size: 13px; padding: 15px; border-radius: 8px; 
                box-shadow: 0 2px 8px rgba(0,0,0,0.2);
                font-family: 'Microsoft JhengHei', Arial, sans-serif;">
        <p style="margin: 0 0 10px 0; font-weight: bold; font-size: 15px; color: #2c3e50;">
            圖例說明
        </p>
        <div style="margin-bottom: 10px;">
            <p style="margin: 5px 0; font-weight: bold; color: #555;">AQI 測站（標記圖示）</p>
            <div style="margin: 3px 0; display: flex; align-items: center;">
                <div style="width: 15px; height: 15px; background-color: green; 
                            margin-right: 8px; border: 1px solid #333;"></div>
                <span>0-50: 良好</span>
            </div>
            <div style="margin: 3px 0; display: flex; align-items: center;">
                <div style="width: 15px; height: 15px; background-color: yellow; 
                            margin-right: 8px; border: 1px solid #333;"></div>
                <span>51-100: 普通</span>
            </div>
            <div style="margin: 3px 0; display: flex; align-items: center;">
                <div style="width: 15px; height: 15px; background-color: orange; 
                            margin-right: 8px; border: 1px solid #333;"></div>
                <span>101-150: 對敏感族群不健康</span>
            </div>
            <div style="margin: 3px 0; display: flex; align-items: center;">
                <div style="width: 15px; height: 15px; background-color: red; 
                            margin-right: 8px; border: 1px solid #333;"></div>
                <span>151+: 不健康</span>
            </div>
        </div>
        <div>
            <p style="margin: 5px 0; font-weight: bold; color: #555;">避難所風險（圓形標記）</p>
            <div style="margin: 3px 0; display: flex; align-items: center;">
                <div style="width: 15px; height: 15px; background-color: green; 
                            border-radius: 50%; margin-right: 8px; border: 1px solid #333;"></div>
                <span>Safe: 安全</span>
            </div>
            <div style="margin: 3px 0; display: flex; align-items: center;">
                <div style="width: 15px; height: 15px; background-color: orange; 
                            border-radius: 50%; margin-right: 8px; border: 1px solid #333;"></div>
                <span>Warning: 警告（室外 + AQI>50）</span>
            </div>
            <div style="margin: 3px 0; display: flex; align-items: center;">
                <div style="width: 15px; height: 15px; background-color: red; 
                            border-radius: 50%; margin-right: 8px; border: 1px solid #333;"></div>
                <span>High Risk: 高風險（AQI>100）</span>
            </div>
        </div>
    </div>
    '''
    m.get_root().html.add_child(folium.Element(legend_html))
    
    # 儲存地圖
    m.save(output_path)
    print(f"✓ 地圖已儲存至: {output_path}\n")

def main():
    """主程式"""
    print("=" * 70)
    print("避難所與 AQI 測站風險分析")
    print("=" * 70)
    print()
    
    # 設定輸出目錄
    project_root = Path(__file__).parent.parent
    output_dir = project_root / 'outputs'
    output_dir.mkdir(exist_ok=True)
    
    # 1. 獲取 AQI 資料
    df_aqi = fetch_aqi_data()
    
    # 2. 情境模擬（如果需要）
    df_aqi = simulate_high_aqi(df_aqi)
    
    # 3. 載入避難所資料
    df_shelters = load_shelter_data()
    
    # 4. 計算避難所到最近 AQI 測站的距離並評估風險
    df_analysis = calculate_shelter_aqi_analysis(df_shelters, df_aqi)
    
    # 5. 儲存分析結果
    output_csv = output_dir / 'shelter_aqi_analysis.csv'
    df_analysis.to_csv(output_csv, index=False, encoding='utf-8-sig')
    print(f"✓ 分析結果已儲存至: {output_csv}")
    
    # 6. 繪製整合地圖
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    map_path = output_dir / f'shelter_aqi_map_{timestamp}.html'
    create_integrated_map(df_analysis, df_aqi, str(map_path))
    
    # 7. 統計摘要
    print("=" * 70)
    print("分析摘要")
    print("=" * 70)
    print(f"AQI 測站數量: {len(df_aqi)}")
    print(f"避難所數量: {len(df_analysis)}")
    print(f"\nAQI 範圍: {df_aqi['aqi'].min():.0f} ~ {df_aqi['aqi'].max():.0f}")
    print(f"平均 AQI: {df_aqi['aqi'].mean():.1f}")
    
    print(f"\n避難所到最近測站距離統計:")
    print(f"  最近: {df_analysis['nearest_station_distance'].min():.2f} km")
    print(f"  最遠: {df_analysis['nearest_station_distance'].max():.2f} km")
    print(f"  平均: {df_analysis['nearest_station_distance'].mean():.2f} km")
    
    print("\n" + "=" * 70)
    print("✓ 所有分析完成！")
    print(f"請開啟 {map_path} 查看互動式地圖")
    print("=" * 70)

if __name__ == "__main__":
    main()
