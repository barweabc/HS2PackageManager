from enum import Enum

class PackageStatus(Enum):
    """资源包安装状态"""
    NORMAL = "normal"  # 正式安装：文件完整且未被覆盖
    CONFLICT = "conflict"  # 冲突/残留：部分文件已被其他包覆盖或修改，卸载时保留
    DRY_RUN = "dry_run"  # 模拟运行：仅产生元数据记录，不包含实际物理文件


class PackageType(Enum):
    """资源包类型"""
    CHARACTER = "人物"
    DHH = "DHH光影"
    OTHER = "其他"
    ALL = "全部"  # 仅用于筛选


class GUIConfigKey(Enum):
    """GUI 配置项键名"""
    SHOW_CARD_VIEW = "show_card_view"  # 列表页是否显示人物卡预览
    SHOW_IMPORT_PREVIEW = "show_import_preview"  # 导入页是否显示人物卡预览
    SELECTED_TAB = "selected_tab"  # 上次选中的标签页索引 (0: 导入, 1: 列表)
