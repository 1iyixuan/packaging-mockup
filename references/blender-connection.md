# Blender 连接与安装

仅在首次检查或连接失败时读。上游维护地址：https://github.com/ahujasid/mcp-for-blender 。安装前查当前 README；命令随版本更新，以当前官方说明和本机 `--help` 为准，不根据旧博客猜插件名或端口。

## 检测与复用

1. 优先调用已有 `get_addon_status`、`get_scene_info`。工具命名可带命名空间；用工具发现查找。确认返回实际 Blender 版本、插件状态与场景信息。空场景不代表失败。
2. 连接错误时只读检查 Blender 是否在运行、可执行文件及版本、已安装 addon、现有 Codex MCP 配置和实际监听。只输出有关配置，避免打印整个含密钥文件。
3. 区分三层：Blender 软件已安装、Blender addon 已启用且服务在运行、Codex MCP 工具真正能读取场景。TCP 可达、后台渲染可运行都不能替代第三层。
4. 本机路径需检测，不硬编码当前作者的盘符。Windows 常见可执行文件在安装目录；`uvx` 不在 PATH 时使用发现的绝对路径。

## 缺失项安装顺序

用户调用此完整工作流包含连接检查与必要配置。存在缺失项时，在当前环境权限允许范围内完成它们，不重复要求用户执行你能完成的操作。用户只要求检测、整理计划、创建 Skill 时不进行安装。

1. 已有 Blender 直接复用。确实没安装则告知缺少软件，再按用户本次授权处理官方安装；不下载来历不明的整合版本。
2. 获取指定 `ahujasid/mcp-for-blender` 仓库或当前官方发布版本。可用 git 克隆到独立工具目录，或使用官方 PyPI 发行包；不得覆盖同名用户目录。记录实际版本或 commit。
3. 按上游要求准备 `uv`/`uvx`。仅在缺失时安装官方工具；不为安装 MCP 更改系统 Python 或全局关闭证书验证。
4. 当前上游支持如下 addon 安装命令；执行前核对当前帮助和 Blender 版本兼容性：

   ```text
   uvx mcp-for-blender install-addon
   ```

   读取命令返回的实际安装路径。已有 addon 则先检查版本与备份行为，避免重复安装。若自动检测失败，可按官方手动方式下载 addon，在 Blender 的偏好设置中安装并启用 **Interface: MCP for Blender**。
5. 打开 Blender，确认 addon 启用，按当前界面启动其 MCP 服务。已有未保存场景先保护；不得为了测试清空场景、杀掉用户 Blender 或覆盖启动文件。
6. 若 Codex 已有可用的同一 MCP 插件/连接，复用，避免另注册一套抢同一服务。只有缺少连接时，按当前 Codex 官方说明注册。上游当前示例：

   ```text
   codex mcp add blender -- uvx mcp-for-blender
   ```

   对应最小配置示例（合并到实际配置，不替换其他服务器）：

   ```toml
   [mcp_servers.blender]
   command = "uvx"
   args = ["mcp-for-blender"]
   ```

   PATH 不可用时换为检测到的完整 uvx 路径。主机与端口从当前配置和 addon 面板核对；仅本机连接，保留原有安全设置，不开放公网监听。不要启用内容遥测、额外生成平台或上传原稿。
7. 新注册工具需要重新载入客户端时，先完成可完成的安装和配置并保存，再明确说明需要重启。不要在当前聊天工作未保存时自行结束 Codex，也不要声称新工具已在当前会话生效。

## 验证与停止条件

- 最终通过 MCP 工具读取真实版本与场景；记录软件/addon 版本、验证时间和结果，不记录密钥。
- 同一错误连续出现时改查具体缺失环节；两次有根据的修复仍失败就说明错误和所需用户动作，保留已完成工作，不无限重装或重复改配置。
- 不为了“连通”关闭防火墙/证书验证、卸载正常插件、修改用户代理或放宽全局审批。

官方依据：

- MCP for Blender 安装与 Codex 配置：https://github.com/ahujasid/mcp-for-blender#installation
- Codex 文档入口：https://developers.openai.com/codex/mcp （若重定向，使用实际官方页面）
