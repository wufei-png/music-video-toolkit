# S06 — 导入歌词与双语排版

状态：未开始。依赖：S05。

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

## 提交与交接

检查 tracked/untracked/ignored，显式 stage 本片代码、测试与状态文档，检查 staged diff 和 `git diff --check --cached` 后提交。更新 status：实际命令/版本、通过或失败、真实集成证据位置、尚未完成的用户审阅，以及下一片。没有通过的 live gate 不能记录成完成；必要时只记录受阻的工作进度，避免伪造验证结果。
