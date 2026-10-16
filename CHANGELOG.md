# 更新记录 / Changelog

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
