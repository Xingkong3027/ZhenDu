## 简体中文

帧渡 ZhenDu **2.0.2**：让输出目录保持简洁。

- 设置新增 **“为每个任务创建子文件夹”**，默认关闭。旧配置升级后也默认关闭。
- **关闭**：直接输出视频到所选目录；目录留空时保存在原视频旁。单段只产生一个视频，分割仍产生多段。不额外留下输出文件夹或 JSON。
- **开启**：保留此前每个任务单独文件夹的方式；目录留空时使用原视频旁的 `帧渡输出`。
- 文件使用 `_ZhenDu` 后缀，重名自动编号，不覆盖源文件或已存在的视频。直接输出的任务记录保存在程序设置目录的 `tasks` 中。
- 已排队任务保留入队时的设置。中英文界面与文档同步更新。

普通用户下载 **`ZhenDu-2.0.2-windows-x64-portable.zip`**，完整解压后运行 `ZhenDu.exe`。同一包包含简体中文／English。源码包、`BUILD_INFO.json` 和 `SHA256SUMS.txt` 随版本提供。升级请关闭旧程序，保留完整运行库；预设继续使用原配置。

## English

ZhenDu **2.0.2** keeps your output directory tidy.

- Add **Create a subfolder for each task** in Settings, **off by default**, including upgrades.
- **Off:** save videos directly to the selected directory, or beside the source when none is selected. A single output produces one video; splitting still creates multiple parts. No extra output folder or JSON files remain there.
- **On:** retain separate task folders; an empty output directory uses `帧渡输出` beside the source.
- Use `_ZhenDu` and automatic numeric suffixes without overwriting sources or existing files. Direct-mode task records live under `tasks` in the application settings directory.
- Queued tasks keep their original output mode. Both UI languages and READMEs are updated.

Download **`ZhenDu-2.0.2-windows-x64-portable.zip`**, extract everything, then run `ZhenDu.exe`. One package includes English and Simplified Chinese. Source, `BUILD_INFO.json` and `SHA256SUMS.txt` are also provided. Close the older application before upgrading, keep the complete runtime, and retain existing preset settings.
