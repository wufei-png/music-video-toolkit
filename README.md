# music-video-toolkit

面向 AI agent 的音乐视频制作工具包。Skill 做创作协作，文件协议保存决策，代码执行可复现制作。

**当前状态：S01 已完成，可将输入音频统一解码为项目内的 canonical WAV；尚不能生成视频。** 首版目标是 macOS 上输出 1920×1080、30fps、H.264/AAC MP4。本仓库的 MIT 许可覆盖代码与 Skill，不改变外部素材、模型和依赖的许可证。

## 两个入口

- **制作歌曲**：读取 [make-music-video Skill](skills/make-music-video/SKILL.md)。使用 harness 已有图片/视频生成工具，或导入用户素材。默认先确认 30–60 秒的多个短样片，再做完整成片。
- **继续开发**：读取 [START-HERE](docs/implementation/START-HERE.md)，按 [切片索引](docs/implementation/README.md) 与 implement-in-stages 工作。不要把计划命令当作当前能力。

## 目标能力

- A：音乐驱动的抽象视觉；B：外部图片/视频构成的意境场景；C：复用 A/B 图层叠加。
- 整曲默认配置 + 段落覆盖；关闭、导入、自动对齐三种歌词模式。
- 保存 timeline、plan、assets、lyrics、render manifest；已有计划和素材即可无模型重渲染。
- 用真实歌曲的样片反馈完善通用能力，歌曲专属决定留在制作工作区。

参见 [设计](docs/architecture/design.md)、[协议语义](docs/architecture/contracts.md)、[技术依据](docs/architecture/evidence.md) 和 [当前状态](docs/implementation/status.md)。

## 当前可运行能力

在本仓库根目录运行（Python 3.12；uv 按锁文件安装）：

```bash
uv sync --locked --group dev
uv run --locked mvt --help
uv run --locked mvt capabilities
uv run --locked mvt doctor
uv run --locked mvt decode "/path/to/input.mp3" --project "/path/to/project"
uv run --locked mvt validate --kind source "/path/to/project/source/source.json"
uv run --locked mvt validate --kind timeline examples/timeline.json
uv run --locked mvt validate --kind plan examples/plan-hybrid.json
uv run --locked mvt schema --kind plan
uv run --locked pytest
uv run --locked ruff check .
uv run --locked python scripts/export_schemas.py --check
```

`decode` 通过 FFmpeg 将首个音频流原子写入 48kHz、双声道、24-bit PCM 的 `source/canonical.wav`，并写入带哈希、实际 PCM 帧数和解码器版本的 `source/source.json`。同一内容会复用已通过 preflight 的结果；不同输入不会覆盖已有项目。`doctor` 仅报告工具是否可发现，不证明渲染可用。`validate` 是单文件结构与部分语义校验；项目 preflight 由需要实际文件的命令执行。示例均为合成协议示例，不是实际成片；详见 [示例说明](examples/README.md)。

原始研究报告、两首歌及其制作资产留在父目录，公共工具仓库不依赖它们。新用户可以安装工具、检查协议并解码自己的音频；分析和视频 pipeline 由后续切片逐步交付。

渲染器目前提供时间映射实现和 Three.js 图层接口；构建与测试：

```bash
pnpm --dir renderer install --frozen-lockfile
pnpm --dir renderer check
```

详情见 [renderer](renderer/README.md)。完整开发检查见 [CONTRIBUTING](CONTRIBUTING.md)。
