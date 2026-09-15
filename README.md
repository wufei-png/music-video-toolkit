# music-video-toolkit

面向 AI agent 的音乐视频制作工具包。Skill 做创作协作，文件协议保存决策，代码执行可复现制作。

**当前状态：开发交接与骨架阶段，尚不能从 MP3 生成视频。** 首版目标是 macOS 上输出 1920×1080、30fps、H.264/AAC MP4。本仓库的 MIT 许可覆盖代码与 Skill，不改变外部素材、模型和依赖的许可证。

## 两个入口

- **制作歌曲**：读取 [make-music-video Skill](skills/make-music-video/SKILL.md)。使用 harness 已有图片/视频生成工具，或导入用户素材。默认先确认 30–60 秒的多个短样片，再做完整成片。
- **继续开发**：读取 [START-HERE](docs/implementation/START-HERE.md)，按 [切片索引](docs/implementation/README.md) 与 implement-in-stages 工作。不要把计划命令当作当前能力。

## 目标能力

- A：音乐驱动的抽象视觉；B：外部图片/视频构成的意境场景；C：复用 A/B 图层叠加。
- 整曲默认配置 + 段落覆盖；关闭、导入、自动对齐三种歌词模式。
- 保存 timeline、plan、assets、lyrics、render manifest；已有计划和素材即可无模型重渲染。
- 用真实歌曲的样片反馈完善通用能力，歌曲专属决定留在制作工作区。

参见 [设计](docs/architecture/design.md)、[协议语义](docs/architecture/contracts.md)、[技术依据](docs/architecture/evidence.md) 和 [当前状态](docs/implementation/status.md)。
