# S08 — 多区间样片与可复现重渲染

状态：完成。依赖：S05, S06, S07。

## 独立交付

交付 `mvt preview` 和可定位的完整 render manifest；已有协议/素材即可无模型重渲染。

## 输入输出

输入：resolved artifacts、明确 sample ranges。输出：独立样片 + 可选 review reel、完整 manifest、可复用缓存。

## 实现范围与方法

拥有 excerpt scheduler、cache DAG、manifest/atomic jobs 与 tests/stages/test_s08.py。默认样片总计约30–60秒，选择 sparse/climax/transition（含前后文），由 Skill 依据分析确定。全局帧编号不复位；有状态效果用 pre-roll/seek cache。预览封装时间可从零起，但视觉/歌词取样保持全曲时间。

## 验收契约

同源同配置两次渲染关键帧误差在锁环境约定容差内；截取整曲对应帧与独立样片一致。plan、asset、font、seed、analysis 配置各改一项验证正确失效；不修改的手工歌词和 section 仍保留。禁用模型/网络仍可重渲染。失败/取消无伪 completed；manifest 缺 output、错 source/hash 或 stale plan 被拒绝。

## 实施时创建并执行的检查

`uv run --locked pytest tests/stages/test_s08.py`；`pnpm --dir renderer check`；actual double render + excerpt/full comparison。

这些是未来验收命令/测试文件；本片开始时补齐，不能直接拿当前文件缺失当产品回归。运行本片测试与所有已完成切片回归，不能依赖后续片的实现。

## 边界与失败处理

不能只用 perceptual hash 证明同步；事件/帧索引精确测，画面另测容差。H.264 文件字节级相同不是承诺。

## 提交与交接

检查 tracked/untracked/ignored，显式 stage 本片代码、测试与状态文档，检查 staged diff 和 `git diff --check --cached` 后提交。更新 status：实际命令/版本、通过或失败、真实集成证据位置、尚未完成的用户审阅，以及下一片。没有通过的 live gate 不能记录成完成；必要时只记录受阻的工作进度，避免伪造验证结果。
