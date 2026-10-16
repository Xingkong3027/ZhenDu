# 第三方源码索引 / Third-party source index

此索引与许可证、固定构建信息一起分发。以下是对应版本的上游源码位置；不是使用最新版替代所分发版本。重新分发时应保留原许可、源代码获取说明，以及外部库的适用条款。

This index is distributed with the notices and pinned build information. Links identify the corresponding upstream versions rather than silently substituting latest versions. Preserve license texts, source-access information and applicable external-library terms when redistributing.

## Command-line FFmpeg / ffprobe

- Binary producer: [Gyan / CODEX FFMPEG](https://www.gyan.dev/ffmpeg/builds/).
- Original release: [2026-01-29-git-c898ddb8fe](https://github.com/GyanD/codexffmpeg/releases/tag/2026-01-29-git-c898ddb8fe).
- Exact FFmpeg source: [c898ddb8fede853027a7c9458d928900d5db6e38](https://github.com/FFmpeg/FFmpeg/tree/c898ddb8fede853027a7c9458d928900d5db6e38).
- [Download that source archive](https://github.com/FFmpeg/FFmpeg/archive/c898ddb8fede853027a7c9458d928900d5db6e38.tar.gz).
- License, configuration, enabled libraries and their reported versions: [`../ffmpeg/README.txt`](../ffmpeg/README.txt) and [`../ffmpeg/LICENSE`](../ffmpeg/LICENSE).
- The original binary archive and executable SHA256 values are pinned in [`../tools/fetch_ffmpeg.py`](../tools/fetch_ffmpeg.py). No FFmpeg source changes or recompilation were made by ZhenDu.

完整构建包含外部库，不能把 FFmpeg 主仓库当作所有外部库的源码。上游 README 列出其实际版本，项目与来源信息可在 [Gyan 构建说明](https://www.gyan.dev/ffmpeg/builds/#libraries) 和 [FFmpeg 外部库说明](https://ffmpeg.org/general.html#External-libraries) 查阅。需要重建该完整构建时，应同时取得对应外部库与构建工具，不能用另一版本的精简构建冒充。

The full build contains external libraries. The FFmpeg repository alone is not the source of every external library. The original README lists their reported versions; upstream project information is available in the [Gyan build notes](https://www.gyan.dev/ffmpeg/builds/#libraries) and [FFmpeg external-library documentation](https://ffmpeg.org/general.html#External-libraries). Rebuilding that full distribution also requires corresponding external libraries and tools.

## Qt / PySide6 / Shiboken6 6.10.2

- [Official Qt for Python source archive directory](https://download.qt.io/official_releases/QtForPython/pyside6/PySide6-6.10.2-src/).
- [PySide/Shiboken source ZIP](https://download.qt.io/official_releases/QtForPython/pyside6/PySide6-6.10.2-src/pyside-setup-everywhere-src-6.10.2.zip).
- [Qt 6.10.2 source modules](https://download.qt.io/archive/qt/6.10/6.10.2/submodules/), including qtbase, qtmultimedia, qtsvg, qtimageformats and qttranslations as applicable to the packaged modules.
- [Qt 6.10.2 source repository](https://code.qt.io/cgit/qt/qt5.git/tree/?h=v6.10.2).
- [Qt Multimedia source/build documentation](https://code.qt.io/cgit/qt/qtmultimedia.git/tree/?h=v6.10.2), including its third-party media integration.
- [Qt license information](https://doc.qt.io/qt-6/licensing.html), [Qt for Python licensing](https://doc.qt.io/qtforpython-6/licenses.html).

Qt 的 FFmpeg DLL 不是 Gyan 命令行 FFmpeg。Qt 运行库报告 FFmpeg 7.1.2；对应 [FFmpeg n7.1.2 源码](https://github.com/FFmpeg/FFmpeg/tree/n7.1.2)。Qt 的集成／构建信息还应参照上述同版本 Qt Multimedia 源码，不应假设命令行版本与它相同。

Qt's FFmpeg DLLs are separate from Gyan's CLI executables. The Qt media runtime reports FFmpeg 7.1.2; see [FFmpeg n7.1.2](https://github.com/FFmpeg/FFmpeg/tree/n7.1.2) together with the matching Qt Multimedia integration/build information.

## Python and PyInstaller

- [CPython v3.14.5 source](https://github.com/python/cpython/tree/v3.14.5), [source archive](https://www.python.org/ftp/python/3.14.5/Python-3.14.5.tar.xz).
- [PyInstaller v6.22.3 source](https://github.com/pyinstaller/pyinstaller/tree/v6.22.3), including bootloader sources and license exception.

软件包管理器可能随时间解析到不同的间接依赖。`BUILD_INFO.json` 记录本次程序版本与核心工具链，发行包 `licenses` 目录保留实际安装包提供的许可。开发者替换依赖后需重新检查构建、行为和许可证。

Package resolvers may select different transitive dependencies over time. `BUILD_INFO.json` records this release's application/core toolchain; `licenses` preserves the notices supplied by installed packages. Dependency substitutions need a fresh build, behavior and license review.
