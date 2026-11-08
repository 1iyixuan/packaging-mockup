# 包装效果图

将包装效果图、刀版或尺寸，整理为白模参考、可编辑 Blender 模型、透明背景正面效果图和可旋转缩放的网页源码。

显示名称：**包装效果图**。技能标识：`packaging-mockup`。当前版本：`0.1.0`。

## 工作流程

1. 检查 Blender 连接；首次使用时检查插件和 Codex MCP 配置，未连接则按官方步骤处理缺失项。
2. 整理包装效果图、刀版、尺寸、材质及网页标题。
3. 先生成白底、灰色表面的白模参考图，用结构线和阴影表现包装体积。
4. 通过 Blender 建立实际三维模型，将原始包装稿映射到对应面。
5. 输出透明背景正面 PNG，保存可编辑 `.blend` 和含贴图的 `.glb`。
6. 生成白色背景、左上角深灰标题的互动网页：电脑拖动旋转、滚轮缩放；手机单指旋转、双指缩放。
7. 先交付原文件和网页源码；本次任务要求部署时，再通过 Netlify Drop 发布并检查链接。

网页布局参考：[包装方案展示页](https://inquisitive-pony-108153.netlify.app/)。

## 安装

下载完整的 [packaging-mockup-v0.1.0.zip](dist/packaging-mockup-v0.1.0.zip)，按 [SHA256SUMS](dist/SHA256SUMS) 校验后解压。将整个 `packaging-mockup` 文件夹放入当前客户端支持的个人技能目录，保留 `scripts`、`references`、`assets` 和 `agents`。

当前官方文档使用 `~/.agents/skills/packaging-mockup/`；部分已有 Codex 环境也使用 `~/.codex/skills/packaging-mockup/`。先检查实际客户端，安装到一处即可，避免重复候选。最终路径必须直接包含 `SKILL.md`，不能多嵌套一层同名文件夹。已有同名技能时先备份再更新。

也可让 Agent 阅读本仓库的 [INSTALL_FOR_AI.md](INSTALL_FOR_AI.md) 后代为安装。

## 调用

桌面界面中输入 `@`，搜索并点选 **包装效果图**，附上资料后发送：

> 根据这些包装资料制作效果图。标题为“品牌名称 / 产品包装方案”。先检查 Blender 连接，再生成白模、建模贴图、透明底正面图和可互动的网页源码，先交付原文件。

Codex CLI／IDE 中可用 `$packaging-mockup`。必须先安装并被应用识别，单纯粘贴 `@包装效果图` 文字不会注册技能。候选未刷新时可重新加载应用。[官方技能说明](https://learn.chatgpt.com/docs/build-skills)

## 依赖与边界

- 实际制作需要可用的图像生成能力和本机 Blender；连接流程使用用户指定的 [MCP for Blender](https://github.com/ahujasid/mcp-for-blender)。安装本 Skill 本身不会安装或启动 Blender 插件。
- 附带的两个 Python 辅助脚本使用 Python 3 标准库；`export_glb.py` 需要在 Blender 的 Python 环境中执行。
- 网页渲染库已本地打包。生成网页后使用 HTTP 服务预览，不能只靠双击 `index.html` 判断是否可用。
- 没有尺寸或刀版时，模型中的估算会单独说明；模型用于外观展示，不等同于生产刀模。
- 颜色以原稿为依据核对；屏幕、印刷与不同渲染器之间不承诺绝对零色差。大陆网络可访问性需要实际测试。
- 本仓库包含技能、脚本和通用模板，不包含客户包装原稿、账号凭据或实际客户模型。

第三方网页库采用 Google model-viewer 4.4.0，保留其 [许可证](assets/viewer/vendor/LICENSE) 和 [来源与完整性记录](assets/viewer/vendor/provenance.json)。
