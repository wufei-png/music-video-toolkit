# S07 — 自动歌词对齐

状态：未开始。依赖：S03, S06。

## 独立交付

交付 `mvt lyrics align --text ... --language ...`，Mac 本地自动对齐已有歌词并输出与导入完全相同的格式。

## 输入输出

输入：已知歌词、canonical/vocals 音轨、语言。输出：aligned cues、unmatched spans、模型/时间偏移记录；人工修正另存 edited 版本。

## 实现范围与方法

拥有 alignment adapter、独立环境/模型锁、文本到词/句 mapping 与 tests/stages/test_s07.py。先做 WhisperX CPU int8 spike：确认 en/zh 对齐模型实际可装可用。ASR 可提供粗时窗，但必须匹配用户原文；WhisperX alignment 的输入带窗口，不可把整首重复歌词粗暴当一个准确窗口。错漏词、长音、反复副歌须显式策略。

## 验收契约

先对两首歌分别选重复副歌和稀疏人声片段，人工标注每首至少12个行首参考点；初始候选门槛为中位绝对误差≤250ms、P90≤500ms，超过则必须标疑并修正，不声称自动合格。全曲输出保持非重叠、有序、不超时，缺失行显式列出。修正后的字幕进入 S06 无需模型重跑。实际两首歌运行和检查后才算支持自动，不以 unit mock 或 import-only 替代。

## 实施时创建并执行的检查

`uv run --locked pytest tests/stages/test_s07.py`；为隔离 adapter 写出锁定安装/运行命令；保存实测参考点、误差统计与耗时。

这些是未来验收命令/测试文件；本片开始时补齐，不能直接拿当前文件缺失当产品回归。运行本片测试与所有已完成切片回归，不能依赖后续片的实现。

## 边界与失败处理

门槛是待实测的初始工程目标，任何调整要记录理由和用户可见效果。模型不适用则修复/更换适配器，维持自动能力为未完成门槛。

## 提交与交接

检查 tracked/untracked/ignored，显式 stage 本片代码、测试与状态文档，检查 staged diff 和 `git diff --check --cached` 后提交。更新 status：实际命令/版本、通过或失败、真实集成证据位置、尚未完成的用户审阅，以及下一片。没有通过的 live gate 不能记录成完成；必要时只记录受阻的工作进度，避免伪造验证结果。
