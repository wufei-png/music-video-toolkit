# S05 — 外部素材图层与混合合成

状态：已完成（2026-09-15）。依赖：S04。

## 独立交付

交付 B 意境模式和 C=A+B 复用合成，支持素材导入/替换、段落换景和转场。

## 输入输出

输入：图片/视频/字体、assets manifest、A/B/C plans。输出：三种模式的短片及素材 preflight 结果。

## 实现范围与方法

拥有 asset preflight、media layers/compositor/transition 与 tests/stages/test_s05.py。检查实际存在/哈希/type/时长/字体；仅消费 local files。定义 fit/crop、z-order、opacity、mask、混合、video offset/loop/hold/trim、图片轻运动及视频默认静音。用同一 A/B 图层代码组合 C。优先确定性 FFmpeg 视频取帧；若浏览器 seek，证明 readiness 和 exact-frame 结果。

## 验收契约

相同 timeline 渲染 A/B/C，不重新分离；替换 asset ID 的内容使相关缓存失效。用带帧编号的短视频证明多片段 seek、loop/hold、出入点及无音轨混入。alpha 叠加、mask 和段落 crossfade 在关键帧有可比证据。缺文件、错哈希、未知素材、过短媒体无策略、字体缺失明确失败。

## 实施时创建并执行的检查

`pnpm --dir renderer check`；`uv run --locked pytest tests/stages/test_s05.py`；实际编码三个模式的 synthetic demo。

这些是未来验收命令/测试文件；本片开始时补齐，不能直接拿当前文件缺失当产品回归。运行本片测试与所有已完成切片回归，不能依赖后续片的实现。

## 边界与失败处理

视觉生成由 harness 做；CLI 不偷偷下载 URL/调用生成 API。公开 fixture 使用自产合成素材。

## 实施结果

`mvt assets check` 对本地图片、恒定帧率视频和字体执行哈希、类型、尺寸、帧数、帧率、时长、音轨及字体族预检，原子写入 `assets.checked.json`。素材 manifest 和每个素材内容共同组成缓存身份；远程 URL、缺失文件、哈希或类型错误、可变帧率视频都会明确失败。

`plan resolve` 已支持 image/video 媒体层，参数边界覆盖 cover/contain、位置、缩放、轻运动、z、opacity、circle mask、normal/add blend，以及视频的全曲样本 offset、半开帧范围 `[in_frame, out_frame)` 和 `error|loop|hold` 结束策略。offset 前保持入口帧，视频自身音轨强制静音。resolved plan 固定原始及已检查素材 manifest 的哈希。

浏览器渲染器复用相同图层生命周期生成 A/B/C；视频先由 FFmpeg 完整解码成零起始编号 PNG，再由全局样本时钟选择源帧。段落切换同时保留前后媒体的独立素材、布局、mask、blend 和 opacity，并按 `transition_samples` 交叉淡化。

自动验收用同一 1 秒 timeline 实际编码 30 帧 A/B/C。带 880 Hz 自有音轨的 6 帧、2 fps 彩色视频证明 trim/offset/loop/hold 与源帧编号；输出音轨仍为 canonical 静音。帧 14/18/23 证明红色背景经中间混合帧转为蓝色，circle mask、alpha 叠加和三模式输出差异均通过像素或哈希检查。持久演示及 contact sheets 位于 `../projects/synthetic-s05/project/`，不进入 Git；人工查看与像素证据一致。当前浏览器仍报告 SwiftShader。

## 提交与交接

已检查 tracked/untracked/ignored；本片提交只包含代码、生成 schema、测试和文档。合成媒体、解码帧和输出视频留在外部项目目录。
