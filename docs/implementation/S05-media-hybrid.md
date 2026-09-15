# S05 — 外部素材图层与混合合成

状态：未开始。依赖：S04。

## 独立交付

交付 B 意境模式和 C=A+B 复用合成，支持素材导入/替换、段落换景和转场。

## 输入输出

输入：图片/视频/字体、assets manifest、A/B/C plans。输出：三种模式的短片及素材 preflight 结果。

## 实现范围与方法

拥有 asset preflight、media layers/compositor/transition 与 tests/stages/test_s05.py。检查实际存在/哈希/type/时长/字体；仅消费 local files。定义 fit/crop、z-order、opacity、mask、混合、video offset/loop/hold/trim、图片轻运动及视频默认静音。用同一 A/B 图层代码组合 C。优先确定性 FFmpeg 视频取帧；若浏览器 seek，证明 readiness 和 exact-frame 结果。

## 验收契约

相同 timeline 渲染 A/B/C，不重新分离；替换 asset ID 的内容使相关缓存失效。用带帧编号的短视频证明多片段 seek、loop/hold、出入点及无音轨混入。alpha 叠加、mask 和段落 crossfade 在关键帧有可比证据。缺文件、错哈希、未知素材、过短媒体无策略、字体缺失明确失败。

## 实施时创建并执行的检查

`pnpm --dir renderer check`；`uv run --locked pytest tests/stages/test_s05.py`；实际编码三个模式的 synthetic demo。

这些是未来验收命令/测试文件；本片开始时补齐，不能直接拿当前文件缺失当产品回归。运行本片测试与所有已完成切片回归，不能依赖后续片的实现。

## 边界与失败处理

视觉生成由 harness 做；CLI 不偷偷下载 URL/调用生成 API。公开 fixture 使用自产合成素材。

## 提交与交接

检查 tracked/untracked/ignored，显式 stage 本片代码、测试与状态文档，检查 staged diff 和 `git diff --check --cached` 后提交。更新 status：实际命令/版本、通过或失败、真实集成证据位置、尚未完成的用户审阅，以及下一片。没有通过的 live gate 不能记录成完成；必要时只记录受阻的工作进度，避免伪造验证结果。
