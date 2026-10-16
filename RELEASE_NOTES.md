## 简体中文

帧渡 ZhenDu 2.0.0：首次公开发布的 PySide6 视频压缩、截取与分割工具。

### 下载

- **普通用户**：下载 `ZhenDu-2.0.0-windows-x64-portable.zip`，完整解压后运行 `ZhenDu.exe`。同一包支持简体中文和 English，无需 Python。
- **开发者**：`ZhenDu-2.0.0-source.zip` 对应该版本标签；依赖获取和构建方法见 README。
- `SHA256SUMS.txt` 用于下载校验；`BUILD_INFO.json` 记录源码提交、工具链和构建信息。

### 本版功能

有声预览、带持续控制栏的放大预览、A/B 与循环；压缩／截取／分割组合操作；不编码时快速复制视频流；自定义预设及可撤销的级联右键菜单；中英双语和深色原生标题栏。FFmpeg 处理不额外弹出控制台窗口。

### 使用提示与验证范围

请保留 `_internal`、`ffmpeg` 和许可文件。设置中可选择语言、注册或撤销右键菜单；Windows 11 从“显示更多选项”访问。移动程序后重新注册菜单。流复制切割依赖关键帧，精确边界需要编码。硬件编码依赖显卡／驱动，4K/HDR 和所有 GPU 组合未全面测量。本机在 Windows 10 验证有声预览、横竖切换、放大／退出与实际处理；发布工作流另外检查固定提交的处理和最终 EXE 任务。详见仓库验证说明。

## English

ZhenDu 2.0.0 is the first public PySide6 release of this Windows video compressor, trimmer and splitter.

### Downloads

- **Users:** get `ZhenDu-2.0.0-windows-x64-portable.zip`, extract everything, then run `ZhenDu.exe`. The same package supports English and Simplified Chinese; no Python installation is needed.
- **Developers:** `ZhenDu-2.0.0-source.zip` matches the version tag. See the README for dependency setup and building.
- `SHA256SUMS.txt` verifies downloads; `BUILD_INFO.json` records the source commit, toolchain and build information.

### Included

Preview with audio, expanded preview with persistent controls, A/B marking and looping; combined compression/trim/split tasks; fast video stream copy when encoding is off; saved presets and a removable cascading Explorer menu; bilingual UI and dark native title bars. Processing hides FFmpeg console windows.

### Notes and validation

Keep `_internal`, `ffmpeg` and license files. Settings provides language and context-menu registration/removal. Use Show more options on Windows 11; register again after moving the program. Stream-copy cuts follow keyframes; precise boundaries need encoding. Hardware support depends on GPU/driver; not all GPU combinations or 4K/HDR workloads were measured. Local Windows 10 testing covered audio, source changes, portrait/landscape preview, expanded-view entry/exit and actual processing. The release workflow additionally checks processing and packaged tasks for the pinned source commit. See the repository's validation notes.
