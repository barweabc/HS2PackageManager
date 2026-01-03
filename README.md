# HS2 Package Manager (HS2 资源包管理工具)

一个为 Honey Select 2 设计的优雅、模块化的资源包管理工具。支持人物卡、插件及各类 MOD 的安装、卸载与冲突检测。

## ✨ 特性

- **智能安装**：自动识别资源包结构，支持 `mods`、`UserData` 和 `abdata` 路径自动映射。
- **冲突检测**：基于文件大小和时间戳的冲突检测，确保卸载时不会误删被其他包覆盖的文件。
- **人物卡预览**：内置人物卡预览功能，支持在导入和列表查看时实时显示角色缩略图。
- **模拟运行**：支持 Dry Run 模式，在不实际移动文件的情况下生成安装记录。
- **模块化设计**：采用解耦的架构，逻辑与界面分离，易于扩展。
- **元数据管理**：完整的 JSON 元数据记录，追踪每一个安装的文件。

## 🚀 快速开始

### 环境要求
- Python 3.13+
- 依赖项：`Pillow` (用于图片预览)

### 安装依赖
```bash
pip install pillow
# 或者使用 uv
uv sync
```

### 运行程序
```bash
python main.py
```

## 📂 项目结构

- [main.py](main.py): 程序入口。
- [hspm/](hspm/): 核心代码包。
    - [hspm/manager.py](hspm/manager.py): 核心逻辑（安装/卸载/配置）。
    - [hspm/gui.py](hspm/gui.py): Tkinter 界面实现。
    - [hspm/models.py](hspm/models.py): 枚举与数据模型。
- [pyproject.toml](pyproject.toml): 项目元数据与依赖配置。

## 🛠 配置说明

配置文件通常位于 `~/.config/HS2PackageManager/config.json`。
- `app_root`: 游戏根目录。
- `meta_dir`: 元数据存储目录。

## 📦 打包

项目包含 [build.bat](build.bat)，可使用 PyInstaller 进行一键打包。

---
*Made with ❤️ for the HS2 Community.*
