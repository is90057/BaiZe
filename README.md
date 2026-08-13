# BaiZe

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10%2B-blue.svg" alt="Python 3.10+">
  <img src="https://img.shields.io/badge/GUI-PyQt6-green.svg" alt="PyQt6">
  <img src="https://img.shields.io/badge/Media-FFmpeg-orange.svg" alt="FFmpeg">
  <img src="https://img.shields.io/badge/AI-Whisper-violet.svg" alt="Whisper AI">
  <img src="https://img.shields.io/badge/License-MIT-brightgreen.svg" alt="License">
</p>

<p align="center">
  <b>切換語言 / Language:</b><br>
  <a href="#繁體中文"><b>繁體中文</b></a> | <a href="#english"><b>English</b></a>
</p>

---

<a id="繁體中文"></a>
# 🎬 BaiZe (繁體中文)

**BaiZe** 是一款基於 **Python 3**、**PyQt6** 與 **FFmpeg** 打造的專業非線性影片剪輯軟體（NLE）。具備靈活的多軌道時間軸剪輯、影格精準預覽、Chroma Key 綠幕去背、豐富轉場與特效、AI 語音自動上字幕（Whisper AI）以及靈活的 FFmpeg 影片匯出功能。

---

## 🌟 主要特色

- 🎬 **多軌道時間軸剪輯**
  - 支援多視訊軌（V1, V2...）與多音訊軌（A1, A2...）。
  - 媒體庫檔案可直接拖曳至時間軸軌道。
  - 影格精準的片段移動、修剪（Trim）、剪斷（Split）與刪除，具備磁性貼齊（Snap-to-edge）功能。
  - 支援入點 / 出點（In / Out Point）範圍選取與標記。

- 👁 **影格精準預覽與播放**
  - 使用 PyAV / FFmpeg 實現高效的影片解碼與實時預覽。
  - 完整的播放控制（播放/暫停、逐格前進/後退、跳至開頭/結尾、播放頭拖曳導覽）。

- 🪄 **綠幕去背與影片特效**
  - **Chroma Key 綠幕去背**：支援綠幕與藍幕去背，可自訂相似度容差（Similarity）與邊緣平滑度（Smoothness）。
  - **罐頭濾鏡特效**：經典黑白、復古懷舊、負片反轉、高對比鮮豔、柔焦模糊、水平鏡像、電影暗角等。

- 🔄 **無縫轉場特效庫**
  - 內建 15+ 種轉場效果：交叉淡入淡出、黑場/白場轉場、四向擦除（Wipe）、四向滑動（Slide）、鏡頭縮放（Zoom In）、圓形揭開（Circle Crop）等。
  - 可為任意片段自訂轉場類型與持續時間。

- ✨ **AI 語音識別自動上字幕 (Whisper AI)**
  - 整合 OpenAI Whisper 模型（tiny / base / small），能自動識別影片/音訊中的語音並精準生成同步字幕。
  - 支援自動語言辨識以及多國語言（中文、英文、日文、韓文等）。
  - 完整的**字幕編輯器**：支援字型、字號、文字顏色、背景框、描邊效果與對齊位置設定。
  - 支援 SRT 字幕檔匯入與匯出。

- ⚡ **強大的 FFmpeg 匯出引擎**
  - 支援格式與編碼：H.264 MP4, H.265 / HEVC MP4, ProRes 422 MOV。
  - 自訂解析度、影格率、縮放模式（等比信箱式 Fit、裁切填滿 Crop、拉伸 Stretch）、位元率與 CRF 畫質控制（0-30）。
  - 可選擇匯出整個時間軸或僅匯出 In-Out 標記範圍。

- 🌐 **多國語言介面與系統整合**
  - 支援介面語言即時切換：繁體中文、簡體中文、英文（選單 `Language >`）。
  - 完整的歷史紀錄復原 / 重做系統（Undo / Redo）。
  - 專案檔儲存與載入（`.bzproj` 格式）。

---

## 💻 系統需求

- **Python**: >= 3.10
- **FFmpeg**: 需安裝於系統環境變數（PATH）中
- **作業系統**: macOS / Windows / Linux

---

## 🚀 安裝說明

### 1. 複製專案庫

```bash
git clone https://github.com/your-username/BaiZe.git
cd BaiZe
```

### 2. 安裝 Python 依賴套件

```bash
pip install -r requirements.txt
```

### 3. 安裝 FFmpeg

- **macOS** (使用 Homebrew):
  ```bash
  brew install ffmpeg
  ```
- **Ubuntu / Debian**:
  ```bash
  sudo apt update && sudo apt install ffmpeg
  ```
- **Windows**:
  使用 `winget install FFmpeg` 或至 [FFmpeg 官網](https://ffmpeg.org/download.html) 下載並將 `ffmpeg.exe` 新增至 PATH 環境變數。

### 4. (可選) 安裝 Whisper AI 語音識別

若需要使用 AI 自動生成字幕功能，可安裝 OpenAI Whisper：
```bash
pip install openai-whisper
```

---

## 🎯 快速開始與使用步驟

1. **啟動軟體**
   ```bash
   python main.py
   ```
2. **匯入媒體**：點擊選單 `檔案 > 匯入媒體...` 或直接將影片/音訊檔案拖曳進「媒體庫」面板。
3. **編排時間軸**：從媒體庫將剪輯拖曳至時間軸軌道（V1 視訊軌、A1 音訊軌等）。
4. **剪輯與調整**：
   - 點擊並拖曳片段以移動位置；拖曳片段左右邊緣進行修剪。
   - 將播放頭移動至目標位置，按下 `Ctrl+B` 在播放頭處切斷片段。
   - 在「檢查器 (Inspector)」中調整片段的縮放、不透明度、音量、播放速度或套用綠幕去背。
5. **添加轉場與特效**：選取片段後，在「轉場特效」或「特效」面板中套用效果。
6. **添加字幕與 AI 辨識**：在「字幕工具」面板手動新增字幕，或點擊 `✨ 開始自動語音辨識上字幕` 自動生成字幕。
7. **匯出影片**：按下 `Ctrl+E`（或選單 `檔案 > 匯出...`），選擇格式與品質後點擊匯出。

---

## ⌨️ 快捷鍵一覽表

| 快捷鍵 | 功能說明 |
|---|---|
| `Space` | 播放 / 暫停 (Play / Pause) |
| `I` / `O` | 設定入點 (In) / 出點 (Out) 範圍 |
| `Ctrl+B` | 在播放頭位置切斷選取片段 (Split) |
| `Delete` / `Backspace` | 刪除選取的片段 |
| `Ctrl+Z` | 復原 (Undo) |
| `Ctrl+Shift+Z` / `Ctrl+Y` | 重做 (Redo) |
| `+` / `-` | 放大 / 縮小時間軸顯示 |
| `R` | 適度顯示整條時間軸 (Fit Timeline) |
| `Home` / `End` | 跳至時間軸開頭 / 結尾 |
| `←` / `→` | 逐影格移動播放頭 (Step Frame) |
| `Ctrl+E` | 開啟影片匯出對話框 |

---

## 📁 專案架構說明

```
BaiZe/
├── main.py                  # 應用程式進入點
├── requirements.txt         # 核心依賴套件
├── README.md                # 專案說明文件
└── app/
    ├── main_window.py       # 主視窗 GUI 介面與選單路由
    ├── i18n.py              # 多國語言 (i18n) 國際化管理
    ├── theme.py             # UI 主題與深色模式樣式
    ├── controllers/
    │   └── project_controller.py  # 專案狀態控制與 Undo/Redo 命令棧
    ├── core/
    │   ├── ffmpeg.py        # FFmpeg 解碼、圖層合成與影片渲染核心
    │   ├── asr.py           # Whisper AI 語音識別與字幕生成引擎
    │   └── utils.py          # 時間碼格式化等通用工具
    ├── models/
    │   ├── media.py         # 媒體檔案與 Clip 資料模型
    │   └── project.py       # 專案檔與時間軸資料架構
    └── views/
        ├── media_panel.py       # 媒體庫面板
        ├── timeline_widget.py   # 多軌道時間軸畫布
        ├── preview_widget.py    # 影格預覽播放器
        ├── inspector_panel.py   # 屬性檢查器面板 (Transform / Audio / Chroma Key)
        ├── transitions_panel.py # 轉場特效庫面板
        ├── subtitle_panel.py    # 字幕編輯與 AI 語音識別面板
        ├── effects_panel.py     # 罐頭濾鏡特效面板
        ├── export_dialog.py     # 影片匯出設定對話框
        └── transport_bar.py     # 播放控制條
```

---

<a id="english"></a>
# 🎬 BaiZe (English)

**BaiZe** is a full-featured, non-linear video editor (NLE) built with **Python 3**, **PyQt6**, and **FFmpeg**. It provides frame-accurate multi-track video editing, real-time preview playback, Chroma Key green screen removal, rich video transitions & visual filters, AI-powered automatic speech-to-subtitle generation (Whisper AI), and robust video rendering via FFmpeg.

---

## 🌟 Key Features

- 🎬 **Multi-Track Timeline Editing**
  - Unlimited video (V1, V2...) and audio (A1, A2...) tracks.
  - Drag-and-drop media directly from the library onto timeline tracks.
  - Frame-accurate clipping: move, trim, split (`Ctrl+B`), and delete clips with magnetic snap-to-edge.
  - In / Out point range markers and selection.

- 👁 **Frame-Accurate Preview & Playback**
  - High-performance real-time decoding powered by PyAV / FFmpeg.
  - Complete transport bar controls: play/pause, step backward/forward frame-by-frame, jump to start/end, and playhead scrubbing.

- 🪄 **Chroma Key & Visual Filters**
  - **Chroma Key (Green/Blue Screen Removal)**: Key out solid backgrounds with configurable similarity tolerance and edge smoothness.
  - **Preset Video Filters**: Grayscale, Sepia Vintage, Color Invert, Vivid Boost, Soft Blur, Horizontal Mirror, Cinema Vignette, and more.

- 🔄 **Transition Effects Library**
  - 15+ built-in seamless transitions: Crossfade, Fade to Black, Fade to White, Wipes (4 directions), Slides (4 directions), Zoom In, Circle Crop, etc.
  - Customizable transition types and durations for any clip.

- ✨ **AI Auto-Subtitling (Whisper ASR) & Subtitle Editor**
  - Integrated OpenAI Whisper AI (`tiny`, `base`, `small`) for automated speech recognition and synchronized subtitle generation.
  - Supports automatic language detection and multiple spoken languages (English, Traditional/Simplified Chinese, Japanese, Korean, etc.).
  - **Comprehensive Subtitle Styling**: Customize font family, size, text color, background color, stroke outline, and text alignment.
  - Import and export SRT subtitle files.

- ⚡ **Flexible FFmpeg Export Engine**
  - Supported Formats & Codecs: H.264 MP4, H.265 / HEVC MP4, ProRes 422 MOV.
  - Customizable resolution, frame rate, aspect ratio scaling (Letterbox Fit / Crop to Fill / Stretch), video & audio bitrates, and CRF quality tuning (0–30).
  - Export full timeline or selected In-Out region.

- 🌐 **Multilingual Interface & Productivity**
  - Instant UI language switching: English, 繁體中文, 简体中文 (`Language >` menu).
  - Full Undo / Redo history stack (`Ctrl+Z`, `Ctrl+Shift+Z`).
  - Project file save / load (`.bzproj` format).

---

## 💻 Requirements

- **Python**: >= 3.10
- **FFmpeg**: Installed and accessible in your system `PATH`
- **OS**: macOS / Windows / Linux

---

## 🚀 Installation

### 1. Clone the Repository

```bash
git clone https://github.com/your-username/BaiZe.git
cd BaiZe
```

### 2. Install Python Dependencies

```bash
pip install -r requirements.txt
```

### 3. Install FFmpeg

- **macOS** (via Homebrew):
  ```bash
  brew install ffmpeg
  ```
- **Ubuntu / Debian**:
  ```bash
  sudo apt update && sudo apt install ffmpeg
  ```
- **Windows**:
  Run `winget install FFmpeg` or download from [FFmpeg Official Site](https://ffmpeg.org/download.html) and add `ffmpeg.exe` to your `PATH`.

### 4. (Optional) Install Whisper AI for Auto Subtitling

To enable AI automatic speech-to-subtitle generation:
```bash
pip install openai-whisper
```

---

## 🎯 Quick Start & Workflow

1. **Launch Application**
   ```bash
   python main.py
   ```
2. **Import Media**: Click `File > Import Media...` or drag & drop files into the Media panel.
3. **Assemble Clips**: Drag clips from the Media panel onto video or audio tracks.
4. **Edit Timeline**:
   - Click and drag clips to move; drag edges to trim.
   - Position playhead and press `Ctrl+B` to split clips.
   - Use the **Inspector** panel to adjust opacity, scale, position, volume, playback speed, or toggle Chroma Key.
5. **Apply Effects & Transitions**: Select a clip and choose from the **Transitions** or **Effects** panels.
6. **Subtitles & AI Transcribe**: Add subtitles manually in the **Subtitles** panel or click `✨ Recognize & Generate Subtitles`.
7. **Export Video**: Press `Ctrl+E` (or `File > Export...`), select your format and quality settings, then render.

---

## ⌨️ Keyboard Shortcuts

| Shortcut | Action |
|---|---|
| `Space` | Play / Pause |
| `I` / `O` | Set In / Out points |
| `Ctrl+B` | Split clip at playhead |
| `Delete` / `Backspace` | Delete selected clip |
| `Ctrl+Z` | Undo |
| `Ctrl+Shift+Z` / `Ctrl+Y` | Redo |
| `+` / `-` | Zoom timeline in / out |
| `R` | Fit timeline to view |
| `Home` / `End` | Jump to timeline start / end |
| `←` / `→` | Step frame backward / forward |
| `Ctrl+E` | Open export dialog |

---

## 📁 Project Architecture

```
BaiZe/
├── main.py                  # Application entry point
├── requirements.txt         # Core Python dependencies
├── README.md                # Project documentation
└── app/
    ├── main_window.py       # Main GUI window & menu routing
    ├── i18n.py              # Internationalization & translation manager
    ├── theme.py             # UI theme & dark mode styles
    ├── controllers/
    │   └── project_controller.py  # Project state & Undo/Redo command stack
    ├── core/
    │   ├── ffmpeg.py        # FFmpeg decoding, compositing & export engine
    │   ├── asr.py           # Whisper AI speech recognition engine
    │   └── utils.py          # Timecode formatting & general utilities
    ├── models/
    │   ├── media.py         # Media item & clip data models
    │   └── project.py       # Project & timeline data structures
    └── views/
        ├── media_panel.py       # Media library panel
        ├── timeline_widget.py   # Multi-track timeline canvas
        ├── preview_widget.py    # Frame-accurate preview player
        ├── inspector_panel.py   # Properties inspector panel (Transform / Audio / Chroma Key)
        ├── transitions_panel.py # Transition effects library panel
        ├── subtitle_panel.py    # Subtitle editor & AI speech recognition panel
        ├── effects_panel.py     # Preset video filters panel
        ├── export_dialog.py     # Video export configuration dialog
        └── transport_bar.py     # Playback control bar
```

---

## 📄 License

Distributed under the **MIT License**.