# Implementation slices

这是按依赖组织的实现切片索引和交付范围；bootstrap 不等于 S01 完成，当前是否已交付以 [status](status.md) 为准。每个切片可成为一个独立提交，依赖只指向此前阶段。

通用检查：`uv sync --locked --group dev`、`uv run --locked pytest`、`uv run --locked ruff check .`、`git diff --check`。有 renderer 改动时执行 `pnpm --dir renderer check`。这些命令在 bootstrap 完成后可运行。

**各切片中的阶段测试和新增 CLI 是对应切片的验收入口，当前已随 S01–S15 实现。** 安装的模型和外部提供器环境应单独锁定；CPU 模拟或 mock 不算真实模型/提供器验证。阶段测试生成可公开的 synthetic fixtures；本地歌曲验收证据保存在仓库外。

S10 之后的工作、依赖顺序和后续选择门槛见 [backlog](TODO.md)。S11–S15 已完成。Astrofox 与 projectM 仍需各自的本地锁定运行环境；projectM 每个任务仅开放一个目录内受检预设。

| ID | Result | Dependencies |
| --- | --- | --- |
| [S01 统一音频与协议](S01-canonical-audio.md) | canonical WAV 与来源记录 | none |
| [S02 最小固定帧渲染闭环](S02-minimal-render.md) | 无人值守固定帧短 MP4 | S01 |
| [S03 分轨与音乐特征](S03-stems-features.md) | 四轨分离与统一特征时间线 | S01, S02 |
| [S04 抽象视觉与段落路由](S04-abstract-sections.md) | A 场景、路由与整曲/段落计划 | S02, S03 |
| [S05 外部素材图层与混合合成](S05-media-hybrid.md) | B 素材层与 C 复用合成 | S04 |
| [S06 导入歌词与双语排版](S06-lyrics-import.md) | 逐句字幕导入、关闭与双语排版 | S05 |
| [S07 自动歌词对齐](S07-lyrics-auto.md) | 已知歌词自动对齐与修正 | S03, S06 |
| [S08 多区间样片与可复现重渲染](S08-preview-reproduction.md) | 多区间预览、缓存与无模型重渲染 | S05, S06, S07 |
| [S09 制作 Skill 全流程验证](S09-production-workflow.md) | 实际制作流程与工具易用性 | S08 |
| [S10 两首歌成片与开源使用就绪](S10-songs-quality.md) | 两首 C 全曲成片与反馈驱动改进 | S09 |
| [S11 同音频方案比较基线](S11-variant-comparison.md) | comparison 协议、审阅产物与外部状态修复 | S10 |
| [S12 竖屏与重复结构分析](S12-portrait-structure.md) | 1080x1920 输出与显式应用的结构候选 | S11 |
| [S13 Astrofox 自动化后端](S13-astrofox-backend.md) | 无界面 Astrofox 提供器、MVT 合成/比较与 projectM 可行性证明 | S12 |
| [S14 受检 projectM 后端](S14-projectm-provider.md) | 锁定预设的离线提供器、全局时间复现与同音频比较 | S13 |
| [S15 projectM 预设目录](S15-projectm-preset-catalog.md) | 两种自创预设纳入哈希目录、正式适配器与同曲审阅 | S14 |
