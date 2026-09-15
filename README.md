# music-video-toolkit

面向 AI agent 的音乐视频制作工具包。Skill 做创作协作，文件协议保存决策，代码执行可复现制作。

**当前状态：S04 已完成。工具可统一解码音频、提取 mix/四轨特征、解析整曲默认值与段落覆盖，并以 orb/ribbon/particles 生成音乐驱动的 1080p30 抽象视频。外部媒体和歌词路径尚未实现。** 本仓库的 MIT 许可覆盖代码与 Skill，不改变外部素材、模型和依赖的许可证。

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
uv run --locked mvt analyze --project "/path/to/project" --stems none
uv run --locked mvt analyze --project "/path/to/project" --stems four
uv run --locked mvt plan resolve --project "/path/to/project" --plan "/path/to/plan.json"
uv run --locked mvt validate --kind source "/path/to/project/source/source.json"
uv run --locked mvt validate --kind stems "/path/to/project/stems/stems.json"
uv run --locked mvt validate --kind timeline examples/timeline.json
uv run --locked mvt validate --kind plan examples/plan-hybrid.json
uv run --locked mvt schema --kind plan
uv run --locked pytest
uv run --locked ruff check .
uv run --locked python scripts/export_schemas.py --check
pnpm --dir renderer install --frozen-lockfile
pnpm --dir renderer exec playwright install chromium
```

`decode` 通过 FFmpeg 将首个音频流原子写入 48kHz、双声道、24-bit PCM 的 `source/canonical.wav`，并写入带哈希、实际 PCM 帧数和解码器版本的 `source/source.json`。同一内容会复用已通过 preflight 的结果；不同输入不会覆盖已有项目。

`analyze --stems none` 只产生 mix RMS、beat 和 12 维 chroma，不伪造 stem 信号。`--stems four` 在独立锁环境中运行 audio-separator 0.44.2 的 `htdemucs.yaml`，验证 vocals/drums/bass/other 四个实际文件，把 44.1kHz 模型输出显式对齐到项目 48kHz 时钟，再增加 stem RMS、drums onset 和 bass low-frequency energy。timeline、stem manifest 和 run manifest 保存源、模型、配置、哈希、对齐和耗时；缓存同时校验这些身份。模型默认下载到用户缓存，可用 `MVT_MODEL_DIR` 改写；预训练权重的许可证尚未由上游确认，不要分发。

`doctor` 报告工具、锁定分析环境和浏览器是否可发现；模型未下载不等于 mix-only 分析不可用。`validate` 是单文件结构与部分语义校验；项目 preflight 由需要实际文件的命令执行。示例均为合成协议示例，不是实际成片；详见 [示例说明](examples/README.md)。

`plan resolve` 对 orb、ribbon、particles 及 linear、threshold、smooth 做参数白名单和范围校验，把整曲默认值、手工或自动候选段落、gap 回退和段落过渡解析成覆盖全曲的 `resolved-plan.json`。route 缺少信号、未知参数/目标、未知段落或任一 span 禁用模式必需图层都会硬失败。`render` 可执行该抽象 resolved plan；S02 的 `s02.pulse`、`s02.image`、`s02.text` 验收计划仍保持兼容。S05 才加入通用媒体层。

原始研究报告、两首歌及其制作资产留在父目录，公共工具仓库不依赖它们。新用户可以安装工具、检查协议、解码并分析自己的音频；生产视觉能力由后续切片逐步交付。

渲染器目前提供时间映射实现和 Three.js 图层接口；构建与测试：

```bash
pnpm --dir renderer install --frozen-lockfile
pnpm --dir renderer check
```

详情见 [renderer](renderer/README.md)。完整开发检查见 [CONTRIBUTING](CONTRIBUTING.md)。
