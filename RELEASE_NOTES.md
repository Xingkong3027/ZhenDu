## 简体中文

帧渡 ZhenDu **2.1.1**：实时查看输出大小，空闲时一键清空队列。

- 任务列表旁新增“清空列表”，仅全部任务停止后可用；排队、处理或取消尚未结束时禁用。清理记录与进度，保留视频和素材列表。
- 新增“输出大小”列，处理中约每半秒刷新已写入大小，完成后显示实际大小；分割任务显示合计和各片段大小，悬停可查看精确字节。
- 按大小分割时，已有片段超过每段目标会显示 `↑`。分析文件和编码／封装副本不重复计入；失败或取消不将临时写入量当作成功输出。
- 清空后重置结果操作和进度，忽略迟到的任务进度，下一轮从零开始。中英文界面、说明和自动回归检查同步更新。

实时大小不是最终大小预测，封装完成或分段重试时可能调整；本次未增加自动限制压缩后文件大小的功能。

下载 **`ZhenDu-2.1.1-windows-x64-portable.zip`**，完整解压后运行 `ZhenDu.exe`。同一个包包含简体中文与 English。升级前关闭旧程序；现有预设继续使用。

## English

ZhenDu **2.1.1** adds live output sizes and an idle-only queue reset.

- Add **Clear list** beside the queue. It stays disabled while jobs are queued, running or still cancelling, and clears records/progress while keeping videos and sources.
- Add **Output size**, updated about every half second while processing and confirmed against actual files on completion. Split tasks show a total plus individual part sizes; hover for exact bytes.
- Show `↑` when a size-based split part exceeds its per-part target. Exclude analysis files and duplicate encoding/remux copies. Failed/cancelled jobs do not present temporary writes as successful output.
- Reset result actions and progress when clearing, ignore late progress updates, and start the next round at zero. Update both UI languages, documentation and automated regressions.

Live bytes are not a final-size prediction and can change during finalization or split retries. This release does not add an automatic compressed-file size limit.

Download **`ZhenDu-2.1.1-windows-x64-portable.zip`**, extract everything and run `ZhenDu.exe`. One package includes English and Simplified Chinese. Close the old application before upgrading; existing presets remain usable.
