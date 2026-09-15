# S01 — 统一音频与协议

状态：完成（2026-09-15）。依赖：none。

## 独立交付

交付 `mvt decode INPUT --project DIR`：统一生成 48kHz stereo PCM WAV 与来源/解码记录，报告 actual sample count。补齐 bootstrap 单文件校验之外的项目级交叉引用和资源路径解析。音频文件保持在仓库外。

## 输入输出

输入：用户音频、输出项目目录。输出：source/canonical.wav、source/source.json、可供后续分析的来源标识。CLI 结构化输出、退出码和失败信息；CLI 不调用生成服务。

## 实现范围与方法

拥有 audio/decode 模块、project preflight、CLI decode、tests/stages/test_s01.py。复用现有协议模型；必要时增加 source record schema。FFmpeg 通过参数数组调用，按显式 stream 解码；使用临时文件并在成功后原子落盘。已有同一输入/配置复用缓存，不同输入不得静默覆盖项目。

## 验收契约

合成一个已知采样点数的 WAV，编码为 MP3 再解码；以实际 PCM 点数为准，不要求损失编码还原全部样值。不同 cwd、带空格/中文路径均可用。验证缺失文件、损坏输入、FFmpeg 缺失、已有冲突输出、失败清理。所有后续重采样从 canonical 派生并可映射回其时钟。

## 实施时创建并执行的检查

`uv run --locked pytest tests/stages/test_s01.py`；真实 FFmpeg decode/ffprobe（测试内执行）；`uv run --locked mvt validate --kind timeline examples/timeline.json`。

这些是未来验收命令/测试文件；本片开始时补齐，不能直接拿当前文件缺失当产品回归。运行本片测试与所有已完成切片回归，不能依赖后续片的实现。

## 边界与失败处理

不要实现 MIR/分轨/渲染。源哈希、canonical 哈希、decoder 版本、点数和声道必须可追溯。

## 提交与交接

检查 tracked/untracked/ignored，显式 stage 本片代码、测试与状态文档，检查 staged diff 和 `git diff --check --cached` 后提交。更新 status：实际命令/版本、通过或失败、真实集成证据位置、尚未完成的用户审阅，以及下一片。没有通过的 live gate 不能记录成完成；必要时只记录受阻的工作进度，避免伪造验证结果。

## 完成证据

- `8f1e4f6`：新增权威 source record 模型/schema、相对记录文件的路径解析，以及 canonical 路径、哈希、WAV 格式和实际 PCM 帧数 preflight。
- `77426ca`：新增原子 FFmpeg 解码、结构化 CLI 结果、缓存/冲突保护和真实 MP3→PCM 集成测试。
- `uv run --locked pytest tests/stages/test_s01.py -q`：12 passed；当前主机实际调用 FFmpeg/ffprobe 8.1，未跳过集成测试。
- 尚未执行真实歌曲主观听音；S01 的验收是解码、时钟与来源可追溯性，不把合成测试表述为歌曲质量证明。
