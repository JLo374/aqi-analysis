# AQI 監測與空間分析專案

即時空氣品質指標（AQI）監測站資料擷取與視覺化分析專案，包含空間距離計算功能。

## 📁 專案結構

```
.
├── data/               # 原始資料目錄
├── outputs/            # 分析結果輸出目錄
│   ├── aqi_data_*.csv        # AQI 資料 (CSV 格式，含距離資訊)
│   ├── aqi_data_*.json       # AQI 資料 (JSON 格式)
│   └── aqi_map_*.html        # 互動式地圖
├── scripts/            # 分析腳本目錄
│   └── fetch_aqi_data.py     # AQI 資料擷取與視覺化腳本
├── .env                # 環境變數設定（包含 API Keys）
├── .gitignore          # Git 忽略檔案清單
├── requirements.txt    # Python 套件依賴清單
└── README.md          # 專案說明文件
```

## 🚀 快速開始

### 1. 環境設定

確認 `.env` 檔案中已設定您的 MOENV API Key：

```env
MOENV_API_KEY=your_api_key_here
```

### 2. 執行腳本

執行 AQI 資料擷取腳本（會自動安裝所需套件）：

```bash
python scripts/fetch_aqi_data.py
```

### 3. 查看結果

腳本執行完成後，會在 `outputs/` 目錄下產生：
- `aqi_data_*.csv` - AQI 資料（CSV 格式，包含距離欄位）
- `aqi_data_*.json` - AQI 資料（JSON 格式）
- `aqi_map_*.html` - 互動式地圖（可用瀏覽器開啟）

## 📊 功能特色

### AQI 資料擷取
- ✅ 自動從環境部資料開放平台獲取即時 AQI 資料
- ✅ 從 `.env` 檔案安全讀取 API Key
- ✅ 自動處理套件依賴安裝

### 空間計算
- ✅ **自動計算每個監測站到台北車站的距離（公里）**
- ✅ 使用 Haversine 公式精確計算地球表面兩點間距離
- ✅ 顯示最近/最遠監測站統計資訊

### 資料視覺化
- ✅ 使用 Folium 建立互動式地圖
- ✅ 所有監測站位置標記
- ✅ **簡化的三級 AQI 顏色編碼**
  - 🟢 綠色 (0-50): 良好
  - 🟡 黃色 (51-100): 普通
  - 🔴 紅色 (101+): 不健康
- ✅ 點擊標記顯示站名、縣市、即時 AQI 值
- ✅ 圖例說明 AQI 分級標準

### 資料輸出
- ✅ CSV 格式（包含 `distance_to_taipei_km` 欄位）
- ✅ JSON 格式（適合程式處理）
- ✅ HTML 互動式地圖（適合視覺化展示）

## 📦 使用的套件

- `requests` - API 請求
- `python-dotenv` - 環境變數管理
- `folium` - 互動式地圖視覺化
- `pandas` - 資料處理與分析

## 🎨 AQI 分級說明

| AQI 範圍 | 狀態 | 顏色 |
|---------|------|------|
| 0-50 | 良好 | 綠色 |
| 51-100 | 普通 | 黃色 |
| 101+ | 不健康 | 紅色 |

## 📍 參考點

**台北車站座標**: 25.0478°N, 121.5170°E

所有監測站到台北車站的距離已自動計算並儲存在輸出的 CSV 和 JSON 檔案中。

## 🔒 安全性

- `.env` 檔案已加入 `.gitignore`，不會被上傳到 GitHub
- API Key 等敏感資訊請妥善保管
- 輸出資料檔案（CSV, JSON, HTML）不會被版本控制

## 📈 資料範例

執行腳本後的統計輸出範例：

```
資料統計：
  監測站數量: 84
  縣市數量: 22
  平均 AQI: 55.69
  最高 AQI: 117
  最低 AQI: 12

距離統計（到台北車站）：
  最近監測站: 萬華 (0.92 km)
  最遠監測站: 恆春 (351.49 km)
  平均距離: 145.71 km
```

## 🌐 GitHub Repository

Repository: https://github.com/JLo374/aqi-analysis

## 📝 授權

本專案僅供學術研究與教育用途。

---

**資料來源**: [環境部資料開放平台](https://data.moenv.gov.tw/)
