# S09 — 制作 Skill 全流程验证

状态：完成。依赖：S08。

## 独立交付

以真实可调用命令修订制作 Skill，完成从 brief、素材、计划到样片/首版的使用闭环，区分 sample-approval 和 autonomous。

## 输入输出

输入：小型公开合成示例和用户约束。输出：演练记录、完整 artifact bundle、可独立运行的重渲染命令。

## 实现范围与方法

拥有 Skill、使用文档、CLI ergonomics 和 tests/stages/test_s09.py。用实际 harness 能力准备素材；若没有生成工具，用明确自产 fixture 演练并报告生成路径未测。新使用者可克隆、安装、查能力并走完支持流程；不要将开发计划或 implement-in-stages 塞入制作 Skill 主流程。

## 验收契约

一次 sample-approval 演练停在样片反馈处，取得明确反馈后才继续；一次明确 autonomous 演练可输出首版。检查 artifact 完整、工具调用符合 capabilities、外部素材可替换、无模型重渲染。Skill 静态校验只证明结构；若未做真实模型行为演练，保持该门槛未验证。把发现的通用操作障碍修入工具，并复测。

## 实施时创建并执行的检查

`uv run --locked pytest tests/stages/test_s09.py`；现有全套检查；可用时执行 skill-creator quick_validate；保存实际演练日志。

这些是未来验收命令/测试文件；本片开始时补齐，不能直接拿当前文件缺失当产品回归。运行本片测试与所有已完成切片回归，不能依赖后续片的实现。

## 边界与失败处理

不因演练擅自安装全局 Skill、发消息、公开素材或发布视频。明确授权的独立模型评估才使用子代理。

## 提交与交接

检查 tracked/untracked/ignored，显式 stage 本片代码、测试与状态文档，检查 staged diff 和 `git diff --check --cached` 后提交。更新 status：实际命令/版本、通过或失败、真实集成证据位置、尚未完成的用户审阅，以及下一片。没有通过的 live gate 不能记录成完成；必要时只记录受阻的工作进度，避免伪造验证结果。
