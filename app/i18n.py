from __future__ import annotations

LANGUAGES = {
    "en": "English",
    "zh_TW": "繁體中文",
    "zh_CN": "简体中文",
}

_current = "en"
_callbacks: list = []

# key = English source string; value = {lang: translated}
_TRANSLATIONS: dict[str, dict[str, str]] = {
    # ---- menus ----
    "&File": {"zh_TW": "檔案(&F)", "zh_CN": "文件(&F)"},
    "&Edit": {"zh_TW": "編輯(&E)", "zh_CN": "编辑(&E)"},
    "&Track": {"zh_TW": "軌道(&T)", "zh_CN": "轨道(&T)"},
    "&Playback": {"zh_TW": "播放(&P)", "zh_CN": "播放(&P)"},
    "&Help": {"zh_TW": "說明(&H)", "zh_CN": "帮助(&H)"},
    "Language": {"zh_TW": "語言", "zh_CN": "语言"},
    "New…": {"zh_TW": "新建…", "zh_CN": "新建…"},
    "Open…": {"zh_TW": "開啟…", "zh_CN": "打开…"},
    "Save": {"zh_TW": "儲存", "zh_CN": "保存"},
    "Save As…": {"zh_TW": "另存為…", "zh_CN": "另存为…"},
    "Import Media…": {"zh_TW": "匯入媒體…", "zh_CN": "导入媒体…"},
    "Export…": {"zh_TW": "匯出…", "zh_CN": "导出…"},
    "Quit": {"zh_TW": "結束", "zh_CN": "退出"},
    "&Undo": {"zh_TW": "復原(&U)", "zh_CN": "撤销(&U)"},
    "&Redo": {"zh_TW": "重做(&R)", "zh_CN": "重做(&R)"},
    "Cut Selected (Video & Audio)": {"zh_TW": "剪輯選取片段 (剪除影片及音檔)", "zh_CN": "剪辑所选片段 (剪除视频及音频)"},
    "Split Selected at Playhead": {"zh_TW": "在播放頭處剪斷選取片段", "zh_CN": "在播放头处剪切所选片段"},
    "Delete Selected": {"zh_TW": "刪除選取片段", "zh_CN": "删除所选片段"},
    "Set In Point": {"zh_TW": "設定起點", "zh_CN": "设置入点"},
    "Set Out Point": {"zh_TW": "設定終點", "zh_CN": "设置出点"},
    "Add Video Track": {"zh_TW": "新增視訊軌道", "zh_CN": "添加视频轨道"},
    "Add Audio Track": {"zh_TW": "新增音訊軌道", "zh_CN": "添加音频轨道"},
    "Fit Timeline": {"zh_TW": "適度顯示時間軸", "zh_CN": "适配显示时间轴"},
    "Play / Pause": {"zh_TW": "播放 / 暫停", "zh_CN": "播放 / 暂停"},
    "Stop": {"zh_TW": "停止", "zh_CN": "停止"},
    "Previous Frame": {"zh_TW": "上一影格", "zh_CN": "上一帧"},
    "Next Frame": {"zh_TW": "下一影格", "zh_CN": "下一帧"},
    "Go to Start": {"zh_TW": "跳到開頭", "zh_CN": "跳到开头"},
    "Go to End": {"zh_TW": "跳到結尾", "zh_CN": "跳到结尾"},
    "About BaiZe": {"zh_TW": "關於 BaiZe", "zh_CN": "关于 BaiZe"},
    "Language…": {"zh_TW": "語言…", "zh_CN": "语言…"},

    # ---- transport ----
    "Play / Pause  (Space)": {"zh_TW": "播放 / 暫停 (空白鍵)", "zh_CN": "播放 / 暂停 (空格键)"},
    "Go to Start  (Home)": {"zh_TW": "跳到開頭 (Home)", "zh_CN": "跳到开头 (Home)"},
    "Previous Frame  (Left)": {"zh_TW": "上一影格 (←)", "zh_CN": "上一帧 (←)"},
    "Next Frame  (Right)": {"zh_TW": "下一影格 (→)", "zh_CN": "下一帧 (→)"},
    "Go to End  (End)": {"zh_TW": "跳到結尾 (End)", "zh_CN": "跳到结尾 (End)"},
    "Set In Point  (I)": {"zh_TW": "設定起點 (I)", "zh_CN": "设置入点 (I)"},
    "Set Out Point  (O)": {"zh_TW": "設定終點 (O)", "zh_CN": "设置出点 (O)"},
    "Clear In/Out": {"zh_TW": "清除起點/終點", "zh_CN": "清除入点/出点"},
    "In": {"zh_TW": "入點", "zh_CN": "入点"},
    "Out": {"zh_TW": "出點", "zh_CN": "出点"},
    "Select Range": {"zh_TW": "選取區間", "zh_CN": "选取区间"},
    "Select Range on Timeline  (Shift+Drag)": {
        "zh_TW": "在時間軸拖曳選取不要的片段區間 (或按住 Shift 拖曳)",
        "zh_CN": "在时间轴拖动选取不要的片段区间 (或按住 Shift 拖动)",
    },
    "Split": {"zh_TW": "分割", "zh_CN": "分割"},
    "Split at Playhead  (Ctrl+B)": {"zh_TW": "在播放頭處分割片段 (Ctrl+B)", "zh_CN": "在播放头处分割片段 (Ctrl+B)"},
    "Cut": {"zh_TW": "剪輯", "zh_CN": "剪辑"},
    "Cut Selected Segment": {"zh_TW": "剪輯 (剪除選取片段)", "zh_CN": "剪辑 (剪除所选片段)"},
    "Cut Selected Segment (Video & Audio)  (Ctrl+X)": {
        "zh_TW": "剪輯：將選取的影片及音檔剪掉 (Ctrl+X)",
        "zh_CN": "剪辑：将所选的视频及音频剪掉 (Ctrl+X)",
    },
    "Selected": {"zh_TW": "已選取", "zh_CN": "已选取"},
    "Split clip at playhead": {"zh_TW": "已在播放頭處分割影片及音訊片段", "zh_CN": "已在播放头处分割视频及音频片段"},
    "Cut {dur:.2f}s of selected video and audio": {
        "zh_TW": "已將選取的影片及音檔剪掉 ({dur:.2f} 秒)",
        "zh_CN": "已将所选的视频及音频剪掉 ({dur:.2f} 秒)",
    },
    "Please select an unwanted clip on the timeline or mark an In–Out range first, then click Cut.": {
        "zh_TW": "請先在時間軸點選不要的片段，或使用「選取區間 / 設定起終點 (I/O)」標記範圍後，再點選「剪輯」。",
        "zh_CN": "请先在时间轴点选不要的片段，或使用「选取区间 / 设置入出点 (I/O)」标记范围后，再点选「剪辑」。",
    },

    # ---- media panel ----
    "Media Library": {"zh_TW": "媒體庫", "zh_CN": "媒体库"},
    "Import…": {"zh_TW": "匯入…", "zh_CN": "导入…"},
    "Import media files": {"zh_TW": "匯入媒體檔案", "zh_CN": "导入媒体文件"},
    "Drag media onto a timeline track to add it.": {
        "zh_TW": "將媒體拖到時間軸軌道上即可加入。", "zh_CN": "将媒体拖到时间轴的轨道上即可加入。"},
    "Add to Timeline (V1 at playhead)": {
        "zh_TW": "加入時間軸 (播放頭處的 V1)", "zh_CN": "添加到时间轴 (入点处 V1)"},
    "Remove from Library": {"zh_TW": "從媒體庫移除", "zh_CN": "从媒体库移除"},
    "In Use": {"zh_TW": "使用中", "zh_CN": "使用中"},
    "{name} is used on the timeline and cannot be removed.": {
        "zh_TW": "{name} 已在時間軸上使用，無法移除。", "zh_CN": "{name} 已在时间轴上使用，无法移除。"},

    # ---- timeline ----
    "Cut Selected (Video & Audio)\tCtrl+X": {
        "zh_TW": "✂️ 剪輯選取片段 (剪除影片及音檔)\tCtrl+X",
        "zh_CN": "✂️ 剪辑所选片段 (剪除视频及音频)\tCtrl+X",
    },
    "Split at Playhead\tCtrl+B": {"zh_TW": "在播放頭處剪斷\tCtrl+B", "zh_CN": "在播放头处剪切\tCtrl+B"},
    "Delete Clip\tDelete": {"zh_TW": "刪除片段\tDelete", "zh_CN": "删除片段\tDelete"},

    # ---- timeline hint ----
    "Timeline hint": {
        "zh_TW": "時間軸 • 點選不要的片段或按住 Shift 拖曳選取區間，點選「✂️ 剪輯」即可將選取的影片及音檔剪掉 • Ctrl+滾輪縮放",
        "zh_CN": "时间轴 • 点选不要的片段或按住 Shift 拖动选取区间，点选「✂️ 剪辑」即可将所选的视频及音频剪掉 • Ctrl+滚轮缩放"},

    # ---- inspector ----
    "Inspector": {"zh_TW": "檢查器", "zh_CN": "检查器"},
    ("Select a clip on the timeline to edit.\n\n"
     "Video: trim, position, opacity.\n"
     "Audio: trim, position, volume."): {
        "zh_TW": ("在時間軸上選取片段以編輯屬性。\n\n"
                  "視訊：修剪、位置、透明度。\n"
                  "音訊：修剪、位置、音量。"),
        "zh_CN": ("在时间轴上选择片段以编辑属性。\n\n"
                  "视频：修剪、位置、不透明度。\n"
                  "音频：修剪、位置、音量。")},
    "Clip": {"zh_TW": "片段", "zh_CN": "片段"},
    "Name": {"zh_TW": "名稱", "zh_CN": "名称"},
    "Type": {"zh_TW": "類型", "zh_CN": "类型"},
    "Start (s)": {"zh_TW": "開始 (秒)", "zh_CN": "开始 (秒)"},
    "Duration (s)": {"zh_TW": "時間長度 (秒)", "zh_CN": "时长 (秒)"},
    "Trim In (s)": {"zh_TW": "片頭修剪 (秒)", "zh_CN": "入点修剪 (秒)"},
    "Volume": {"zh_TW": "音量", "zh_CN": "音量"},
    "Opacity": {"zh_TW": "透明度", "zh_CN": "不透明度"},
    "Video": {"zh_TW": "視訊", "zh_CN": "视频"},
    "Audio": {"zh_TW": "音訊", "zh_CN": "音频"},
    "Project": {"zh_TW": "專案", "zh_CN": "项目"},
    "media": {"zh_TW": "個媒體", "zh_CN": "个媒体"},
    "clips": {"zh_TW": "個片段", "zh_CN": "个片段"},
    "Duration": {"zh_TW": "時長", "zh_CN": "时长"},
    "All Supported Media": {"zh_TW": "所有支援的媒體檔", "zh_CN": "所有支持的媒体文件"},
    "Image Files": {"zh_TW": "圖片檔案", "zh_CN": "图片文件"},
    "Video Files": {"zh_TW": "影片檔案", "zh_CN": "视频文件"},
    "Audio Files": {"zh_TW": "音訊檔案", "zh_CN": "音频文件"},

    # ---- preview ----
    "No video at playhead": {"zh_TW": "播放頭處沒有視訊", "zh_CN": "播放头处没有视频"},
    "PLAYING": {"zh_TW": "播放中", "zh_CN": "播放中"},

    # ---- export dialog ----
    "Export Video": {"zh_TW": "匯出影片", "zh_CN": "导出视频"},
    "Format": {"zh_TW": "格式", "zh_CN": "格式"},
    "H.264 MP4": {"zh_TW": "H.264 MP4", "zh_CN": "H.264 MP4"},
    "H.265 / HEVC MP4": {"zh_TW": "H.265 / HEVC MP4", "zh_CN": "H.265 / HEVC MP4"},
    "ProRes 422 MOV": {"zh_TW": "ProRes 422 MOV", "zh_CN": "ProRes 422 MOV"},
    "Resolution": {"zh_TW": "解析度", "zh_CN": "分辨率"},
    "Match project": {"zh_TW": "符合專案", "zh_CN": "匹配项目"},
    "Frame rate": {"zh_TW": "影格率", "zh_CN": "帧率"},
    "Scaling": {"zh_TW": "縮放方式", "zh_CN": "缩放方式"},
    "Fit (letterbox)": {"zh_TW": "等比縮放 (信箱式)", "zh_CN": "等比缩放 (信箱式)"},
    "Crop to fill": {"zh_TW": "裁切填滿", "zh_CN": "裁剪填充"},
    "Stretch": {"zh_TW": "拉伸", "zh_CN": "拉伸"},
    "Range": {"zh_TW": "範圍", "zh_CN": "范围"},
    "Entire timeline": {"zh_TW": "整個時間軸", "zh_CN": "整个时间轴"},
    "In–Out range": {"zh_TW": "入點至出點範圍", "zh_CN": "入点到出点范围"},
    "Video bitrate": {"zh_TW": "視訊位元率", "zh_CN": "视频比特率"},
    "Leave empty for CRF quality": {"zh_TW": "留空則使用 CRF 畫質", "zh_CN": "留空则使用 CRF 质量"},
    "e.g. 8M": {"zh_TW": "例如 8M", "zh_CN": "例如 8M"},
    "Audio bitrate": {"zh_TW": "音訊位元率", "zh_CN": "音频比特率"},
    "Quality (CRF 0=best 30=worst)": {
        "zh_TW": "畫質 (CRF 0=最佳 30=最差)", "zh_CN": "质量 (CRF 0=最佳 30=最差)"},
    "Output:": {"zh_TW": "輸出：", "zh_CN": "输出："},
    "Browse…": {"zh_TW": "瀏覽…", "zh_CN": "浏览…"},
    "Export": {"zh_TW": "匯出", "zh_CN": "导出"},
    "Close": {"zh_TW": "關閉", "zh_CN": "关闭"},
    "Cancel": {"zh_TW": "取消", "zh_CN": "取消"},
    "Choose an output path.": {"zh_TW": "請選擇輸出路徑。", "zh_CN": "请选择输出路径。"},
    "Rendering…": {"zh_TW": "正在渲染…", "zh_CN": "正在渲染…"},
    "Export complete.": {"zh_TW": "匯出完成。", "zh_CN": "导出完成。"},
    "Video exported to\n": {"zh_TW": "影片已匯出至\n", "zh_CN": "视频已导出到\n"},
    "Export failed.": {"zh_TW": "匯出失敗。", "zh_CN": "导出失败。"},
    "Export failed.\n": {"zh_TW": "匯出失敗。\n", "zh_CN": "导出失败。\n"},
    "Export to": {"zh_TW": "匯出至", "zh_CN": "导出到"},

    # ---- status bar & dialogs ----
    "Ready": {"zh_TW": "就緒", "zh_CN": "就绪"},
    "Unsaved Changes": {"zh_TW": "尚未儲存的變更", "zh_CN": "未保存的更改"},
    "Import Media": {"zh_TW": "匯入媒體", "zh_CN": "导入媒体"},
    "Media": {"zh_TW": "媒體", "zh_CN": "媒体"},
    "All files": {"zh_TW": "所有檔案", "zh_CN": "所有文件"},
    "Save": {"zh_TW": "儲存", "zh_CN": "保存"},
    "Saved {path}": {"zh_TW": "已儲存 {path}", "zh_CN": "已保存 {path}"},
    "Removed {name}": {"zh_TW": "已移除 {name}", "zh_CN": "已移除 {name}"},
    "Added {name} at {pos}s": {"zh_TW": "已加入 {name}（{pos} 秒處）", "zh_CN": "已添加 {name}（{pos} 秒处）"},
    "Ready — import media and drag onto the timeline": {
        "zh_TW": "就緒 — 匯入媒體並拖到時間軸上", "zh_CN": "就绪 — 导入媒体并拖到时间轴上"},
    "Project changed": {"zh_TW": "專案已變更", "zh_CN": "项目已变更"},
    "Added video track": {"zh_TW": "已新增視訊軌道", "zh_CN": "已添加视频轨道"},
    "Added audio track": {"zh_TW": "已新增音訊軌道", "zh_CN": "已添加音频轨道"},
    "Open Project": {"zh_TW": "開啟專案", "zh_CN": "打开项目"},
    "Could not open project:\n{err}": {"zh_TW": "無法開啟專案：\n{err}", "zh_CN": "无法打开项目：\n{err}"},
    "Save Project": {"zh_TW": "儲存專案", "zh_CN": "保存项目"},
    "Save changes to the project before exiting?": {
        "zh_TW": "結束前要儲存專案的變更嗎？", "zh_CN": "退出前是否保存项目的更改？"},
    "Discard": {"zh_TW": "不儲存", "zh_CN": "不保存"},
    "About text": {
        "zh_TW": ("以 Python + Qt6 打造之專業非線性影片剪輯軟體。\n"
                  "多軌道時間軸、影格精準播放、復原/重做，以及 ffmpeg 匯出。\n\n"
                  "快捷鍵：Space 播放、I/O 起終點、Ctrl+B 剪斷、R 適度顯示、"
                  "Ctrl+Z/Y 復原/重做。"),
        "zh_CN": ("使用 Python + Qt6 打造的专业非线性视频剪辑软件。\n"
                  "多轨道时间轴、帧精准播放、撤销/重做，以及基于 ffmpeg 的导出。\n\n"
                  "快捷键：Space 播放、I/O 入出点、Ctrl+B 剪切、R 适配显示、"
                  "Ctrl+Z/Y 撤销/重做。")},
    # ---- transitions ----
    "Transitions": {"zh_TW": "轉場特效", "zh_CN": "转场特效"},
    "Transitions Library": {"zh_TW": "轉場特效庫", "zh_CN": "转场特效库"},
    "Apply to Selected Clip": {"zh_TW": "套用至選取的片段", "zh_CN": "应用到所选片段"},
    "Fade / Crossfade": {"zh_TW": "交叉淡入淡出", "zh_CN": "交叉淡入淡出"},
    "Fade to Black": {"zh_TW": "黑場淡入淡出", "zh_CN": "黑场淡入淡出"},
    "Fade to White": {"zh_TW": "白場淡入淡出", "zh_CN": "白场淡入淡出"},
    "Wipe Right": {"zh_TW": "向右擦除", "zh_CN": "向右擦除"},
    "Wipe Left": {"zh_TW": "向左擦除", "zh_CN": "向左擦除"},
    "Wipe Up": {"zh_TW": "向上擦除", "zh_CN": "向上擦除"},
    "Wipe Down": {"zh_TW": "向下擦除", "zh_CN": "向下擦除"},
    "Slide Right": {"zh_TW": "向右滑動", "zh_CN": "向右滑动"},
    "Slide Left": {"zh_TW": "向左滑動", "zh_CN": "向左滑动"},
    "Slide Up": {"zh_TW": "向上滑動", "zh_CN": "向上滑动"},
    "Slide Down": {"zh_TW": "向下滑動", "zh_CN": "向下滑动"},
    "Zoom In": {"zh_TW": "鏡頭縮放 (Zoom)", "zh_CN": "镜头缩放 (Zoom)"},
    "Circle Crop": {"zh_TW": "圓形揭開", "zh_CN": "圆形揭开"},
    "Fade In (Entry)": {"zh_TW": "開頭轉場 (淡入)", "zh_CN": "开头转场 (淡入)"},
    "Fade Out (Exit)": {"zh_TW": "結尾轉場 (淡出)", "zh_CN": "结尾转场 (淡出)"},
    "Transition Type": {"zh_TW": "轉場類型", "zh_CN": "转场类型"},
    "Transition Duration (s)": {"zh_TW": "轉場時長 (秒)", "zh_CN": "转场时长 (秒)"},
    "Applied {name} transition": {"zh_TW": "已套用 {name} 轉場特效", "zh_CN": "已应用 {name} 转场特效"},
    "Select a clip on the timeline first.": {"zh_TW": "請先在時間軸選取片段。", "zh_CN": "请先在时间轴上选择片段。"},

    # ---- subtitles ----
    "Subtitles": {"zh_TW": "字幕工具", "zh_CN": "字幕工具"},
    "Subtitle Editor": {"zh_TW": "字幕編輯器", "zh_CN": "字幕编辑器"},
    "Add Subtitle": {"zh_TW": "新增字幕", "zh_CN": "添加字幕"},
    "Add Subtitle at Playhead": {"zh_TW": "+ 在播放頭處新增字幕", "zh_CN": "+ 在播放头处添加字幕"},
    "Delete Subtitle": {"zh_TW": "刪除字幕", "zh_CN": "删除字幕"},
    "Edit Subtitle Text": {"zh_TW": "編輯字幕文字內容", "zh_CN": "编辑字幕文本内容"},
    "Edit Subtitle Text…": {"zh_TW": "編輯字幕文字…", "zh_CN": "编辑字幕文本…"},
    "Enter subtitle text content:": {"zh_TW": "請輸入字幕文字內容：", "zh_CN": "请输入字幕文本内容："},
    "Edit Selected Subtitle Text": {"zh_TW": "編輯選取字幕內容", "zh_CN": "编辑所选字幕内容"},
    "Select a subtitle from the list to edit its text...": {"zh_TW": "在列表中點選字幕即可編輯文字內容...", "zh_CN": "在列表中点选字幕即可编辑文本内容..."},
    "Edit Template Text": {"zh_TW": "編輯樣板文字內容", "zh_CN": "编辑模板文本内容"},
    "Enter custom text content for this template:": {"zh_TW": "請輸入要套用的樣板文字內容：", "zh_CN": "请输入要套用的模板文本内容："},
    "Import SRT…": {"zh_TW": "匯入 SRT 字幕…", "zh_CN": "导入 SRT 字幕…"},
    "Export SRT…": {"zh_TW": "匯出 SRT 字幕…", "zh_CN": "导出 SRT 字幕…"},
    "Subtitle Text": {"zh_TW": "字幕內容", "zh_CN": "字幕内容"},
    "Font Family": {"zh_TW": "字型名稱", "zh_CN": "字体名称"},
    "Font Size": {"zh_TW": "字號大小", "zh_CN": "字号大小"},
    "Font Color": {"zh_TW": "文字顏色", "zh_CN": "文字颜色"},
    "Background": {"zh_TW": "底框顏色", "zh_CN": "底框颜色"},
    "Outline": {"zh_TW": "描邊顏色", "zh_CN": "描边颜色"},
    "Outline Width": {"zh_TW": "描邊粗細", "zh_CN": "描边粗细"},
    "Alignment": {"zh_TW": "對齊位置", "zh_CN": "对齐位置"},
    "Bottom Center": {"zh_TW": "底部居中", "zh_CN": "底部居中"},
    "Top Center": {"zh_TW": "頂部居中", "zh_CN": "顶部居中"},
    "Center": {"zh_TW": "中央", "zh_CN": "中央"},
    "Bottom Left": {"zh_TW": "左下角", "zh_CN": "左下角"},
    "Bottom Right": {"zh_TW": "右下角", "zh_CN": "右下角"},
    "Type subtitle text here...": {"zh_TW": "請在此輸入字幕文字...", "zh_CN": "请在此输入字幕文字..."},
    "Import SRT Subtitles": {"zh_TW": "匯入 SRT 字幕檔", "zh_CN": "导入 SRT 字幕文件"},
    "Export SRT Subtitles": {"zh_TW": "匯出 SRT 字幕檔", "zh_CN": "导出 SRT 字幕文件"},
    "SRT Subtitle Files (*.srt)": {"zh_TW": "SRT 字幕檔 (*.srt)", "zh_CN": "SRT 字幕文件 (*.srt)"},
    "Imported {count} subtitles.": {"zh_TW": "成功匯入 {count} 條字幕。", "zh_CN": "成功导入 {count} 条字幕。"},
    "Exported subtitles to {path}": {"zh_TW": "字幕已成功匯出至 {path}", "zh_CN": "字幕已成功导出至 {path}"},
    "Text Animation": {"zh_TW": "文字/字幕特效", "zh_CN": "文字/字幕特效"},
    "Animation Effect": {"zh_TW": "特效效果", "zh_CN": "特效效果"},
    "Effect Duration (s)": {"zh_TW": "特效時長 (秒)", "zh_CN": "特效时长 (秒)"},
    "None": {"zh_TW": "無特效", "zh_CN": "无特效"},
    "Fly-In / Fly-Out": {"zh_TW": "飛入/飛出", "zh_CN": "飞入/飞出"},
    "Fade In / Fade Out": {"zh_TW": "淡化 (淡入/淡出)", "zh_CN": "淡化 (淡入/淡出)"},
    "Typewriter": {"zh_TW": "打字機效果", "zh_CN": "打字机效果"},

    # ---- Preset Title & Animation Templates ----
    "Preset Title & Animation Templates": {"zh_TW": "預設標題與片頭片尾動畫模板", "zh_CN": "预设标题与片头片尾动画模板"},
    "Category Filter:": {"zh_TW": "分類篩選：", "zh_CN": "分类筛选："},
    "All Templates": {"zh_TW": "全部模板", "zh_CN": "全部模板"},
    "🎬 Intro Animations": {"zh_TW": "🎬 開場片頭動畫", "zh_CN": "🎬 开场片头动画"},
    "🔚 Outro Animations": {"zh_TW": "🔚 結尾片尾動畫", "zh_CN": "🔚 结尾片尾动画"},
    "📝 Title & Text": {"zh_TW": "📝 標題與文字", "zh_CN": "📝 标题与文字"},
    "⭐ Custom & Imported": {"zh_TW": "⭐ 自訂與匯入模板", "zh_CN": "⭐ 自定义与导入模板"},
    "+ Add Template to Timeline": {"zh_TW": "+ 新增模板至時間軸", "zh_CN": "+ 添加模板至时间轴"},
    "💾 Save Selected as Template": {"zh_TW": "💾 存為自訂模板", "zh_CN": "💾 存为自定义模板"},
    "📥 Import JSON": {"zh_TW": "📥 匯入 JSON 模板", "zh_CN": "📥 导入 JSON 模板"},
    "📤 Export JSON": {"zh_TW": "📤 匯出 JSON 模板", "zh_CN": "📤 导出 JSON 模板"},
    "Save Custom Template": {"zh_TW": "儲存自訂模板", "zh_CN": "保存自定义模板"},
    "Enter custom template name:": {"zh_TW": "請輸入自訂模板名稱：", "zh_CN": "请输入自定义模板名称："},
    "Please select a subtitle on the timeline to save as template.": {"zh_TW": "請先在時間軸選取要儲存為模板的字幕。", "zh_CN": "请先在时间轴上选择要保存为模板的字幕。"},
    "Custom template saved successfully!": {"zh_TW": "自訂模板已成功儲存！", "zh_CN": "自定义模板已成功保存！"},
    "Import Template JSON": {"zh_TW": "匯入 JSON 模板檔", "zh_CN": "导入 JSON 模板文件"},
    "Export Templates": {"zh_TW": "匯出 JSON 模板檔", "zh_CN": "导出 JSON 模板文件"},
    "Successfully imported": {"zh_TW": "已成功匯入", "zh_CN": "已成功导入"},
    "templates!": {"zh_TW": "個模板！", "zh_CN": "个模板！"},
    "Successfully exported": {"zh_TW": "已成功匯出", "zh_CN": "已成功导出"},
    "Failed to import JSON file": {"zh_TW": "匯入 JSON 檔案失敗", "zh_CN": "导入 JSON 文件失败"},
    "Failed to export templates": {"zh_TW": "匯出模板失敗", "zh_CN": "导出模板失败"},
    "No valid template objects found in JSON file.": {"zh_TW": "JSON 檔案中找不到有效的模板物件。", "zh_CN": "JSON 文件中找不到有效的模板对象。"},
    "No custom templates to export.": {"zh_TW": "目前沒有自訂模板可供匯出。", "zh_CN": "目前没有自定义模板可供导出。"},

    # ---- Intros & Outros ----
    "Vlog Studio Opening": {"zh_TW": "Vlog 酷炫開場片頭", "zh_CN": "Vlog 酷炫开场片头"},
    "Cool opening title banner for Vlog episodes": {"zh_TW": "鮮黃色經典大標題 ＋ 飛入特效，適合 Vlog 酷炫開場", "zh_CN": "鲜黄色经典大标题 ＋ 飞入特效，适合 Vlog 酷炫开场"},
    "Cyber Gaming Intro": {"zh_TW": "賽博電競極速開場片頭", "zh_CN": "赛博电竞极速开场片头"},
    "High-tech neon typewriter intro for gaming & tech": {"zh_TW": "霓虹青藍打字機特效，適合電競、遊戲與科技頻道開場", "zh_CN": "霓虹青蓝打字机特效，适合电竞、游戏与科技频道开场"},
    "Cinematic Movie Opening": {"zh_TW": "電影大片震撼開場片頭", "zh_CN": "电影大片震撼开场片头"},
    "Dramatic golden-white title for films & trailers": {"zh_TW": "黑金白字搭配平滑淡入淡出，營造電影大片震撼片頭", "zh_CN": "黑金白字搭配平滑淡入淡出，营造电影大片震撼片头"},
    "Tech Keynote Intro": {"zh_TW": "科技發佈會簡約片頭", "zh_CN": "科技发布会简约片头"},
    "Clean white card intro for announcements & tutorials": {"zh_TW": "純白質感小卡與打字機效果，適合發佈會與教學開場", "zh_CN": "纯白质感小卡与打字机效果，适合发布会与教学开场"},
    "Like & Subscribe Outro": {"zh_TW": "訂閱按讚片尾結尾", "zh_CN": "订阅按赞片尾结尾"},
    "Vibrant red banner for channel end credits": {"zh_TW": "鮮紅卡片橫條飛入，提醒觀眾按讚訂閱與分享片尾", "zh_CN": "鲜红卡片横条飞入，提醒观众按赞订阅与分享片尾"},
    "Next Episode Outro": {"zh_TW": "下集預告與追蹤片尾", "zh_CN": "下集预告与追踪片尾"},
    "Neon blue end card for next episode previews": {"zh_TW": "霓虹青藍打字機結尾，適合下集預告與社群追蹤提示", "zh_CN": "霓虹青蓝打字机结尾，适合下集预告与社群追踪提示"},
    "End Credits Roll": {"zh_TW": "經典謝幕工作人員片尾", "zh_CN": "经典谢幕工作人员片尾"},
    "Classic movie rolling end credits template": {"zh_TW": "經典電影風格柔和謝幕字幕，適合製作人員與感謝名單", "zh_CN": "经典电影风格柔和谢幕字幕，适合制作人员与感谢名单"},

    # ---- Preset Title Templates ----
    "Preset Title Templates": {"zh_TW": "預設標題模板", "zh_CN": "预设标题模板"},
    "Templates": {"zh_TW": "預設模板", "zh_CN": "预设模板"},
    "Click a template to preview or add directly onto timeline.": {"zh_TW": "雙擊或點擊按鈕即可直接套用標題模板至時間軸。", "zh_CN": "双击或点击按钮即可直接套用标题模板至时间轴。"},
    "Template Actions": {"zh_TW": "模板操作", "zh_CN": "模板操作"},
    "+ Add Template at Playhead": {"zh_TW": "+ 在播放頭處新增標題模板", "zh_CN": "+ 在播放头处添加标题模板"},
    "Apply Style to Selected Subtitle": {"zh_TW": "套用模板樣式至選取的字幕", "zh_CN": "套用模板样式至所选字幕"},
    "Please select a subtitle on the timeline first.": {"zh_TW": "請先在時間軸選取一條字幕。", "zh_CN": "请先在时间轴上选择一条字幕。"},
    "Vlog Headline": {"zh_TW": "Vlog 熱門大標題", "zh_CN": "Vlog 热门大标题"},
    "Bright yellow bold banner for Vlog video titles": {"zh_TW": "鮮黃色經典滿版高亮標題條，適合 Vlog 封面與主標題", "zh_CN": "鲜黄色经典满版高亮标题条，适合 Vlog 封面与主标题"},
    "Tech Cyber Title": {"zh_TW": "科技感打字標題", "zh_CN": "科技感打字标题"},
    "Neon cyan typewriter title for tech & gaming": {"zh_TW": "霓虹青藍打字機特效，適合科技開箱與遊戲片頭", "zh_CN": "霓虹青蓝打字机特效，适合科技开箱与游戏片头"},
    "Cinematic Title": {"zh_TW": "電影質感大片標題", "zh_CN": "电影质感大片标题"},
    "Elegant white heading with smooth fade for films": {"zh_TW": "典雅白字搭配平滑淡入淡出，營造電影大片質感", "zh_CN": "典雅白字搭配平滑淡入淡出，营造电影大片质感"},
    "News Lower Third": {"zh_TW": "新聞/訪談下三分之一字幕條", "zh_CN": "新闻/访谈下三分之一字幕条"},
    "Crimson red banner for news & interviews": {"zh_TW": "經典深紅橫條飛入字幕，適合新聞與訪談簡介", "zh_CN": "经典深红横条飞入字幕，适合新闻与访谈简介"},
    "Tutorial Note Card": {"zh_TW": "教學知識型簡約卡片", "zh_CN": "教学知识型简约卡片"},
    "Clean white card for tutorials and knowledge tips": {"zh_TW": "純白質感小卡與打字機效果，適合教學與重點提示", "zh_CN": "纯白质感小卡与打字机效果，适合教学与重点提示"},
    "Vibrant Highlight": {"zh_TW": "極簡爆款重點標籤", "zh_CN": "极简爆款重点标签"},
    "Hot pink bold text for intense highlight clips": {"zh_TW": "桃紅高調文字，適合高潮精華與重點強調", "zh_CN": "桃红高调文字，适合高潮精华与重点强调"},
    "Gold Luxury Heading": {"zh_TW": "金色尊貴標題", "zh_CN": "金色尊贵标题"},
    "Golden upscale title for awards & luxury clips": {"zh_TW": "高貴金色描邊標題，適合頒獎與高級質感影片", "zh_CN": "高贵金色描边标题，适合颁奖与高级质感视频"},
    "Podcast Quote": {"zh_TW": "訪談/Podcast 金句框", "zh_CN": "访谈/Podcast 金句框"},
    "Subtle grey card quote for podcasts & talk shows": {"zh_TW": "深灰卡片質感底框，適合 Podcast 與訪談節目金句", "zh_CN": "深灰卡片质感底框，适合 Podcast 與訪談節目金句"},

    # ---- Object Removal & Content-Aware Fill ----
    "Object Removal & Content-Aware Fill": {"zh_TW": "🪄 魔法筆物件與浮水印移除 (Object Removal)", "zh_CN": "🪄 魔法笔物件与水印移除 (Object Removal)"},
    "Enable Object Removal": {"zh_TW": "啟用物件/浮水印移除", "zh_CN": "启用物件/水印移除"},
    "🪄 Activate Magic Eraser": {"zh_TW": "🪄 開啟魔法筆塗抹畫刷", "zh_CN": "🪄 开启魔法笔涂抹画刷"},
    "🧹 Clear Masks": {"zh_TW": "🧹 清除所有塗抹遮罩", "zh_CN": "🧹 清除所有涂抹遮罩"},
    "Brush Radius": {"zh_TW": "畫筆粗細", "zh_CN": "画笔粗细"},
    "masks applied": {"zh_TW": "個塗抹遮罩", "zh_CN": "个涂抹遮罩"},
    "🎯 Auto-Track Motion": {"zh_TW": "🎯 AI 自動物件運動追蹤", "zh_CN": "🎯 AI 自动物件运动追踪"},
    "Magic Eraser Active": {"zh_TW": "🪄 魔法筆塗抹模式中", "zh_CN": "🪄 魔法笔涂抹模式中"},
    "masks": {"zh_TW": "遮罩", "zh_CN": "遮罩"},
    "AI Auto Subtitling": {"zh_TW": "✨ AI 語音辨識自動上字幕", "zh_CN": "✨ AI 语音识别自动上字幕"},
    "Recognize & Generate Subtitles": {"zh_TW": "✨ 開始自動語音辨識上字幕", "zh_CN": "✨ 开始自动语音识别上字幕"},
    "AI Model:": {"zh_TW": "AI 模型：", "zh_CN": "AI 模型："},
    "base (Recommended)": {"zh_TW": "base (推薦，平衡)", "zh_CN": "base (推荐，平衡)"},
    "tiny (Fastest)": {"zh_TW": "tiny (超快速)", "zh_CN": "tiny (超快速)"},
    "small (High Accuracy)": {"zh_TW": "small (高精準度)", "zh_CN": "small (高精确度)"},
    "Language:": {"zh_TW": "識別語言：", "zh_CN": "识别语言："},
    "Auto Detect": {"zh_TW": "自動識別", "zh_CN": "自动识别"},
    "Chinese (zh)": {"zh_TW": "中文 (zh)", "zh_CN": "中文 (zh)"},
    "English (en)": {"zh_TW": "英文 (en)", "zh_CN": "英文 (en)"},
    "Japanese (ja)": {"zh_TW": "日文 (ja)", "zh_CN": "日文 (ja)"},
    "Korean (ko)": {"zh_TW": "韓文 (ko)", "zh_CN": "韩文 (ko)"},
    "Speech Recognition Failed": {"zh_TW": "語音辨識失敗", "zh_CN": "语音识别失败"},
    "Speech Recognition Progress": {"zh_TW": "語音辨識中", "zh_CN": "语音识别中"},

    # ---- Chroma Key ----
    "Chroma Key (Green Screen)": {"zh_TW": "Chroma Key 綠幕去背", "zh_CN": "Chroma Key 绿幕去背"},
    "Enable Chroma Key": {"zh_TW": "啟用綠幕去背", "zh_CN": "启用绿幕去背"},
    "Key Color": {"zh_TW": "去背顏色", "zh_CN": "去背颜色"},
    "Green": {"zh_TW": "綠幕", "zh_CN": "绿幕"},
    "Blue": {"zh_TW": "藍幕", "zh_CN": "蓝幕"},
    "Similarity": {"zh_TW": "相似度容差", "zh_CN": "相似度容差"},
    "Smoothness": {"zh_TW": "邊緣平滑度", "zh_CN": "边缘平滑度"},
    "Chroma Key Enabled": {"zh_TW": "已開啟綠幕去背", "zh_CN": "已开启绿幕去背"},
    "Applying Chroma Key...": {"zh_TW": "正在套用綠幕去背...", "zh_CN": "正在套用绿幕去背..."},

    # ---- Preset Video Effects & Adjustments ----
    "Preset Effects": {"zh_TW": "視覺與濾鏡特效", "zh_CN": "视觉与滤镜特效"},
    "Effects": {"zh_TW": "特效", "zh_CN": "特效"},
    "Video Effect": {"zh_TW": "濾鏡調色", "zh_CN": "滤镜调色"},
    "Select a video clip on timeline and click an effect to apply.": {"zh_TW": "請點選時間軸上的影片片段，然後點擊特效套用。", "zh_CN": "请点选时间轴上的视频片段，然后点击特效套用。"},
    "Please select a video clip on the timeline first.": {"zh_TW": "請先在時間軸上選擇影片片段。", "zh_CN": "请先在时间轴上选择视频片段。"},
    "Original": {"zh_TW": "無特效 (原圖)", "zh_CN": "无特效 (原图)"},
    "Explosion Burst": {"zh_TW": "💥 爆炸衝擊波", "zh_CN": "💥 爆炸冲击波"},
    "Camera Flash": {"zh_TW": "⚡ 強光閃光相機", "zh_CN": "⚡ 强光闪光相机"},
    "Gold Sparkles": {"zh_TW": "✨ 金燦星光粒子", "zh_CN": "✨ 金灿星光粒子"},
    "Cyber Particles": {"zh_TW": "🌌 賽博霓光粒子", "zh_CN": "🌌 赛博霓光粒子"},
    "Warm Film": {"zh_TW": "暖陽電影調", "zh_CN": "暖阳电影调"},
    "Cool Cyberpunk": {"zh_TW": "冷藍賽博調", "zh_CN": "冷蓝赛博调"},
    "Teal & Orange": {"zh_TW": "青橙大片調", "zh_CN": "青橙大片调"},
    "Grayscale": {"zh_TW": "經典黑白", "zh_CN": "经典黑白"},
    "Sepia Vintage": {"zh_TW": "復古懷舊", "zh_CN": "复古怀旧"},
    "Color Invert": {"zh_TW": "負片反轉", "zh_CN": "负片反转"},
    "Vivid Boost": {"zh_TW": "高對比鮮豔", "zh_CN": "高对比鲜艳"},
    "Soft Blur": {"zh_TW": "柔焦模糊", "zh_CN": "柔焦模糊"},
    "Center Focus": {"zh_TW": "中心聚焦 (景深)", "zh_CN": "中心聚焦 (景深)"},
    "Tilt Shift Focus": {"zh_TW": "移軸聚焦 (微縮)", "zh_CN": "移轴聚焦 (微缩)"},
    "Horizontal Mirror": {"zh_TW": "水平鏡像", "zh_CN": "水平镜像"},
    "Cinema Vignette": {"zh_TW": "電影暗角", "zh_CN": "电影暗角"},

    # ---- Visual FX Controls ----
    "Playback Speed (Slow/Fast Motion)": {"zh_TW": "⚡ 播放速度 (慢動作 / 快動作)", "zh_CN": "⚡ 播放速度 (慢动作 / 快动作)"},
    "Speed Multiplier": {"zh_TW": "速度倍率", "zh_CN": "速度倍率"},
    "Color Correction & Grading": {"zh_TW": "🎨 色彩校正與分級 (Color Grading)", "zh_CN": "🎨 色彩校正与分级 (Color Grading)"},
    "Brightness": {"zh_TW": "亮度", "zh_CN": "亮度"},
    "Contrast": {"zh_TW": "對比度", "zh_CN": "对比度"},
    "Saturation": {"zh_TW": "飽和度", "zh_CN": "饱和度"},
    "Blur & Focus Effects": {"zh_TW": "🔍 模糊與聚焦 (Blur & Focus)", "zh_CN": "🔍 模糊与聚焦 (Blur & Focus)"},
    "Focus Mode": {"zh_TW": "聚焦/模糊模式", "zh_CN": "聚焦/模糊模式"},
    "Gaussian Blur": {"zh_TW": "高斯/全圖模糊", "zh_CN": "高斯/全图模糊"},
    # ---- Preset Title Templates ----
    "Preset Title Templates": {"zh_TW": "預設標題模板", "zh_CN": "预设标题模板"},
    "Templates": {"zh_TW": "預設模板", "zh_CN": "预设模板"},
    "Click a template to preview or add directly onto timeline.": {"zh_TW": "雙擊或點擊按鈕即可直接套用標題模板至時間軸。", "zh_CN": "双击或点击按钮即可直接套用标题模板至时间轴。"},
    "Template Actions": {"zh_TW": "模板操作", "zh_CN": "模板操作"},
    "+ Add Template at Playhead": {"zh_TW": "+ 在播放頭處新增標題模板", "zh_CN": "+ 在播放头处添加标题模板"},
    "Apply Style to Selected Subtitle": {"zh_TW": "套用模板樣式至選取的字幕", "zh_CN": "套用模板样式至所选字幕"},
    "Please select a subtitle on the timeline first.": {"zh_TW": "請先在時間軸選取一條字幕。", "zh_CN": "请先在时间轴上选择一条字幕。"},
    "Vlog Headline": {"zh_TW": "Vlog 熱門大標題", "zh_CN": "Vlog 热门大标题"},
    "Bright yellow bold banner for Vlog video titles": {"zh_TW": "鮮黃色經典滿版高亮標題條，適合 Vlog 封面與主標題", "zh_CN": "鲜黄色经典满版高亮标题条，适合 Vlog 封面与主标题"},
    "Tech Cyber Title": {"zh_TW": "科技感打字標題", "zh_CN": "科技感打字标题"},
    "Neon cyan typewriter title for tech & gaming": {"zh_TW": "霓虹青藍打字機特效，適合科技開箱與遊戲片頭", "zh_CN": "霓虹青蓝打字机特效，适合科技开箱与游戏片头"},
    "Cinematic Title": {"zh_TW": "電影質感大片標題", "zh_CN": "电影质感大片标题"},
    "Elegant white heading with smooth fade for films": {"zh_TW": "典雅白字搭配平滑淡入淡出，營造電影大片質感", "zh_CN": "典雅白字搭配平滑淡入淡出，营造电影大片质感"},
    "News Lower Third": {"zh_TW": "新聞/訪談下三分之一字幕條", "zh_CN": "新闻/访谈下三分之一字幕条"},
    "Crimson red banner for news & interviews": {"zh_TW": "經典深紅橫條飛入字幕，適合新聞與訪談簡介", "zh_CN": "经典深红横条飞入字幕，适合新闻与访谈简介"},
    "Tutorial Note Card": {"zh_TW": "教學知識型簡約卡片", "zh_CN": "教学知识型简约卡片"},
    "Clean white card for tutorials and knowledge tips": {"zh_TW": "純白質感小卡與打字機效果，適合教學與重點提示", "zh_CN": "纯白质感小卡与打字机效果，适合教学与重点提示"},
    "Vibrant Highlight": {"zh_TW": "極簡爆款重點標籤", "zh_CN": "极简爆款重点标签"},
    "Hot pink bold text for intense highlight clips": {"zh_TW": "桃紅高調文字，適合高潮精華與重點強調", "zh_CN": "桃红高调文字，适合高潮精华与重点强调"},
    "Gold Luxury Heading": {"zh_TW": "金色尊貴標題", "zh_CN": "金色尊贵标题"},
    "Golden upscale title for awards & luxury clips": {"zh_TW": "高貴金色描邊標題，適合頒獎與高級質感影片", "zh_CN": "高贵金色描边标题，适合颁奖与高级质感视频"},
    "Podcast Quote": {"zh_TW": "訪談/Podcast 金句框", "zh_CN": "访谈/Podcast 金句框"},
    "Subtle grey card quote for podcasts & talk shows": {"zh_TW": "深灰卡片質感底框，適合 Podcast 與訪談節目金句", "zh_CN": "深灰卡片质感底框，适合 Podcast 与访谈节目金句"},

    # ---- Picture-in-Picture (PiP / 子母畫面) ----
    "Picture-in-Picture & Layout": {"zh_TW": "子母畫面與版面排列", "zh_CN": "画中画与版面排列"},
    "PiP Layout": {"zh_TW": "子母畫面", "zh_CN": "子母画面"},
    "Toggle Picture-in-Picture Interactive Edit Mode": {
        "zh_TW": "開啟/關閉「子母畫面互動調整」：可直接在預覽畫面拖曳調整母畫面與子畫面的大小及位置",
        "zh_CN": "开启/关闭「子母画面互动调整」：可直接在预览画面拖动调整母画面与子画面的大小及位置",
    },
    "Swap PiP": {"zh_TW": "子母互換", "zh_CN": "子母互换"},
    "Swap Main Screen and Sub Screen": {"zh_TW": "子母畫面互換 (對調母畫面與子畫面的位置與圖層)", "zh_CN": "子母画面互换 (对调母画面与子画面的位置与图层)"},
    "Swap Main and Sub Screens": {"zh_TW": "子母畫面互換", "zh_CN": "子母画面互换"},
    "Swapped Main Screen and Sub Screen": {"zh_TW": "已互換母畫面與子畫面的大小與排列位置", "zh_CN": "已互换母画面与子画面的大小与排列位置"},
    "Place at least two video clips (e.g. on V1 and V2) at the playhead to swap Main and Sub screens.": {
        "zh_TW": "請在播放頭處放置至少兩個視訊片段（例如 V1 母畫面與 V2 子畫面），即可一鍵互換子母畫面。",
        "zh_CN": "请在播放头处放置至少两个视频片段（例如 V1 母画面与 V2 子画面），即可一键互换子母画面。",
    },
    "Add as Sub Screen": {"zh_TW": "加入為子畫面", "zh_CN": "添加为子画面"},
    "Add as Sub Screen (V2 PiP)": {"zh_TW": "加入為子畫面 (V2 子母畫面)", "zh_CN": "添加为子画面 (V2 子母画面)"},
    "Add selected media as Picture-in-Picture sub screen (V2)": {
        "zh_TW": "將選取媒體作為子畫面加入上層視訊軌道 (V2)",
        "zh_CN": "将所选媒体作为子画面加入上层视频轨道 (V2)",
    },
    "Added {name} as Sub Screen (PiP) at {pos}s": {
        "zh_TW": "已將 {name} 加入為子畫面（{pos} 秒處）",
        "zh_CN": "已将 {name} 添加为子画面（{pos} 秒处）",
    },
    "Main Screen": {"zh_TW": "母畫面", "zh_CN": "母画面"},
    "Sub Screen": {"zh_TW": "子畫面", "zh_CN": "子画面"},
    "Sub": {"zh_TW": "子畫面", "zh_CN": "子画面"},
    "Current Target": {"zh_TW": "目前編輯對象", "zh_CN": "当前编辑对象"},
    "Select Main (V1)": {"zh_TW": "選取母畫面 (V1)", "zh_CN": "选取母画面 (V1)"},
    "Select Sub (V2)": {"zh_TW": "選取子畫面 (V2)", "zh_CN": "选取子画面 (V2)"},
    "Set as Sub Screen": {"zh_TW": "設為子畫面", "zh_CN": "设为子画面"},
    "Set as Sub Screen (PiP)": {"zh_TW": "設為子畫面 (移至上層軌道)", "zh_CN": "设为子画面 (移至上层轨道)"},
    "Set as Main Screen": {"zh_TW": "設為母畫面", "zh_CN": "设为母画面"},
    "Set as Main Screen (V1)": {"zh_TW": "設為母畫面 (移至 V1 底層)", "zh_CN": "设为母画面 (移至 V1 底层)"},
    "Interactive Drag/Resize in Preview": {
        "zh_TW": "在預覽畫面直接拖曳調整大小與位置",
        "zh_CN": "在预览画面直接拖动调整大小与位置",
    },
    "PiP Edit Mode: Drag frame to move, drag corners/edges to resize, click to switch Main/Sub screen": {
        "zh_TW": "子母畫面編輯模式：拖曳畫面可移動位置、拉動邊角可縮放大小、點選畫面可切換母畫面/子畫面",
        "zh_CN": "子母画面编辑模式：拖动画面可移动位置、拉动边角可缩放大小、点选画面可切换母画面/子画面",
    },
    "Layout Preset": {"zh_TW": "版面排列預設", "zh_CN": "版面排列预设"},
    "Apply Layout": {"zh_TW": "套用排列", "zh_CN": "套用排列"},
    "Corner PiP: Bottom-Right": {"zh_TW": "右下子畫面 (母全螢幕 + 右下子畫面)", "zh_CN": "右下子画面 (母全屏 + 右下子画面)"},
    "Corner PiP: Bottom-Left": {"zh_TW": "左下子畫面 (母全螢幕 + 左下子畫面)", "zh_CN": "左下子画面 (母全屏 + 左下子画面)"},
    "Corner PiP: Top-Right": {"zh_TW": "右上子畫面 (母全螢幕 + 右上子畫面)", "zh_CN": "右上子画面 (母全屏 + 右上子画面)"},
    "Corner PiP: Top-Left": {"zh_TW": "左上子畫面 (母全螢幕 + 左上子畫面)", "zh_CN": "左上子画面 (母全屏 + 左上子画面)"},
    "Side by Side 50/50 (Main Left / Sub Right)": {"zh_TW": "左右並排 50/50 (左母畫面 / 右子畫面)", "zh_CN": "左右并排 50/50 (左母画面 / 右子画面)"},
    "Side by Side 50/50 (Sub Left / Main Right)": {"zh_TW": "左右並排 50/50 (左子畫面 / 右母畫面)", "zh_CN": "左右并排 50/50 (左子画面 / 右母画面)"},
    "Left Main 70% + Right Sub 30%": {"zh_TW": "左大右小 70/30 (左母 70% + 右子 30%)", "zh_CN": "左大右小 70/30 (左母 70% + 右子 30%)"},
    "Left Sub 30% + Right Main 70%": {"zh_TW": "右大左小 30/70 (左子 30% + 右母 70%)", "zh_CN": "右大左小 30/70 (左子 30% + 右母 70%)"},
    "Top & Bottom Split 50/50": {"zh_TW": "上下並排 50/50 (上母畫面 / 下子畫面)", "zh_CN": "上下并排 50/50 (上母画面 / 下子画面)"},
    "Floating Dual Windows": {"zh_TW": "雙視窗交錯排列 (左上母畫面 + 右下子畫面)", "zh_CN": "双窗口交错排列 (左上母画面 + 右下子画面)"},
    "Reset Full Screen (100%)": {"zh_TW": "恢復全螢幕 (100%)", "zh_CN": "恢复全屏 (100%)"},
    "Uniform Scale (%)": {"zh_TW": "等比例縮放 (%)", "zh_CN": "等比例缩放 (%)"},
    "Width (%)": {"zh_TW": "寬度 (%)", "zh_CN": "宽度 (%)"},
    "Height (%)": {"zh_TW": "高度 (%)", "zh_CN": "高度 (%)"},
    "Position X (%)": {"zh_TW": "水平位置 X (%)", "zh_CN": "水平位置 X (%)"},
    "Position Y (%)": {"zh_TW": "垂直位置 Y (%)", "zh_CN": "垂直位置 Y (%)"},
    "Quick Position": {"zh_TW": "九宮格快速對齊", "zh_CN": "九宫格快速对齐"},
    "Border": {"zh_TW": "外框粗細與顏色", "zh_CN": "边框粗细与颜色"},
    "Border Color": {"zh_TW": "外框顏色", "zh_CN": "边框颜色"},
}


def tr(text: str) -> str:
    """Translate an English source string to the current UI language."""
    if _current == "en":
        return text
    entry = _TRANSLATIONS.get(text)
    if entry is None:
        return text
    return entry.get(_current, text)


def subscribe(callback) -> None:
    _callbacks.append(callback)


def set_language(lang: str) -> None:
    global _current
    if lang not in LANGUAGES:
        return
    _current = lang
    for cb in _callbacks:
        try:
            cb()
        except Exception:
            pass


def current_language() -> str:
    return _current