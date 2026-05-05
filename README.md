# Panorama - MC全景图/天空盒生成工具

> 🎬 相关视频：https://www.bilibili.com/video/BV1bbeGzDEe9

将 Minecraft 游戏内截图（6个方向）转换为 **Minecraft 主菜单全景图背景** 或 **OptiFine 天空盒**，还支持将等距圆柱投影图（Equirectangular）转换为 MC 全景图。

## 📦 项目内容

| 文件/目录 | 说明 |
|-----------|------|
| `mc截图转全景图.py` | 带 GUI 的全景图生成工具（将6张方向截图合成为 panorama 资源包） |
| `mc截图转全景图纯终端.py` | 同上，纯命令行版本，适合无 GUI 环境 |
| `等距圆柱投射图转mc全景图/` | 将等距圆柱投影图（360° 全景照片/视频帧）转换为 MC 全景图 |
| `JE1.21.6主菜单全景图资源包示例/` | 示例输出：可直接用于 MC 1.21.6 主菜单背景的资源包 |
| `JE天空盒资源包示例（需要optifine）/` | 示例输出：OptiFine 天空盒资源包 |
| `input/` | 示例输入：6张 MC 截图（前/右/后/左/上/下） |
| `requirements.txt` | Python 依赖 |

## 🛠️ 使用方法

### 1. 安装依赖
```bash
pip install -r requirements.txt
```

### 2. 准备截图
在 Minecraft 中站在你想要的位置，按 **F2** 分别截取 **6个方向** 的截图：
- 🟢 前 (front)
- 🔴 右 (right)
- 🟠 后 (back)
- 🔵 左 (left)
- ⬆ 上 (up)
- ⬇ 下 (down)

将截图放入 `input/` 目录，按上述方向命名（如 `front.png`、`right.png`...）。

### 3. 运行
```bash
python "mc截图转全景图.py"
```

或使用纯终端版：
```bash
python "mc截图转全景图纯终端.py"
```

### 4. 输出
生成的文件在 `output/` 目录，可直接作为 **Minecraft 资源包** 使用。

## 🔄 等距圆柱投影图转换

如果你有 360° 全景照片或视频帧（等距圆柱投影），可以使用 `等距圆柱投射图转mc全景图/` 下的工具：

```bash
cd "等距圆柱投射图转mc全景图"
python "等距圆柱投射图转mc全景图.py"
```

## 📂 输出说明

### 主菜单全景图
将 `output/` 中的 `panorama_0.png` ~ `panorama_5.png` 按资源包结构放置：
```
assets/minecraft/textures/gui/title/background/
```

### OptiFine 天空盒
将生成的天空盒图片放入：
```
assets/minecraft/optifine/sky/world0/
```

## 📋 依赖
- Python 3.7+
- Pillow
- numpy
- PyQt5（仅 GUI 版本需要）

---

> 作者：[得酥君](https://space.bilibili.com/1454977233)  
> 视频教程：https://www.bilibili.com/video/BV1bbeGzDEe9
