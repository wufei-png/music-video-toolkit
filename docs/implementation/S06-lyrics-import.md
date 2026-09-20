# S06 — 导入歌词与双语排版

状态：已完成（2026-09-15）。依赖：S05。

## 独立交付

交付 `mvt lyrics import`，支持 LRC/SRT 转统一逐句 cues、关闭与显示，手工修正后可重渲染。

## 输入输出

输入：带时间戳歌词、语言、pin 住的字体。输出：lyrics.json、字幕渲染短片。

## 实现范围与方法

拥有 lyric importer、cue timeline、text layout 和 tests/stages/test_s06.py。LRC 缺少最后结束时间时需明确采用下一行起点/歌曲终点的规则并记录；SRT 重叠不能静默丢弃。静态逐句字幕与轻淡入淡出即可，逐字卡拉 OK 非目标。

## 验收契约

中文、英文、多行、长句、标点、重复段落、无歌词间奏可显示且不越安全边距。cue 的起止帧与关闭模式符合契约，off 不加载歌词模型/文件。实际使用可分发字体时附许可证；不能凭本机有字体就宣称可移植。导入-编辑-再渲染保留文本顺序和时间。

## 实施时创建并执行的检查

`uv run --locked pytest tests/stages/test_s06.py`；`pnpm --dir renderer check`；渲染双语 fixture 做截图与 timing checks。

这些是未来验收命令/测试文件；本片开始时补齐，不能直接拿当前文件缺失当产品回归。运行本片测试与所有已完成切片回归，不能依赖后续片的实现。

## 边界与失败处理

用户提供歌词作为权威文本，bootstrap 两首歌词不进入公共 fixture。

## 实施结果

`mvt lyrics import FILE --project DIR --language TAG` 已支持严格 UTF-8 LRC/SRT。LRC 保留源文件顺序与重复文本，按下一保留时间点或歌曲终点补齐结束时间，并记录 offset、结束规则和跳过的 stage heading 数；SRT 保留显式多行文本与端点，重叠、倒序、空 cue、越界、未知格式及超过 240 字符均明确失败。输入文本哈希、canonical audio 哈希和 importer provenance 写入 `lyrics.json`。相同导入可复用；任何不同或损坏的既有输出都不会被覆盖，保护手工修正。

启用字幕的 plan 必须指定已通过 S05 preflight 的 font asset。resolved plan 绑定歌词哈希并在自定义输出目录中重写相对路径。渲染器嵌入该字体，以半开样本范围选择 cue，在 100 ms 内轻淡入淡出；中英文、显式换行和长句会缩放并最多包为五行，字幕面板保持在 1080p 安全边距内。`off` 不解析默认 `lyrics.json`，无歌词间奏不显示面板。

自动测试实际编码 2.5 秒、75 帧双语短片，帧 10 显示中英首句、帧 30 为无字幕间奏、帧 50 显示长双语句；区域像素和时间测试均通过。持久样片与 contact sheet 位于 `../projects/synthetic-s06/project/`。人工查看确认换行、标点和安全边距清楚。验收使用系统 Arial Unicode，仅作为本机证据，未复制或宣称字体可分发。

## 提交与交接

本片提交只包含 importer、协议/schema、固定布局实现、合成测试与文档。系统字体、歌词输入、截图和生成视频留在外部 synthetic 项目，不进入 Git。
