# 更新记录 / Changelog

## 2.0.3 — 2026-10-17

### 简体中文

帧渡 ZhenDu **2.0.3**：处理完成后，直接复制、打开与预览视频。

- 队列结束后，“取消任务”变成 **“复制文件”**，一次复制当前队列全部成功视频，包括分割片段，可直接在资源管理器或支持文件粘贴的程序中粘贴。
- 任务展开输出文件列表，支持选中某个视频、Ctrl／Shift 多选、右键菜单和 Ctrl+C；父子同时选择自动去重。
- 新增 **“打开视频”** 调用默认播放器，以及 **“预览”** 在程序内播放成品，支持声音、定位与放大。选中多个文件时可指定其中一个打开或预览。
- 成品预览保留原素材的处理设置和截取时间；点击左侧素材即可返回。预览区域更紧凑，为结果列表留出空间。
- 修复退出放大后立刻暂停可能出现的预览空白，保留最后一帧。
- 新任务恢复取消按钮；文件已移动或删除时给出提示。简体中文与 English 同步更新。


### English

ZhenDu **2.0.3** adds direct file copying, opening and previewing after processing.

- When the queue finishes, Cancel tasks becomes **Copy files**, copying all successful videos in the queue, including split parts, for pasting in File Explorer or supported applications.
- Completed tasks expand into output files. Select individual parts or Ctrl/Shift selections, use context commands or Ctrl+C. Parent/child selections are deduplicated.
- **Open video** uses the default system player; **Preview** plays results inside ZhenDu with audio, seeking and expanded controls. Choose a specific file from multiple selections.
- Result preview preserves source settings and trim times; click the left source list to return. A more compact preview gives output rows more space.
- Keep the last preview frame when pausing immediately after leaving expanded view.
- New jobs restore Cancel tasks. Moved/deleted files produce a clear message. English and Simplified Chinese are updated together.


## 2.0.2 — 2026-10-17

### 简体中文

- 新增“为每个任务创建子文件夹”设置，默认关闭，包括从旧配置升级。
- 关闭时视频直接保存到所选目录；未选择目录时保存在原视频旁。开启时恢复原有任务文件夹结构。
- 直接输出使用 `_ZhenDu` 后缀，重名自动编号，不覆盖源文件或已有输出；分割视频直接生成带段号的多个文件。
- 直接输出的任务记录移到设置目录，不在视频旁生成 JSON；失败或取消清理临时输出。
- 输出方式随任务入队保存，排队中切换设置不改变既有任务。

### English

- Add **Create a subfolder for each task**, off by default, including upgrades from older settings.
- Save videos directly into the selected directory, or beside the source if none is selected. Enable the setting to retain the previous task-folder layout.
- Use `_ZhenDu` and automatic numeric suffixes to preserve source/existing files. Split parts are saved directly as numbered videos.
- Keep direct-mode task records in the settings directory, leaving no JSON files beside videos. Failed/cancelled jobs clean up temporary outputs.
- Snapshot the output mode when queuing each task.

## 2.0.0 — 2026-10-16

### 简体中文

首次公开发布 PySide6 重构版本，包含此前本机验证的修复。

- 以三栏界面组织素材、预览和处理参数；输出与任务按钮保持可见。
- 使用 Qt Multimedia 提供有声预览，修复切换素材、暂停定位和 A/B 范围重置。
- 放大预览按比例居中，保留进度、时间、播放、声音与 A/B 控制；支持按钮、Esc、F11、双击退出。
- 压缩、截取和分割可组合，先截取再分割；关闭编码后复制视频流。
- 支持自定义预设、导入／导出和可撤销的当前用户级联右键菜单。
- 简体中文／English／自动选择语言；界面与原生窗口标题栏使用深色。
- 统一隐藏 FFmpeg 子进程控制台；后台探测和任务队列减少界面阻塞。
- 提供完整双语 README、GPL-3.0 许可证、固定依赖获取与 GitHub 发布构建。

### English

First public release of the PySide6 rewrite, including fixes validated during local development.

- Three-column layout for sources, preview and processing; output/task controls stay visible.
- Qt Multimedia audio/video preview with source-switching, paused-seeking and range-reset fixes.
- Centered expanded preview with timeline, time, playback, audio and A/B controls; button, Esc, F11 and double-click exits.
- Combine compression, trimming and splitting; trim before splitting and stream-copy video when encoding is disabled.
- Custom/importable/exportable presets and a removable per-user cascading Explorer menu.
- Simplified Chinese, English and automatic language selection; dark UI and native title bars.
- Hidden FFmpeg consoles, background probing and queued processing.
- Complete bilingual documentation, GPL-3.0 license, pinned dependency fetching and GitHub release builds.
