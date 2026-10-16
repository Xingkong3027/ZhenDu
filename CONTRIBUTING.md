# 贡献与发布 / Contributing and releasing

## 简体中文

欢迎通过 Issues 提交问题或通过 Pull Request 改进代码。问题中请提供版本、Windows 与显卡／驱动信息、复现步骤和脱敏日志。不要提交个人配置、私人视频、虚拟环境、FFmpeg EXE 或编译目录。

使用 README 中的固定工具链和 `tools/fetch_ffmpeg.py` 准备依赖。运行单元测试、`tests.integration` 与 `tests.edge_integration`。修改预览时，在有桌面和音频设备的 Windows 环境运行 `tests.expanded_preview`，或使用 EXE 的 `--self-test ... --test-video ... --test-expanded`。不要把无音频设备的 CI 视为真实听感或显卡性能验证。

版本流程：更新 `zhendu/__init__.py`、CHANGELOG、双语发行说明与示例版本号；检查 README 的两种语言同步。提交源码后等待 CI 成功，再为同一提交创建附注标签，例如 `git tag -a v2.0.0 -m "ZhenDu 2.0.0"`，推送标签。标签工作流在 Windows 构建并验证程序，生成准确 Git 源码包、BUILD_INFO 和 SHA256SUMS，在草稿中重新下载核验附件后公开。已公开标签不可移动，发布修复使用新版本。

发布不依赖本机浏览器凭据或私人令牌。Git 使用正常认证；Actions 的发布任务仅使用仓库内的临时 `GITHUB_TOKEN`。Pull Request 的测试任务不发布版本。正式仓库不提交大型程序包，后续版本可复用该流程。

## English

Use Issues for reports and Pull Requests for changes. Include version, Windows/GPU/driver details, reproduction steps and redacted logs. Do not commit private settings or videos, virtual environments, FFmpeg executables or build directories.

Use the pinned README toolchain and dependency helper. Run unit tests, `tests.integration` and `tests.edge_integration`. Preview changes also need `tests.expanded_preview` on a Windows desktop with audio devices, or the packaged `--self-test ... --test-video ... --test-expanded` check. CI without audio hardware does not validate subjective playback or GPU performance.

Update `zhendu/__init__.py`, the changelog, bilingual release notes and version examples. Keep both READMEs aligned. After source CI passes, create an annotated version tag on the same commit and push it. The tag workflow builds and checks the Windows program, archives exact Git source, records build information and hashes, downloads draft assets for verification, then publishes. Never move published tags; use a new version for fixes.

Git uses normal authentication; publishing uses the repository-scoped temporary Actions token. Browser credentials and private tokens are not collected. PR checks cannot publish. Large application archives belong in Releases, not source history.
