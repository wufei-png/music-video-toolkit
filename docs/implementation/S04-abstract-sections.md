# S04 — 抽象视觉与段落路由

状态：未开始。依赖：S02, S03。

## 独立交付

交付一个可用于整曲的 A 风格，以及整曲默认值 + 段落覆盖的统一 resolver；Skill 可修正段落标签和边界。

## 输入输出

输入：timeline + editable plan。输出：resolved-plan、分段 A 样片，仍可使用不带段落覆盖的整曲计划。

## 实现范围与方法

拥有 plan resolver、signal sampler、transform registry、abstract layers 与 tests/stages/test_s04.py。实现有限可配置的 orb/ribbon/particles（可合并为一个风格），不同 stem 控制明确不同对象。给每种参数和 transform 定义 allowlist、范围、插值/attack-release、信号缺失策略。未知参数硬失败；缺少信号不能静默当零。

## 验收契约

合成 stem-isolation：仅 bass 有信号时 bass 对象响应，drums/vocals 对象不响应。whole defaults 和 section override 的优先级、gap fallback、half-open endpoints、重复 ID/未知 section/未知 route target、模式所需图层被禁用均有检查。自动 novelty 只标记候选边界，手工语义标签可保留。输出至少一个真实片段，并记录对可辨识响应和画面层级的检查。

## 实施时创建并执行的检查

`pnpm --dir renderer check`；`uv run --locked pytest tests/stages/test_s04.py`；通过 S02 的实际 render 回归 click/stem-isolation。

这些是未来验收命令/测试文件；本片开始时补齐，不能直接拿当前文件缺失当产品回归。运行本片测试与所有已完成切片回归，不能依赖后续片的实现。

## 边界与失败处理

默认层仍支持整曲 A；C 不在此做独立实现。不要添加任意代码执行和逐镜头编辑器。

## 提交与交接

检查 tracked/untracked/ignored，显式 stage 本片代码、测试与状态文档，检查 staged diff 和 `git diff --check --cached` 后提交。更新 status：实际命令/版本、通过或失败、真实集成证据位置、尚未完成的用户审阅，以及下一片。没有通过的 live gate 不能记录成完成；必要时只记录受阻的工作进度，避免伪造验证结果。
