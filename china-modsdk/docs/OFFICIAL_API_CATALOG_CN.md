# 中国版 ModSDK 官方文档目录与 Diorama 适配结论

> 采集日期：2026-10-19。以网易官方文档为准；所有接口仍需在目标开发工作台/手机自测包中验证。

## 文档入口与版本

- [API 入口](https://mc.163.com/m/dev/apidocs.html)（JS 目录壳）
- [ModAPI 索引](https://mc.163.com/dev/mcmanual/mc-dev/mcdocs/1-ModAPI/接口/Api索引表.html?catalog=1)
- [事件索引](https://mc.163.com/dev/mcmanual/mc-dev/mcdocs/1-ModAPI/事件/事件索引表.html?catalog=1)
- [UI 数据绑定](https://mc.163.com/dev/mcmanual/mc-dev/mcguide/18-界面与交互/70-UI数据绑定.html?catalog=1)
- [方块组合/微缩方块](https://mc.163.com/dev/mcmanual/mc-dev/mcdocs/1-ModAPI/接口/世界/方块组合.html?catalog=1)
- [渲染 API](https://mc.163.com/dev/mcmanual/mc-dev/mcdocs/1-ModAPI/接口/渲染.html?catalog=1)
- [ShaderSDK](https://mc.163.com/dev/mcmanual/mc-dev/mcdocs/4-ShaderSDK/0-概述.html)
- [测试与发布指南](https://mc.163.com/m/dev/mcmanual/mc-dev/mcguide/30-测试/)

当前 Android 中国版适配基线：ModAPI 3.9 / Bedrock 1.21.120。3.10 为 Beta 线，不能作为默认目标。

## 对 Diorama 最有价值的官方能力

### 1. 方块数据与几何

- `GetBlockPaletteBetweenPos` / `GetBlockPaletteFromPosList`：服务端/客户端读取区域方块调色板。
- `SerializeBlockPalette` / `DeserializeBlockPalette`：适合服务端到客户端同步压缩后的地图数据。
- `CombineBlockPaletteToGeometry`：客户端把调色板合并为可渲染几何体。
- `CreateMicroBlockResStr(identifier, start, end, colorMap, isMerge, icon)`：生成微缩方块资源；最大微缩体积 64×64×64，单个微缩方块最大 4×4×4；只包含方块、不包含生物。
- 微缩资源必须写入文件并放入行为包/资源包约定目录，且 PE 大型微缩数据会增加初始加载时间。

**Diorama 计划**：近处使用 2D HUD tile/grid；全屏地图使用分块微缩/几何体快照，避免每帧重新生成。

### 2. 客户端 UI

- `RegisterUI` → `CreateUI` → `ScreenNode` 生命周期。
- `GetViewBinderCls` / `binding` / `binding_collection`：JSON UI 的视图绑定。
- `stack_grid` 支持集合绑定，适合 16×16 地图格子和雷达图标。
- `bindEntityId` / `bindWorldPosition` 可把 HUD/世界标签绑定到实体或坐标。
- 官方建议资源池和分批更新；同屏批量增删 UI 会卡顿。

**Diorama 计划**：用 collection binding 更新 16×16 或 32×32 低分辨率地图；路径点/雷达使用少量复用控件。

### 3. 客户端绘制与虚拟世界

- `DrawingCompClient`：Box/Line/Arrow/Circle/Sphere/Text 世界空间形状，可设置颜色、优先级、半径和分段。
- `VirtualWorldCreate`：全局只能创建一个虚拟世界；支持天空、相机、FOV/缩放和模型。
- `ModelCreateMinecraftObject`：虚拟世界中创建原版模型。
- `CreateFreeModel`：创建自由模型，必须设置合理包围盒，否则可能被视锥剔除。
- `BindModel` / `MoveToVirtualWorld`：将模型、文本板、粒子等放入虚拟世界。

**Diorama 计划**：全屏地图模式切换 VirtualWorld；雷达和路径点用 Drawing/Text；不把虚拟世界冒充为 HUD 纹理。

### 4. 后处理与 ShaderSDK

- ModAPI 后处理：预设渐晕、模糊、色彩、景深、镜头效果；自定义多 pass 的 0/1/2 纹理槽保留给上一 pass/原始颜色/深度，自定义槽为 3–7。
- ShaderSDK CSS r21u12：RenderDragon Custom Surface Shader；花式渲染器有效输出为 Albedo/Alpha，灵动视效增加 PBR 字段。
- CSS 适合颜色分级、雾、材质和表面效果；官方没有提供把完整独立 3D 场景直接 blit 到 HUD 纹理的接口。

### 5. 事件、存储和通信

- `ListenForEvent` / `NotifyToClient` / `NotifyToServer`：客户端/服务端同步地图、雷达和路径点。
- 客户端 `CreateConfigClient`：本地配置/路径点存储，配置名只能使用字母、数字和下划线，建议加命名空间。
- Apollo 的 MySQL/Redis/Mongo 是网络服能力，不用于普通单机 ModSDK。

## 当前工程对应关系

| 官方能力 | 工程位置 | 当前状态 |
|---|---|---|
| 投影/DDA/光照/LOD/MipMap | `DioramaMod/.../modCore/` | 已有，离线测试 |
| HUD grid | `diorama_resource_pack/ui/` | 已有模板，需 ViewBinder 真机适配 |
| 服务端方块采样 | `modServer/engine/block_source.py` | 已有适配边界 |
| 微缩方块快照 | 待接入 | 下一阶段重点 |
| VirtualWorld 全屏地图 | 待接入 | 下一阶段重点 |
| DrawingComp 雷达/路径点 | 部分组件已有 | 需真实客户端验证 |
| ShaderSDK | 未接入 | 后处理验证后再接 |

## 关键限制

官方 API 能把实现推进到“HUD 地图 + 全屏立体快照/虚拟世界”的高相似度，但没有文档证明可以把独立 3D 场景实时渲染到 HUD 小窗纹理。因此不把这个缺口描述成已解决。
