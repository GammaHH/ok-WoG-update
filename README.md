# ok-WoG — War of Genesis: Idle Loot Automation

[English](README_en.md) | 中文

**ok-WoG** 是一個針對 **[WoG] War of Genesis: Idle Loot** 開發的開源自動化工具，  
基於 [ok-script](https://github.com/ok-oldking/ok-script) 框架製作。

本專案主要透過 **畫面辨識、模板匹配與 OCR** 操作遊戲 UI，
不修改遊戲檔案，也不依賴寫死的遊戲內部物件 ID。

> 本專案為非官方 **War of Genesis: Idle Loot** 自動化工具。

## ☕ 支持專案

如果這個專案對你有幫助，可以請我喝杯咖啡 ☕

[![Buy Me a Coffee](https://img.shields.io/badge/Buy%20Me%20a%20Coffee-Support%20this%20project-yellow?logo=buymeacoffee)](https://buymeacoffee.com/st810597m)

所有功能與 Releases 仍免費公開，贊助完全自願。

## 功能

### 自動訓練

- 自動掃描訓練項目
- 可設定優先強化項目
- OCR 金錢與升級成本辨識
- 自動處理多層前置訓練條件

### 自動倉庫儲存

- 偵測背包已滿
- 自動將物品存入倉庫
- 支援多個倉庫頁面

### 自動合成

- 背包滿且完成存倉後可自動進入合成
- 自動處理已辨識為綠色／藍色的素材
- 偵測空位或未知狀態時自動停止

### 關卡卡死偵測與恢復

- 持續監測金錢變化
- 偵測長時間無進度時嘗試重新進入目前關卡

### 其他功能

- 斷線偵測與重新連線
- OCR 畫面文字與數值辨識
- Template Matching UI 定位
- 依目前 UI 位置動態計算操作座標

## 語言支援

目前自動化辨識以 **繁體中文遊戲介面** 為主要支援環境。

部分功能包含中文 OCR、訓練項目名稱與前置條件文字解析，
因此目前不保證英文或其他語言的遊戲介面能正常運作。
## 使用方式

1. 啟動 **[WoG] War of Genesis: Idle Loot**
2. 確認遊戲程序 `Genesis.exe` 已執行
3. 啟動 **ok-WoG**
4. 在 **Task** 頁面開啟需要的自動化功能

目前工具只會尋找並連接：

`Genesis.exe`

工具本身不會自動啟動遊戲，因此可透過 Steam 啟動遊戲後再開啟本工具。

## 下載

請至 GitHub 右側的 **Releases** 頁面下載最新版本。

建議優先使用最新 Release，因為 **War of Genesis: Idle Loot** 仍持續更新，
遊戲 UI 變化可能影響 OCR、模板匹配或自動化流程。

## 安全機制

本工具在多個自動化流程中加入辨識與確認機制，避免單純依固定座標盲目操作。

例如自動合成功能只會繼續處理已辨識為綠色或藍色的素材；
若偵測到空位、未知顏色或 UI 狀態不符，流程會停止，而不是繼續點擊。

## 專案狀態

本專案目前仍持續開發、測試與改善中。

如果遊戲更新後出現 UI 改動、OCR 辨識錯誤或自動化流程異常，
歡迎透過 GitHub Issues 回報。

## 開發基礎

本專案基於以下開源專案：

- [ok-script](https://github.com/ok-oldking/ok-script)
- [ok-script-app](https://github.com/ok-oldking/ok-script-app)
- [OnnxOCR](https://github.com/ok-oldking/OnnxOCR)
- [PyQt-Fluent-Widgets](https://github.com/zhiyiYo/PyQt-Fluent-Widgets)

感謝原作者與所有相關開源專案的貢獻。

## 免責聲明

**ok-WoG** 為非官方社群專案，與 **War of Genesis: Idle Loot** 的開發商及發行商無關。

使用者應自行確認遊戲服務條款與相關規範，並自行承擔使用自動化工具可能產生的風險。

---

**Keywords:** War of Genesis, War of Genesis Idle Loot, WoG, ok-WoG, automation, auto training, auto storage, auto synthesis, OCR, computer vision, game automation

