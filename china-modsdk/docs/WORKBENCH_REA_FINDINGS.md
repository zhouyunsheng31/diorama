# MCStudio / ModSDK 静态逆向初步结果

目标：网易官方下载的 `MCStudio_1.1.0.20124.exe`，未执行，仅做本地静态分析。

- 下载入口：官方开发者页面的 `adl.netease.com/d/g/mc/c/dev`。
- 安装包 SHA-256：`3ebcfc6c04b4b8b4f6a402fe2c3fe0529b0d5462cf022b2cbcc7f0a1ee061ac1`。
- 使用 REA 提取 Inno Setup 内容后，发现 `app/data/apollo/` 样例工程、`deploy_x86/` Python 2.7 部署工具、ModSDK UI 样例和资源包模板。
- 典型入口是 `from common.mod import Mod`，而不是 `mod.common.mod`。
- 客户端 API 入口是 `client.extraClientApi`，服务端 API 入口是 `server.extraServerApi`。
- 官方样例通过 `RegisterSystem(namespace, name, class_path)` 注册系统；客户端 UI 通过 `RegisterUI(namespace, ui_key, ScreenNodeClass, "namespace.json_basename")`，再 `CreateUI`。
- 官方 ScreenNode 使用 `GetScreenNodeCls()`、`InitScreen()`、`AddTouchEventHandler()`、`SetText()`、`SetVisible()`、`SetSprite()` 等接口。
- 官方示例确认 Python 2.7 语法和 `common.mod`/`client`/`server` 命名空间。
- 样例包含真实的 `_ui_defs.json`、HUD/UI 屏幕、行为包和资源包布局，可作为本项目工作台适配依据。

本次结果只说明接口和文件结构的静态证据，不代表已运行 MCStudio 或中国版客户端。没有做反作弊、登录、DRM 或授权绕过；下一步仍需在合法的工作台/测试环境验证实际签名和 UI 路径。
