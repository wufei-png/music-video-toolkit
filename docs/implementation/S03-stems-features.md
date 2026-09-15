# S03 — 分轨与音乐特征

状态：未开始。依赖：S01, S02。

## 独立交付

交付 `mvt analyze --project DIR --stems four|none`，让真实音乐的 mix 和可选 4 stems 产生 renderer-neutral timeline。

## 输入输出

输入：canonical.wav。输出：stems、timeline、模型/分析配置/耗时记录。four 模式必须产生 vocals/drums/bass/other；none 只产生 mix，不伪造其余信号。

## 实现范围与方法

拥有 separation adapter、librosa analyzer、独立模型依赖锁与 tests/stages/test_s03.py。先试 python-audio-separator 的 4-stem 模型，核实模型名称、来源、授权、版本/哈希和 Mac 内存。feature 参数、hop、边界 padding、normalization、silence policy 要记录。声音分离器和歌词模型采用独立环境，避免强制把 GPU/模型依赖装进轻量 CLI。

## 验收契约

合成四轨输入验证时间基准和静音行为；真实模型测试不能用 mock 代替。两首本地歌各选一个≥20秒片段实际分离，记录时长、峰值资源（可测则测）、听检串音和质量。导出源于指定输入/配置的 RMS、drums onset、bass low energy、mix beat/chroma；不声称 beat=downbeat。用新 timeline 在 S02 渲染路径看到真实响应。

## 实施时创建并执行的检查

`uv run --locked pytest tests/stages/test_s03.py`；为选定 adapter 写出并执行独立锁环境安装/运行命令；保存两首片段实跑报告到外部工作区。

这些是未来验收命令/测试文件；本片开始时补齐，不能直接拿当前文件缺失当产品回归。运行本片测试与所有已完成切片回归，不能依赖后续片的实现。

## 边界与失败处理

模型失败应报告失败，不生成假的 stems。缓存包括 canonical/model/config 哈希；对齐点数变化记录处理，不静默裁剪。

## 提交与交接

检查 tracked/untracked/ignored，显式 stage 本片代码、测试与状态文档，检查 staged diff 和 `git diff --check --cached` 后提交。更新 status：实际命令/版本、通过或失败、真实集成证据位置、尚未完成的用户审阅，以及下一片。没有通过的 live gate 不能记录成完成；必要时只记录受阻的工作进度，避免伪造验证结果。
