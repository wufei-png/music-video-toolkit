# S02 — 最小固定帧渲染闭环

状态：未开始。依赖：S01。

## 独立交付

交付由合成时间线驱动的 1080p30 短片，贯通 Three.js、可定位帧的截图/读回与 FFmpeg H.264/AAC。一个命令可无人值守执行。

## 输入输出

输入：S01 canonical 音频、合成 timeline 和最小 plan。输出：短 MP4、同步证据、渲染环境记录。

## 实现范围与方法

拥有 renderer host/capture/encode、Python render adapter 与 tests/stages/test_s02.py。首选本地 Chromium + Playwright 控制渲染；安装阶段锁定浏览器修订并通过 doctor 报告。禁止依赖屏幕录制、实时 requestAnimationFrame 速度、自动播放和 save dialog。为每帧资源 readiness 建立 barrier；FFmpeg 管道要处理背压、取消和错误清理。

## 验收契约

5–10 秒 public synthetic click fixture 在 1/2/3 秒触发画面脉冲，比较解码后的音频 click 与画面帧，视觉量化误差≤1帧，容器 AAC 延迟应解释并检查。全程 1920×1080、30/1、无丢帧、总帧数与端点符合契约。证明中文字体渲染和本地图片层（由合成 fixture 提供）；完整素材系统后置。重复输出比关键帧误差并记录同机容差。

## 实施时创建并执行的检查

`pnpm --dir renderer install --frozen-lockfile`；`pnpm --dir renderer check`；`uv run --locked pytest tests/stages/test_s02.py`（实际浏览器与 FFmpeg）；ffprobe 验证编码/尺寸/fps。

这些是未来验收命令/测试文件；本片开始时补齐，不能直接拿当前文件缺失当产品回归。运行本片测试与所有已完成切片回归，不能依赖后续片的实现。

## 边界与失败处理

如果捕获/中文/编码不通，先修 host，不叠加复杂场景。CPU 软件绘制仅能证明功能，必须报告是否使用硬件加速。

## 提交与交接

检查 tracked/untracked/ignored，显式 stage 本片代码、测试与状态文档，检查 staged diff 和 `git diff --check --cached` 后提交。更新 status：实际命令/版本、通过或失败、真实集成证据位置、尚未完成的用户审阅，以及下一片。没有通过的 live gate 不能记录成完成；必要时只记录受阻的工作进度，避免伪造验证结果。
