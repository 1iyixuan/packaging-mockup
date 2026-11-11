# 为接收方安装“包装效果图”Skill

用户要求安装本仓库的“包装效果图”时，按以下步骤操作。只安装完整技能，不在安装阶段执行客户建模或网站部署。

1. 从本仓库的 [最新发行版](https://github.com/1iyixuan/packaging-mockup/releases/latest) 下载 `packaging-mockup-v<版本>.zip` 和同版 `SHA256SUMS`，核对 ZIP 的 SHA-256。校验失败时停止。
2. 解压到独立临时目录。确认顶层是 `packaging-mockup`，内部直接含 `SKILL.md`、`VERSION`、`agents/openai.yaml`、`scripts`、`references` 及完整 `assets/viewer`（包括 vendor 库、许可证和来源记录）。
3. 读取 `SKILL.md` 和 UI 元数据，确认技术标识 `packaging-mockup`、显示名称“包装效果图”，检查相对引用和实际文件完整性。
4. 检测当前接收设备的客户端和个人技能目录。按照该客户端的官方文档安装；常见个人目录是 `~/.agents/skills`，已有 Codex 环境也可能使用 `$CODEX_HOME/skills` 或 `~/.codex/skills`。不要复制发送方的个人路径，也不要为“兼容”在多个扫描位置重复安装。
5. 已有同名技能时检查版本并保留备份；不要静默覆盖用户修改。将整个文件夹安装到一个受支持目录，确保实际路径为 `技能目录/packaging-mockup/SKILL.md`。
6. 确认客户端发现该技能。支持 `@` 的桌面端应能搜索到“包装效果图”；CLI／IDE 可使用 `$packaging-mockup`。列表未更新时说明重新加载要求，不把源码已复制冒充界面已验证。
7. 报告实际安装位置、版本、发现结果及无法完成项。首次实际制作再按 Skill 的第 0 步检查 Blender 软件、addon、MCP 配置与只读场景调用；不要将仅可运行后台 Blender 当成连接成功。

默认保持既有账户、安全设置、场景和其他技能。安装此技能不代表用户已授权发布客户原稿、创建付费服务或公开部署。
