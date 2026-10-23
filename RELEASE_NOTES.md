## 简体中文

帧渡 ZhenDu **2.1.0**：按素材配置，更清楚地管理每轮任务。

- 修复历史任务导致下一轮进度从 50% 开始的问题，进度和结束统计只计算本轮；保留历史结果操作。
- 压缩／截取／分割各有“同步配置”，默认仅压缩开启。关闭时分别记住每个素材的参数；开启时将当前页应用到全部素材。
- 成功后自动移出素材列表；失败保留、取消勾选并标红；取消的素材保留并取消勾选。已重试的历史失败不重复提交。
- 右键菜单和素材勾选适配深色主题；失败文件即使选中也保持红色。
- 分割未启用时参数全部变灰，且只显示当前分割方式对应的设置。
- 主预览与放大预览支持在线上任意位置点击或拖动定位，并保持播放／暂停状态。
- 修复隐藏／未启用字段的残留文本阻止处理、素材切换丢失草稿等状态问题。中英文界面与说明同步更新。

下载 **`ZhenDu-2.1.0-windows-x64-portable.zip`**，完整解压后运行 `ZhenDu.exe`。同一个包包含简体中文与 English。升级前关闭旧程序；现有预设继续使用。

## English

ZhenDu **2.1.0** adds individual source settings and clearer processing rounds.

- Start every new round at 0, excluding historical tasks from progress and summary counts while preserving their output actions.
- Add independent **Sync settings** switches to Compress, Trim and Split. Only Compress is synchronized by default. With sync off, each source retains its own settings; enabling it applies the current tab to every source.
- Remove successful sources automatically. Keep failures unchecked and red, including selected rows. Keep cancelled sources unchecked. Do not resubmit already retried historical failures.
- Match context menus and source checkboxes to the dark theme.
- Gray out disabled split parameters and show only fields relevant to the selected split mode.
- Click or drag anywhere on either preview timeline, preserving playback/pause state.
- Prevent hidden/inactive stale text from blocking jobs and preserve drafts across source changes. Update both UI languages and documentation.

Download **`ZhenDu-2.1.0-windows-x64-portable.zip`**, extract everything and run `ZhenDu.exe`. One package includes English and Simplified Chinese. Close the old application before upgrading; existing presets remain usable.
