# 验证范围 / Validation scope

## 2.0.1 输出方式 / Output layout

18 项基础／实际输出／隔离注册表测试通过。其中新增 8 项覆盖：默认同目录直接输出、选定目录只留视频、重名与源文件保护、分割直接输出、开启后的原目录结构、取消清理、发布部分失败回滚、旧设置迁移与保存，以及记录写入失败后保留成功视频。Qt 界面与两次预设任务测试验证选项默认关闭、持久保存、两种语言和直接输出无重名覆盖。

18 unit/output/isolated-registry checks passed locally. Eight new tests cover direct output beside the source, clean selected directories, source/existing-file protection, split outputs, the previous folder layout, cancellation, partial-publication rollback, settings migration/persistence and preserving completed videos if history is unwritable. Qt settings and repeated preset-task checks validate the default, persistence, language behavior and collision-free direct output.

## 本机验证 / Local validation

2026-10-12，Windows 10 Pro 22H2 x64，Python 3.14.5，PySide6 6.10.2，PyInstaller 6.22.3。2026-10-16 整理开源发布文档，应用逻辑保留已验证版本。

- 9 项基础测试、1 项独立命名空间的真实 Windows 注册表测试。
- 17 个真实视频处理场景：流复制、截取后分割、按段数／时长／大小分割、保守上限、仅音频编码、去音轨、多个音轨／字幕、H.264／H.265／VP9／AV1、取消清理。
- 流复制对比编码包 SHA256，确认未重新编码视频；输出重新解码检查。
- EXE 连续两次启动，第二次任务加入现有实例；两个任务各输出两段并可以解码。
- 横屏 H.264、有声竖屏、H.265、无声视频预览；切换后范围重置、暂停定位更新。
- 放大控制栏、居中比例、时间轴、声音控制、英文切换、空格、Esc、F11、双击、反复退出／进入、返回后保持位置与状态。
- Windows GUI 程序类型、隐藏子进程选项；主窗口／设置／预设窗口 DWM 深色标题栏属性。

Local checks covered real processing, packet-data preservation in copy mode, output decoding, packaged repeated launches, preview with/without audio, source changes and expanded-preview controls. Audio buffer delivery and device availability were observed; this is not a listening test on every audio device. Dark-title-bar checks read native DWM attributes.

## 发布 CI / Release CI

工作流重新检查对应源码提交的基础／注册表测试、生成素材的 FFmpeg 回归、边缘场景、Windows 构建以及最终 EXE 的任务、重复启动、流复制、输出解码和 GUI 类型。运行记录是实际 CI 验证的依据；本文件不预先宣称未来运行通过。

The release workflow checks its pinned commit with unit/registry tests, generated-media FFmpeg integration and edge cases, a Windows build, and packaged task/repeated-launch/stream-copy/decode/GUI-subsystem checks. Actual Actions logs establish the result of each release; this document does not pre-claim future passes.

## 限制 / Limits

Windows 11、所有硬件编码器与驱动、4K/HDR、高码率素材、长时间播放及所有多屏/DPI 组合未全面实测。CI 不替代真实桌面的声音、驱动或性能验证。流复制时间与大小边界依赖素材关键帧及封装。没有数字签名或自动更新。

Windows 11, every GPU/driver, 4K/HDR, high-bitrate and long-running playback, and all multi-monitor/DPI configurations have not been comprehensively tested. CI does not replace real desktop/audio/driver performance testing. Stream-copy boundaries depend on source keyframes and muxing. Releases are unsigned and do not auto-update.
