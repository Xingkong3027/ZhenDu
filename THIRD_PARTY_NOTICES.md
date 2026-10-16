# 第三方组件 / Third-party notices

帧渡自身代码使用 GPL-3.0-only，见根目录 LICENSE。第三方代码、商标及其许可证仍归原权利人所有。以下组件没有因包含于帧渡而变成本项目自有作品。

ZhenDu's own code is GPL-3.0-only. Dependencies, trademarks and their licenses remain with their respective owners. Their inclusion is not a claim of ownership.

| Component | Version / origin | License / notices |
| --- | --- | --- |
| FFmpeg / ffprobe CLI | Gyan `2026-01-29-git-c898ddb8fe-full_build` | GPLv3; original `ffmpeg/LICENSE` and `ffmpeg/README.txt` including upstream source commit, configuration and external library versions |
| Qt / PySide6 / Shiboken6 | 6.10.2, official Qt for Python wheels | Applicable LGPLv3/GPLv3 and third-party terms in distributed `licenses` directory; see source index |
| Qt Multimedia FFmpeg runtime | 7.1.2, shipped by Qt wheels | Separate from the CLI build; its sources and notices belong to the Qt/FFmpeg upstream distributions |
| Python | 3.14.5 | PSF license and bundled notices in `licenses/Python-LICENSE.txt` |
| PyInstaller bootloader | 6.22.3 | GPL with bootloader exception, as stated by upstream; included package notices in `licenses` |

命令行 FFmpeg 保留原始二进制，不做裁剪重编译。ffplay 没有被调用或分发。Qt 媒体 DLL 位于 `_internal/PySide6`，不能因省略 ffplay 而删除它们。保留发行包中的动态库和完整许可信息；没有禁止替换库或为调试修改而进行逆向工程的附加条款。

The CLI FFmpeg binaries are unmodified. Unused ffplay is not shipped. Qt's multimedia DLLs in `_internal/PySide6` are distinct from the CLI tools and must remain. Keep the dynamic libraries and notices with distributions. This project imposes no additional prohibition on replacing libraries or reverse engineering to debug modifications.

源码与版本信息见 [docs/THIRD_PARTY_SOURCES.md](docs/THIRD_PARTY_SOURCES.md)。外部依赖不会被冒称为帧渡源码，源码仓库也不包含大型第三方 EXE。

Source locations and version information: [docs/THIRD_PARTY_SOURCES.md](docs/THIRD_PARTY_SOURCES.md). Large third-party executables are excluded from source control.

- [FFmpeg license information](https://ffmpeg.org/legal.html)
- [Qt for Python license information](https://doc.qt.io/qtforpython-6/licenses.html)
- [Python license](https://docs.python.org/3.14/license.html)
- [PyInstaller license and exception](https://pyinstaller.org/en/stable/license.html)
