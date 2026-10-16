# 更新记录 / Changelog

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
