"""
避難收容所資料分析腳本
1. 檢查座標系統 (EPSG:3826 或 EPSG:4326)
2. 排除異常點位 (0,0 或台灣邊界外)
3. 語意分析新增 is_indoor 欄位
"""

import os
import sys
import re
from pathlib import Path
from datetime import datetime

import pandas as pd
import numpy as np
from pyproj import Transformer, CRS
from shapely.geometry import Point, Polygon

# 台灣邊界 (EPSG:4326 經緯度)
TAIWAN_BBOX = {
    'lon_min': 119.0,
    'lon_max': 122.5,
    'lat_min': 21.5,
    'lat_max': 26.0
}

# 室內設施關鍵字
INDOOR_KEYWORDS = [
    '學校', '小學', '中學', '國中', '國小', '高中', '大學',
    '活動中心', '社區活動中心', '集會所', '社區發展協會',
    '教室', '禮堂', '體育館', '館', '會館',
    '辦公處', '村辦公處', '里辦公處', '公所',
    '室', '教會', '寺廟', '宮',
    '圖書館', '文化中心', '福利中心'
]

# 室外設施關鍵字
OUTDOOR_KEYWORDS = [
    '公園', '廣場', '操場', '運動場', '球場',
    '綠地', '空地', '停車場'
]

def detect_coordinate_system(df, lon_col='經度', lat_col='緯度'):
    """
    檢測座標系統
    
    Parameters:
        df: DataFrame
        lon_col: 經度欄位名稱
        lat_col: 緯度欄位名稱
        
    Returns:
        str: 'EPSG:4326' 或 'EPSG:3826'
    """
    # 移除 NaN 和 0 值
    valid_coords = df[(df[lon_col].notna()) & (df[lat_col].notna()) & 
                      (df[lon_col] != 0) & (df[lat_col] != 0)]
    
    if len(valid_coords) == 0:
        print("⚠ 警告：沒有有效的座標資料")
        return None
    
    # 取樣本
    sample = valid_coords.head(100)
    lon_values = sample[lon_col].values
    lat_values = sample[lat_col].values
    
    # EPSG:4326 的範圍檢查
    # 經度: 119-122, 緯度: 21-26
    wgs84_match = np.sum((lon_values >= 119) & (lon_values <= 123) & 
                         (lat_values >= 21) & (lat_values <= 26))
    
    # EPSG:3826 (TWD97 TM2) 的範圍檢查
    # X: 約 140000-380000, Y: 約 2400000-2900000
    twd97_match = np.sum((lon_values >= 140000) & (lon_values <= 400000) & 
                         (lat_values >= 2400000) & (lat_values <= 2950000))
    
    wgs84_ratio = wgs84_match / len(sample)
    twd97_ratio = twd97_match / len(sample)
    
    print(f"座標系統檢測：")
    print(f"  WGS84 (EPSG:4326) 符合率: {wgs84_ratio:.1%}")
    print(f"  TWD97 (EPSG:3826) 符合率: {twd97_ratio:.1%}")
    
    if wgs84_ratio > 0.8:
        return 'EPSG:4326'
    elif twd97_ratio > 0.8:
        return 'EPSG:3826'
    else:
        print("⚠ 警告：無法確定座標系統")
        print(f"樣本座標範圍：")
        print(f"  經度/X: {lon_values.min():.2f} ~ {lon_values.max():.2f}")
        print(f"  緯度/Y: {lat_values.min():.2f} ~ {lat_values.max():.2f}")
        return None

def convert_to_wgs84(df, source_epsg, lon_col='經度', lat_col='緯度'):
    """
    轉換座標到 WGS84 (EPSG:4326)
    
    Parameters:
        df: DataFrame
        source_epsg: 來源座標系統
        lon_col: 經度欄位名稱
        lat_col: 緯度欄位名稱
        
    Returns:
        DataFrame: 包含 lon_wgs84, lat_wgs84 欄位
    """
    df = df.copy()
    
    if source_epsg == 'EPSG:4326':
        print("✓ 座標系統已是 WGS84，無需轉換")
        df['lon_wgs84'] = df[lon_col]
        df['lat_wgs84'] = df[lat_col]
        return df
    
    print(f"正在轉換座標從 {source_epsg} 到 EPSG:4326...")
    
    # 建立轉換器
    transformer = Transformer.from_crs(source_epsg, 'EPSG:4326', always_xy=True)
    
    # 轉換座標
    valid_mask = (df[lon_col].notna()) & (df[lat_col].notna()) & \
                 (df[lon_col] != 0) & (df[lat_col] != 0)
    
    lon_wgs84 = np.full(len(df), np.nan)
    lat_wgs84 = np.full(len(df), np.nan)
    
    if valid_mask.sum() > 0:
        lon_wgs84[valid_mask], lat_wgs84[valid_mask] = transformer.transform(
            df.loc[valid_mask, lon_col].values,
            df.loc[valid_mask, lat_col].values
        )
    
    df['lon_wgs84'] = lon_wgs84
    df['lat_wgs84'] = lat_wgs84
    
    print(f"✓ 座標轉換完成")
    
    return df

def is_in_taiwan(lon, lat):
    """
    檢查座標是否在台灣邊界內
    
    Parameters:
        lon: 經度 (WGS84)
        lat: 緯度 (WGS84)
        
    Returns:
        bool: True 表示在台灣境內
    """
    if pd.isna(lon) or pd.isna(lat):
        return False
    
    return (TAIWAN_BBOX['lon_min'] <= lon <= TAIWAN_BBOX['lon_max'] and
            TAIWAN_BBOX['lat_min'] <= lat <= TAIWAN_BBOX['lat_max'])

def filter_invalid_coordinates(df):
    """
    過濾異常座標點位
    
    Parameters:
        df: DataFrame (必須包含 lon_wgs84, lat_wgs84)
        
    Returns:
        DataFrame: 過濾後的資料
    """
    print("\n正在過濾異常點位...")
    
    original_count = len(df)
    
    # 1. 移除 (0, 0) 點
    df = df[~((df['lon_wgs84'] == 0) & (df['lat_wgs84'] == 0))]
    zero_removed = original_count - len(df)
    
    # 2. 移除 NaN
    df = df[df['lon_wgs84'].notna() & df['lat_wgs84'].notna()]
    nan_removed = original_count - zero_removed - len(df)
    
    # 3. 移除台灣邊界外的點
    df['in_taiwan'] = df.apply(
        lambda row: is_in_taiwan(row['lon_wgs84'], row['lat_wgs84']), 
        axis=1
    )
    out_of_bounds = (~df['in_taiwan']).sum()
    df = df[df['in_taiwan']].drop(columns=['in_taiwan'])
    
    final_count = len(df)
    
    print(f"過濾結果：")
    print(f"  原始筆數: {original_count}")
    print(f"  移除 (0,0) 點: {zero_removed} 筆")
    print(f"  移除 NaN 值: {nan_removed} 筆")
    print(f"  移除台灣邊界外: {out_of_bounds} 筆")
    print(f"  有效筆數: {final_count} 筆")
    print(f"  保留率: {final_count/original_count:.1%}\n")
    
    return df

def classify_indoor_outdoor(facility_name):
    """
    根據設施名稱語意分析判斷室內/室外
    
    Parameters:
        facility_name: 設施名稱
        
    Returns:
        bool: True=室內, False=室外, None=無法判斷
    """
    if pd.isna(facility_name) or facility_name == '':
        return None
    
    facility_name = str(facility_name)
    
    # 檢查室外關鍵字（優先，因為更明確）
    for keyword in OUTDOOR_KEYWORDS:
        if keyword in facility_name:
            return False
    
    # 檢查室內關鍵字
    for keyword in INDOOR_KEYWORDS:
        if keyword in facility_name:
            return True
    
    # 如果 CSV 原本有「室內」「室外」欄位，優先使用
    return None

def add_indoor_classification(df, name_col='避難收容處所名稱'):
    """
    新增 is_indoor 欄位
    
    Parameters:
        df: DataFrame
        name_col: 設施名稱欄位
        
    Returns:
        DataFrame: 包含 is_indoor 欄位
    """
    print("正在進行室內/室外語意分析...")
    
    df = df.copy()
    
    # 先檢查是否已有「室內」欄位
    if '室內' in df.columns and '室外' in df.columns:
        print("✓ 發現原始資料包含「室內」「室外」欄位，將結合使用")
        
        def combine_classification(row):
            # 優先使用原始標記
            if row['室內'] == '是':
                return True
            elif row['室外'] == '是':
                return False
            # 如果原始標記不明確，使用語意分析
            else:
                return classify_indoor_outdoor(row[name_col])
        
        df['is_indoor'] = df.apply(combine_classification, axis=1)
    else:
        # 純用語意分析
        df['is_indoor'] = df[name_col].apply(classify_indoor_outdoor)
    
    # 統計
    indoor_count = (df['is_indoor'] == True).sum()
    outdoor_count = (df['is_indoor'] == False).sum()
    unknown_count = df['is_indoor'].isna().sum()
    
    print(f"\n分類結果：")
    print(f"  室內設施: {indoor_count} 筆 ({indoor_count/len(df):.1%})")
    print(f"  室外設施: {outdoor_count} 筆 ({outdoor_count/len(df):.1%})")
    print(f"  無法判斷: {unknown_count} 筆 ({unknown_count/len(df):.1%})\n")
    
    # 顯示一些範例
    if unknown_count > 0 and unknown_count <= 10:
        print("無法判斷的設施範例：")
        unknown_samples = df[df['is_indoor'].isna()][name_col].head(10)
        for idx, name in enumerate(unknown_samples, 1):
            print(f"  {idx}. {name}")
        print()
    
    return df

def main():
    """主程式"""
    print("=" * 70)
    print("避難收容所資料分析")
    print("=" * 70)
    print()
    
    # 設定路徑
    project_root = Path(__file__).parent.parent
    data_dir = project_root / 'data'
    output_dir = project_root / 'outputs'
    output_dir.mkdir(exist_ok=True)
    
    # 尋找 CSV 檔案
    csv_files = list(data_dir.glob('避難*.csv'))
    
    if not csv_files:
        print("❌ 在 data/ 資料夾中找不到避難收容所 CSV 檔案")
        sys.exit(1)
    
    csv_file = csv_files[0]
    print(f"讀取檔案: {csv_file.name}\n")
    
    # 讀取資料
    try:
        df = pd.read_csv(csv_file, encoding='utf-8')
    except UnicodeDecodeError:
        df = pd.read_csv(csv_file, encoding='big5')
    
    print(f"✓ 成功讀取 {len(df)} 筆資料")
    print(f"欄位: {', '.join(df.columns.tolist())}\n")
    
    # 1. 檢測座標系統
    coord_system = detect_coordinate_system(df)
    if coord_system is None:
        print("❌ 無法確定座標系統，程式終止")
        sys.exit(1)
    
    print(f"✓ 檢測到座標系統: {coord_system}\n")
    
    # 2. 轉換到 WGS84
    df = convert_to_wgs84(df, coord_system)
    
    # 3. 過濾異常點位
    df_clean = filter_invalid_coordinates(df)
    
    # 4. 語意分析新增 is_indoor 欄位
    df_clean = add_indoor_classification(df_clean)
    
    # 5. 儲存結果
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    # 儲存完整資料 (包含原始欄位 + 新增欄位)
    output_csv = output_dir / f'shelters_analyzed_{timestamp}.csv'
    df_clean.to_csv(output_csv, index=False, encoding='utf-8-sig')
    print(f"✓ 完整分析結果已儲存: {output_csv}")
    
    # 儲存簡化版 (只保留關鍵欄位)
    key_columns = [
        '序號', '縣市及鄉鎮市區', '避難收容處所名稱', '避難收容處所地址',
        'lon_wgs84', 'lat_wgs84', 'is_indoor', '預計收容人數', '適用災害類別'
    ]
    # 只保留存在的欄位
    available_columns = [col for col in key_columns if col in df_clean.columns]
    df_simple = df_clean[available_columns]
    
    output_simple = output_dir / f'shelters_simplified_{timestamp}.csv'
    df_simple.to_csv(output_simple, index=False, encoding='utf-8-sig')
    print(f"✓ 簡化版資料已儲存: {output_simple}")
    
    # 儲存 JSON
    output_json = output_dir / f'shelters_analyzed_{timestamp}.json'
    df_clean.to_json(output_json, orient='records', force_ascii=False, indent=2)
    print(f"✓ JSON 格式已儲存: {output_json}")
    
    # 6. 統計報告
    print("\n" + "=" * 70)
    print("分析統計報告")
    print("=" * 70)
    print(f"總處理筆數: {len(df_clean)}")
    print(f"座標系統: {coord_system} → EPSG:4326")
    
    if '縣市及鄉鎮市區' in df_clean.columns:
        print(f"\n縣市分布:")
        city_counts = df_clean['縣市及鄉鎮市區'].str.extract(r'(^[^縣市]+[縣市])')[0].value_counts()
        for city, count in city_counts.head(10).items():
            print(f"  {city}: {count} 處")
    
    print(f"\n室內/室外分類:")
    print(f"  室內設施: {(df_clean['is_indoor'] == True).sum()} 處")
    print(f"  室外設施: {(df_clean['is_indoor'] == False).sum()} 處")
    print(f"  無法判斷: {df_clean['is_indoor'].isna().sum()} 處")
    
    print("\n" + "=" * 70)
    print("✓ 分析完成！")
    print("=" * 70)

if __name__ == "__main__":
    main()
