# 中国版 ModSDK 测试导入

本目录是网易 MCStudio/开发工作台导入用的 `DioramaMod` 工程根目录。

## 官方手机自测流程

网易官方教程说明：MCStudio 的「工具箱 → 手机测试版启动器」会打开开发者内容管理工具二维码；手机扫描后安装自测客户端。作品在 MCStudio「作品库 → 基岩版组件 → 发布」后，可通过「机审自测」或「免机审自测」上传到自测平台，再由手机测试客户端下载自己的组件。

1. 在 Windows 上安装 MCStudio，并登录已审核的开发者账号。
2. 导入本目录 `DioramaMod/`，或将本目录作为 ModSDK 工程内容合并到工作台新建项目。
3. 目录结构已对齐官方 ModSDK 工程：`behavior_packs/diorama_behavior_pack/` 与 `resource_packs/diorama_resource_pack/`；脚本入口是 `dioramaScripts/modMain.py`。
4. 使用「工具箱 → 手机测试版启动器」安装中国版手机测试客户端。
5. 将工程发布为基岩版组件，选择「机审自测」或「免机审自测」。
6. 在手机测试客户端用同一开发者账号登录，在资源中心下载自己的自测组件。
7. 进入测试世界，启用行为包/资源包，检查 HUD、路径点、地图和雷达。
8. 打开地图界面后点「3D」按钮，验证官方 PaperDoll 块几何层是否生效；失败会回退到贴图地图。

包清单版本为 `0.4.0`；每次重新发布前需要再次提升版本号，否则平台机审会拒绝。

> 当前环境没有 Windows、MCStudio GUI 或网易开发者账号，因此没有代替用户执行登录、上传、二维码下载和手机安装。工程已按官方样例对齐，但 `RegisterUI`/客户端 UI 路径仍需在目标工作台版本中实测。

## 关键 API 依赖

工程会用到这些官方接口，缺少时会安全回退而不是报错：

| 接口 | 用途 | 缺失时 |
|---|---|---|
| `GetViewBinderCls` | HUD 坐标/方位/群系数据绑定 | 退回 `SetText` |
| `GetBlockPaletteBetweenPos` / `SerializeBlockPalette` | 服务端生成地图调色板 | 返回 `geometry_unavailable` |
| `DeserializeBlockPalette` / `CombineBlockPaletteToGeometry` | 客户端生成立体几何 | 退回贴图地图 |
| `PaperDollUIControl.RenderBlockGeometryModel` | 在 UI 内渲染块几何 | 退回贴图地图 |
| `CreateVirtualWorld` / `ModelCreate*` | 可选虚拟世界模式 | 功能不可用，不崩溃 |
| `CreateMicroBlockResStr` | 预烘焙微缩快照 | 返回原因字符串 |

## 没有 Windows 时

最短路径是租用临时 Windows 云桌面，用远程桌面完成上述一次性登录、构建和上传。无需在手机上逆向客户端，也不需要修改网易原始二进制。
