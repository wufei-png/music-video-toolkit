# S04 — 抽象视觉与段落路由

状态：完成。依赖：S02, S03。

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

## 2026-09-15 实施记录

- `mvt plan resolve` 生成带源 plan/timeline 哈希的 `resolved-plan.json`；每个 span 精确覆盖全曲，段落优先于整曲默认值，gap 使用默认值，边界采用半开区间。
- 手工 section 的 ID、label、origin 原样保留；没有 section 时，mix RMS novelty 只生成无语义标签的 `automatic` 候选。静音不会生成伪边界。
- orb/ribbon/particles 参数和 route target 均使用闭合白名单及范围；linear/threshold/smooth 参数完整校验。信号线性采样、尾值保持、attack/release 和 section transition 都在固定帧路径执行。
- 合成 stem isolation 中只有 bass 信号变化；bass orb 响应，drums ribbon 与 vocals particles 保持各自最小路由值。未知参数、信号、section、target、重复 override 和禁用必需图层均硬失败。
- soft-harm 的真实 20 秒 S03 timeline 已渲染为 600 帧抽象样片。代表帧视觉检查确认青色 orb、洋红 ribbon、暖色 particles 的对象身份和前中后层级可辨识；记录保存在外部 `projects/soft-harm/s04/`。

## 2026-10-03 兼容维护

- Ribbon 新增静态 `length` 参数，范围 `[0.1, 1.0]`，默认 `1.0`；支持已有段落覆盖与过渡，不新增音频路由目标。长度与线宽、纵向幅度独立。
- 旧 resolved plan 缺少此字段时，浏览器使用 `1.0`。实际 Chromium/WebGL 检查确认旧计划和显式默认值像素相同；`0.75` 将水平墨迹范围缩至 75%，纵向范围保持不变，两种输出比例均通过。
- 锁定环境检查：S04 Python **14 passed**，完整 Python **178 passed in 127.50 s**，渲染器 **27 passed**；Ruff、schema export check、`git diff --check` 通过。Python 协议 envelope 未改，JSON schemas 无漂移；旧 resolver 需要升级后才能处理显式 `length`。
- 外部 `../projects/releases-20261002/songs/01-68b31531/preview-review-v2/` 的三个真实三秒片段完成；23 秒与 105 秒帧已查看，背景覆盖完整、曲线长度收窄。歌曲视觉批准与后续整曲检查仍在外部生产工作区，不能由这些代码检查代替。

### 固定粒子方向

- Particles 新增静态 `rotation_speed`，范围 `[0.0, 0.25]` rad/s，默认及旧 resolved plan 的浏览器回退值均为 `0.05`。设为 `0.0` 后整片粒子方向固定，现有 size 路由仍有效；不增加音频路由目标或动态透明度功能。
- 实际 Chromium/WebGL 在两种输出比例检查旧计划与显式默认值像素相同；固定方向的 0 秒和 10 秒画面一致，反向 seek 不改变结果。Python 检查默认、段落覆盖、非法值与禁止音频路由。
- 锁定完整 Python **184 passed in 138.04 s**，S04 **20 passed**，渲染器 **28 passed**；Ruff、schema export check、`git diff --check` 通过。协议 envelope 与 JSON schemas 未变。实际歌曲声部映射短片与主观审阅属于外部生产工作，不构成本片自动测试结论。
