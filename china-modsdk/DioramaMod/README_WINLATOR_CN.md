# 无 Windows 电脑的 Android 测试方案（Winlator）

如果没有 Windows 电脑，可以在 Android 上尝试运行官方 MCStudio：

1. 从 Winlator 官方发布页安装适合手机架构的版本（不要使用来路不明的修改版）。
2. 在 Winlator 中创建 Windows 7/10、32-bit 前缀，给足磁盘空间。
3. 从网易官方开发工作台入口下载 `MCStudio_1.1.0.20124.exe`：
   `https://adl.netease.com/d/g/mc/c/dev`
4. 在 Winlator 中运行安装器并登录开发者账号。
5. 打开「工具箱 → 手机测试版启动器」，让工作台生成测试客户端二维码。
6. 手机扫码安装官方测试客户端；在工作台中导入本目录工程或使用 `Diorama-China-ModSDK-TestBundle`。

## 现实限制

- MCStudio 是旧版 x86/.NET/WPF/CEFSharp 程序，Winlator/Wine 兼容性不保证；可能卡在登录、WPF、CEF 或证书校验。
- 本项目已在 Linux 上用 Wine 做过尝试，但 MCStudio 因 Mono/WPF 类型解析和证书读取崩溃，不能宣称 Winlator 一定可用。
- Winlator 只能提供免费实验路径，不能绕过网易开发者账号、自测平台或测试客户端授权。
- 如果 Winlator 失败，仍需借用一次 Windows 电脑；无需购买，学校/朋友/公共电脑都可以。

本项目不会分发网易 MCStudio 或官方测试客户端，只引用官方官方下载地址。
