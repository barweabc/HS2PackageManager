import os
import re
import json
import threading
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from .manager import PackageManager
from .models import PackageStatus, PackageType, GUIConfigKey

class AddPackageGUI:
    def __init__(self, root):
        self.root = root
        self.manager = PackageManager()
        self.root.title(f"HS2 资源包管理工具 v{self.manager.version}")
        self.root.geometry("1600x900")

        config = self.manager.config
        self.config_exists = bool(config.get("app_root") and config.get("meta_dir"))

        # 变量
        self.app_root = tk.StringVar(value=config.get("app_root", ""))
        self.meta_dir = tk.StringVar(value=config.get("meta_dir", ""))
        self.source_path = tk.StringVar()
        self.pkg_type = tk.StringVar(value=PackageType.CHARACTER.value)
        self.name = tk.StringVar()
        self.sid = tk.StringVar()
        self.dry_run = tk.BooleanVar(value=False)
        self.create_meta_on_dry_run = tk.BooleanVar(value=False)
        self.original_order = []

        # 列表页筛选变量
        self.list_filter_type = tk.StringVar(value=PackageType.CHARACTER.value)
        gui_config = config.get("gui", {})
        self.show_card_view = tk.BooleanVar(
            value=gui_config.get(GUIConfigKey.SHOW_CARD_VIEW.value, False)
        )

        # 导入页预览变量
        self.show_import_preview = tk.BooleanVar(
            value=gui_config.get(GUIConfigKey.SHOW_IMPORT_PREVIEW.value, False)
        )
        self.initial_tab = gui_config.get(GUIConfigKey.SELECTED_TAB.value, 0)

        self.last_hover = None  # 记录上次悬停的状态 (item_id, part)

        self.setup_ui()

        # 延迟初始化界面状态，确保窗口已渲染
        self.root.after(100, self.initialize_ui_state)
        # 延迟检查配置，确保窗口已初始化后再弹窗
        self.root.after(500, self.check_config_on_startup)

    def initialize_ui_state(self):
        """初始化界面状态（在窗口渲染后执行）"""
        self.on_type_change()
        self.on_dry_run_change()
        self.on_list_filter_change()

    def check_config_on_startup(self):
        if not self.config_exists:
            messagebox.showwarning(
                "配置缺失",
                f"未找到配置文件或配置为空: {self.manager.config_path}\n请确保文件存在并包含 app_root 和 meta_dir。",
            )
        else:
            # 确保 mods/MyMods 文件夹存在
            app_root = self.app_root.get()
            if app_root:
                my_mods_dir = Path(app_root) / "mods" / "MyMods"
                if not my_mods_dir.exists():
                    try:
                        my_mods_dir.mkdir(parents=True, exist_ok=True)
                        print(f"已创建目录: {my_mods_dir}")
                    except Exception as e:
                        print(f"创建目录失败 {my_mods_dir}: {e}")

    def open_config_dir(self):
        if self.manager.config_dir.exists():
            os.startfile(self.manager.config_dir)
        else:
            messagebox.showerror("错误", f"配置目录不存在: {self.manager.config_dir}")

    def open_meta_dir(self):
        meta_path = Path(self.meta_dir.get())
        if meta_path.exists():
            os.startfile(meta_path)
        else:
            messagebox.showerror("错误", f"元数据目录不存在: {meta_path}")

    def on_tab_changed(self, event):
        selected_tab = self.notebook.index(self.notebook.select())
        self.save_settings()
        if selected_tab == 1:  # 资源包列表 Tab 的索引
            self.refresh_package_list()

    def refresh_package_list(self):
        # 清空现有数据
        for item in self.tree.get_children():
            self.tree.delete(item)

        packages = self.manager.get_package_list(self.meta_dir.get())
        filter_type = self.list_filter_type.get()

        for pkg in packages:
            # 筛选逻辑
            if filter_type != PackageType.ALL.value and pkg.get("type") != filter_type:
                continue

            date_display = pkg["created_at"]
            try:
                dt = datetime.fromisoformat(pkg["created_at"])
                date_display = dt.strftime("%Y-%m-%d %H:%M:%S")
            except:
                pass

            status_val = pkg.get("status")
            if status_val == PackageStatus.DRY_RUN.value:
                status_display = "模拟"
            elif status_val == PackageStatus.CONFLICT.value:
                # 冲突状态必然是正式安装产生的
                status_display = "正式 (残留)"
            else:
                status_display = "正式"

            self.tree.insert(
                "",
                "end",
                values=(
                    pkg["name"],
                    pkg["sid"],
                    pkg.get("type", "未知"),
                    date_display,
                    pkg["file_count"],
                    status_display,
                    "👁查看 🗑删除",
                    pkg["meta_path"],
                ),
            )

        # 记录原始顺序
        self.original_order = list(self.tree.get_children(""))

        # 默认选中第一行
        children = self.tree.get_children()
        if children:
            self.tree.selection_set(children[0])
            self.tree.focus(children[0])
            self.tree.see(children[0])
            self.on_tree_select()
        else:
            # 如果没有数据，清空预览
            self.list_preview_label.config(image="", text="列表为空")

    def on_tree_click(self, event):
        """处理表格单击事件，模拟按钮点击"""
        region = self.tree.identify_region(event.x, event.y)
        if region == "cell":
            column = self.tree.identify_column(event.x)
            item_id = self.tree.identify_row(event.y)
            if column == "#7":  # 操作列
                values = self.tree.item(item_id, "values")
                if not values:
                    return
                meta_path = values[7]
                bbox = self.tree.bbox(item_id, column)
                if bbox:
                    cell_x = event.x - bbox[0]
                    cell_width = bbox[2]
                    if cell_x < cell_width / 2:
                        # 查看逻辑
                        if os.path.exists(meta_path):
                            os.startfile(meta_path)
                        else:
                            messagebox.showerror("错误", f"文件不存在: {meta_path}")
                    else:
                        # 删除逻辑
                        if messagebox.askyesno(
                            "确认删除",
                            f"确定要删除资源包 {values[0]} 吗？\n这将删除所有已安装的文件和目录。",
                        ):
                            success, msg = self.manager.delete_package(
                                meta_path, self.app_root.get()
                            )
                            if success:
                                messagebox.showinfo("成功", msg)
                                self.refresh_package_list()
                            else:
                                messagebox.showerror("错误", msg)

    def reset_tree_hover(self):
        """重置表格的悬停高亮状态"""
        if self.last_hover:
            item_id, _ = self.last_hover
            if self.tree.exists(item_id):
                vals = list(self.tree.item(item_id, "values"))
                vals[6] = "👁查看 🗑删除"
                self.tree.item(item_id, values=vals)
            self.last_hover = None

    def on_tree_motion(self, event):
        """鼠标移动时改变光标样式并实现按钮高亮效果"""
        region = self.tree.identify_region(event.x, event.y)
        item_id = self.tree.identify_row(event.y)
        column = self.tree.identify_column(event.x)

        current_state = None

        if region == "cell" and column == "#7":
            bbox = self.tree.bbox(item_id, column)
            if bbox:
                cell_x = event.x - bbox[0]
                cell_width = bbox[2]
                part = "view" if cell_x < cell_width / 2 else "delete"
                current_state = (item_id, part)
                self.tree.configure(cursor="hand2")
        else:
            self.tree.configure(cursor="")

        # 如果状态发生变化，更新 UI
        if current_state != self.last_hover:
            # 重置旧状态
            if self.last_hover:
                old_item, _ = self.last_hover
                if self.tree.exists(old_item):
                    vals = list(self.tree.item(old_item, "values"))
                    vals[6] = "👁查看 🗑删除"
                    self.tree.item(old_item, values=vals)

            # 设置新状态
            if current_state:
                new_item, part = current_state
                vals = list(self.tree.item(new_item, "values"))
                if part == "view":
                    vals[6] = "【👁查看】 🗑删除"
                else:
                    vals[6] = "👁查看 【🗑删除】"
                self.tree.item(new_item, values=vals)

            self.last_hover = current_state

    def on_tree_double_click(self, event):
        """处理表格双击事件"""
        region = self.tree.identify_region(event.x, event.y)
        if region == "cell":
            column = self.tree.identify_column(event.x)
            item_id = self.tree.identify_row(event.y)
            values = self.tree.item(item_id, "values")
            if values:
                # path 列的索引为 7
                meta_path = values[7]

                if column != "#7":
                    # 双击非操作列默认执行查看
                    if os.path.exists(meta_path):
                        os.startfile(meta_path)
                    else:
                        messagebox.showerror("错误", f"文件不存在: {meta_path}")

    def treeview_sort_column(self, col, state):
        """表格排序逻辑: asc -> desc -> original"""
        columns = {
            "name": "资源包名称",
            "sid": "SID",
            "type": "类型",
            "date": "安装日期",
            "files": "文件数量",
            "status": "状态",
        }

        if state == "original":
            # 恢复原始顺序
            for index, k in enumerate(self.original_order):
                self.tree.move(k, "", index)

            # 重置所有表头图标和命令
            for c_id, c_name in columns.items():
                self.tree.heading(
                    c_id,
                    text=c_name,
                    command=lambda c=c_id: self.treeview_sort_column(c, "asc"),
                )
            return

        # 获取所有行的数据
        l = [(self.tree.set(k, col), k) for k in self.tree.get_children("")]

        reverse = state == "desc"

        # 根据列类型进行排序
        if col == "files":
            l.sort(
                key=lambda t: int(t[0]) if str(t[0]).isdigit() else 0, reverse=reverse
            )
        else:
            l.sort(reverse=reverse)

        # 重新排列项目
        for index, (val, k) in enumerate(l):
            self.tree.move(k, "", index)

        # 更新表头图标和下一次点击的命令
        next_state = "desc" if state == "asc" else "original"

        for c_id, c_name in columns.items():
            if c_id == col:
                icon = " ▲" if state == "asc" else " ▼"
                self.tree.heading(
                    c_id,
                    text=c_name + icon,
                    command=lambda c=c_id: self.treeview_sort_column(c, next_state),
                )
            else:
                # 其他列重置为初始状态
                self.tree.heading(
                    c_id,
                    text=c_name,
                    command=lambda c=c_id: self.treeview_sort_column(c, "asc"),
                )

    def setup_ui(self):
        padding = {"padx": 10, "pady": 5}

        # 设置样式以增大 Tab 标签
        style = ttk.Style()
        # padding 参数: [左, 上, 右, 下]
        style.configure("TNotebook.Tab", padding=[12, 5], font=("Microsoft YaHei", 10))
        # 提示文本样式
        style.configure("Hint.TLabel", foreground="gray", font=("Microsoft YaHei", 9))

        # 创建 Notebook (Tab 控件)
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill="both", expand=True, padx=5, pady=5)

        # 1. "资源包列表" Tab
        self.tab_list = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_list, text="资源包列表")

        # 2. "导入资源包" Tab
        self.tab_import = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_import, text="导入资源包")

        # 资源包列表筛选工具栏
        frame_filter = ttk.Frame(self.tab_list)
        frame_filter.pack(fill="x", **padding)
        ttk.Label(frame_filter, text="筛选类型:").pack(side="left", padx=5)

        for t in [PackageType.ALL, PackageType.CHARACTER, PackageType.OTHER]:
            ttk.Radiobutton(
                frame_filter,
                text=t.value,
                variable=self.list_filter_type,
                value=t.value,
                command=self.on_list_filter_change,
            ).pack(side="left", padx=10)

        self.cb_list_preview = ttk.Checkbutton(
            frame_filter,
            text="显示人物卡预览",
            variable=self.show_card_view,
            command=self.on_list_preview_toggle,
        )
        # 初始状态由 on_list_filter_change 决定

        # 资源包列表工具栏
        frame_list_tools = ttk.Frame(self.tab_list)
        frame_list_tools.pack(fill="x", **padding)
        ttk.Button(
            frame_list_tools, text="刷新列表", command=self.refresh_package_list
        ).pack(side="left", padx=5)
        ttk.Button(
            frame_list_tools, text="打开元数据目录", command=self.open_meta_dir
        ).pack(side="left", padx=5)

        # 列表主区域
        self.frame_list_main = ttk.Frame(self.tab_list)
        self.frame_list_main.pack(fill="both", expand=True, **padding)

        # 左侧表格容器
        self.frame_tree = ttk.Frame(self.frame_list_main)
        self.frame_tree.pack(side="left", fill="both", expand=True)

        # 资源包列表表格
        self.tree = ttk.Treeview(
            self.frame_tree,
            columns=(
                "name",
                "sid",
                "type",
                "date",
                "files",
                "status",
                "action",
                "path",
            ),
            show="headings",
        )
        self.tree.heading(
            "name",
            text="资源包名称",
            command=lambda: self.treeview_sort_column("name", "asc"),
        )
        self.tree.heading(
            "sid", text="SID", command=lambda: self.treeview_sort_column("sid", "asc")
        )
        self.tree.heading(
            "type",
            text="类型",
            command=lambda: self.treeview_sort_column("type", "asc"),
        )
        self.tree.heading(
            "date",
            text="安装日期",
            command=lambda: self.treeview_sort_column("date", "asc"),
        )
        self.tree.heading(
            "files",
            text="文件数量",
            command=lambda: self.treeview_sort_column("files", "asc"),
        )
        self.tree.heading(
            "status",
            text="状态",
            command=lambda: self.treeview_sort_column("status", "asc"),
        )
        self.tree.heading("action", text="操作 (查看 | 删除)")

        # 设置列宽
        self.tree.column("name", width=200)
        self.tree.column("sid", width=250)
        self.tree.column("type", width=80, anchor="center")
        self.tree.column("date", width=200)
        self.tree.column("files", width=100, anchor="center")
        self.tree.column("status", width=80, anchor="center")
        self.tree.column("action", width=120, anchor="center")
        self.tree.column("path", width=0, stretch=False)  # 隐藏路径列

        # 只显示需要的列
        self.tree["displaycolumns"] = (
            "name",
            "sid",
            "type",
            "date",
            "files",
            "status",
            "action",
        )

        # 滚动条
        scrollbar = ttk.Scrollbar(
            self.frame_tree, orient="vertical", command=self.tree.yview
        )
        self.tree.configure(yscrollcommand=scrollbar.set)

        self.tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # 右侧预览容器
        self.frame_list_preview = ttk.LabelFrame(
            self.frame_list_main, text="人物卡预览"
        )
        self.list_preview_label = ttk.Label(self.frame_list_preview, text="未选择项目")
        self.list_preview_label.pack(padx=10, pady=10)

        # 绑定双击事件 (保留双击查看功能)
        self.tree.bind("<Double-1>", self.on_tree_double_click)
        # 绑定单击事件 (用于操作列的按钮模拟)
        self.tree.bind("<ButtonRelease-1>", self.on_tree_click)
        # 绑定鼠标移动事件 (用于改变光标和高亮)
        self.tree.bind("<Motion>", self.on_tree_motion)
        # 绑定鼠标离开事件 (重置高亮)
        self.tree.bind("<Leave>", lambda e: self.reset_tree_hover())
        # 绑定选择事件
        self.tree.bind("<<TreeviewSelect>>", self.on_tree_select)

        # 绑定标签页切换事件，自动刷新列表
        self.notebook.bind("<<NotebookTabChanged>>", self.on_tab_changed)

        # 恢复上次选择的标签页
        try:
            self.notebook.select(self.initial_tab)
        except:
            pass

        # --- 导入资源包页面的内容 ---
        # 基础配置 (仅显示)
        frame_config = ttk.LabelFrame(self.tab_import, text="基础配置")
        frame_config.pack(fill="x", **padding)
        frame_config.columnconfigure(1, weight=1)

        ttk.Label(frame_config, text="游戏根目录:").grid(
            row=0, column=0, sticky="w", **padding
        )
        ttk.Entry(frame_config, textvariable=self.app_root, state="readonly").grid(
            row=0, column=1, sticky="ew", **padding
        )

        ttk.Label(frame_config, text="元数据目录:").grid(
            row=1, column=0, sticky="w", **padding
        )
        ttk.Entry(frame_config, textvariable=self.meta_dir, state="readonly").grid(
            row=1, column=1, sticky="ew", **padding
        )

        ttk.Button(
            frame_config, text="打开配置目录", command=self.open_config_dir
        ).grid(row=0, column=2, rowspan=2, **padding)

        # 选择源目录
        frame_source = ttk.LabelFrame(self.tab_import, text="选择资源包")
        frame_source.pack(fill="x", padx=10, pady=2)

        # 使用两栏布局：左侧输入，右侧预览
        self.frame_import_main = ttk.Frame(frame_source)
        self.frame_import_main.pack(fill="x", expand=True)

        # 左侧输入栏
        self.frame_import_left = ttk.Frame(self.frame_import_main)
        self.frame_import_left.pack(side="left", fill="x", expand=True)

        # 第一行：路径选择
        frame_path = ttk.Frame(self.frame_import_left)
        frame_path.pack(fill="x", padx=5, pady=2)
        ttk.Entry(frame_path, textvariable=self.source_path).pack(
            side="left", fill="x", expand=True, padx=5
        )
        ttk.Button(frame_path, text="浏览...", command=self.browse_source).pack(
            side="right", padx=5
        )

        # 第二行：资源包类型选择
        frame_type = ttk.Frame(self.frame_import_left)
        frame_type.pack(fill="x", padx=5, pady=2)
        ttk.Label(frame_type, text="资源包类型:").pack(side="left", padx=5)

        ttk.Radiobutton(
            frame_type,
            text=PackageType.CHARACTER.value,
            variable=self.pkg_type,
            value=PackageType.CHARACTER.value,
            command=self.on_type_change,
        ).pack(side="left", padx=10)
        ttk.Radiobutton(
            frame_type,
            text=PackageType.OTHER.value,
            variable=self.pkg_type,
            value=PackageType.OTHER.value,
            command=self.on_type_change,
        ).pack(side="left", padx=10)

        # 第三行：识别信息 (动态显示)
        self.frame_info = ttk.Frame(self.frame_import_left)
        # 初始状态由 on_type_change 决定

        self.frame_info.columnconfigure(1, weight=1)

        ttk.Label(self.frame_info, text="角色名称:").grid(
            row=0, column=0, sticky="w", padx=5, pady=2
        )
        self.name_entry = ttk.Entry(self.frame_info, textvariable=self.name)
        self.name_entry.grid(row=0, column=1, sticky="ew", padx=5, pady=2)
        ttk.Label(self.frame_info, text="例如: 霜雪", style="Hint.TLabel").grid(
            row=1, column=1, sticky="w", padx=10, pady=(0, 2)
        )

        ttk.Label(self.frame_info, text="角色 SID:").grid(
            row=2, column=0, sticky="w", padx=5, pady=2
        )
        self.sid_entry = ttk.Entry(self.frame_info, textvariable=self.sid)
        self.sid_entry.grid(row=2, column=1, sticky="ew", padx=5, pady=2)
        ttk.Label(
            self.frame_info, text="例如: HS2ChaF_20251105165109590", style="Hint.TLabel"
        ).grid(row=3, column=1, sticky="w", padx=10, pady=(0, 2))

        self.cb_import_preview = ttk.Checkbutton(
            self.frame_info,
            text="显示人物卡预览",
            variable=self.show_import_preview,
            command=self.on_import_preview_toggle,
        )
        self.cb_import_preview.grid(row=4, column=1, sticky="w", padx=5, pady=2)

        # 右侧预览栏
        self.frame_import_right = ttk.Frame(self.frame_import_main)
        self.frame_import_right.pack(side="right", padx=10, pady=0)
        
        self.import_preview_label = ttk.Label(self.frame_import_right, text="无预览图")
        self.import_preview_label.pack()

        # 选项
        frame_opts = ttk.Frame(self.tab_import)
        frame_opts.pack(fill="x", **padding)
        ttk.Checkbutton(
            frame_opts,
            text="模拟运行 (不实际复制文件)",
            variable=self.dry_run,
            command=self.on_dry_run_change,
        ).pack(side="left")
        self.cb_create_meta = ttk.Checkbutton(
            frame_opts,
            text="是否为模拟运行创建 meta 文件",
            variable=self.create_meta_on_dry_run,
        )
        # 初始状态由 on_dry_run_change 决定

        # 日志输出
        frame_log = ttk.LabelFrame(self.tab_import, text="运行日志")
        frame_log.pack(fill="both", expand=True, **padding)

        self.log_text = tk.Text(frame_log, height=10, state="disabled")
        self.log_text.pack(fill="both", expand=True, padx=5, pady=5)

        # 操作按钮
        frame_actions = ttk.Frame(self.tab_import)
        frame_actions.pack(pady=10)
        
        ttk.Button(frame_actions, text="开始安装", command=self.start_process).pack(
            side="left", padx=10
        )
        ttk.Button(frame_actions, text="清除日志", command=self.clear_log).pack(
            side="left", padx=10
        )

    def clear_log(self):
        """清除运行日志"""
        self.log_text.config(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.config(state="disabled")

    def on_type_change(self, event=None):
        if self.pkg_type.get() == PackageType.CHARACTER.value:
            self.frame_info.pack(fill="x", padx=5, pady=2)
            self.on_import_preview_toggle(save=False)
        else:
            self.frame_info.pack_forget()

    def on_list_filter_change(self):
        """列表筛选类型改变时触发"""
        if self.list_filter_type.get() == PackageType.CHARACTER.value:
            self.cb_list_preview.pack(side="left", padx=20)
        else:
            self.cb_list_preview.pack_forget()

        # 确保预览面板的显示状态与变量同步
        self.on_list_preview_toggle(save=False)
        self.refresh_package_list()

    def on_list_preview_toggle(self, save=True):
        """列表预览开关切换时触发"""
        if save:
            self.save_settings()
        # 只有在筛选类型为“人物”且勾选了显示时，才真正展示预览面板
        if self.show_card_view.get() and self.list_filter_type.get() == PackageType.CHARACTER.value:
            # 确保预览面板在右侧，表格在左侧并填充剩余空间
            # 重新打包以保证顺序：先排预览面板（固定在右），再排表格（填充剩余）
            self.frame_tree.pack_forget()
            self.frame_list_preview.pack(side="right", fill="y", padx=10, pady=10)
            self.frame_tree.pack(side="left", fill="both", expand=True)
            self.on_tree_select()
        else:
            self.frame_list_preview.pack_forget()

    def on_tree_select(self, event=None):
        """列表选中项改变时更新预览"""
        if not self.show_card_view.get() or self.list_filter_type.get() != PackageType.CHARACTER.value:
            return

        selected = self.tree.selection()
        if not selected:
            self.list_preview_label.config(image="", text="未选择项目")
            return

        item = self.tree.item(selected[0])
        values = item["values"]
        pkg_type = values[2]
        meta_path = values[7]

        if pkg_type != PackageType.CHARACTER.value:
            self.list_preview_label.config(image="", text="该类型不支持预览")
            return

        try:
            with open(meta_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            png_path = None
            status = data.get("status")

            if status == PackageStatus.DRY_RUN.value:
                # 模拟数据：从原始路径加载
                source_path = data.get("source_path")
                if source_path and os.path.exists(source_path):
                    src_pngs = list(Path(source_path).rglob("*.png"))
                    # 优先级：female > male > 其他
                    src_pngs.sort(
                        key=lambda x: (
                            0
                            if "female" in str(x).lower()
                            else 1 if "male" in str(x).lower() else 2
                        )
                    )
                    if src_pngs:
                        png_path = src_pngs[0]
            else:
                # 正式数据：从安装目标路径加载
                app_root = Path(self.app_root.get())
                png_candidates = []
                for f_info in data.get("files", []):
                    dest = f_info.get("dest")
                    if dest and dest.lower().endswith(".png"):
                        # 统一路径分隔符进行匹配
                        norm_dest = dest.replace("\\", "/")
                        if "userdata/chara" in norm_dest.lower():
                            png_candidates.append(dest)

                # 优先级：female > male > 其他
                png_candidates.sort(
                    key=lambda x: (
                        0 if "female" in x.lower() else 1 if "male" in x.lower() else 2
                    )
                )

                if png_candidates:
                    png_path = app_root / png_candidates[0]

            if png_path and os.path.exists(png_path):
                # 列表页预览图高度可以稍微大一点，或者保持一致
                self.load_image_to_label(png_path, self.list_preview_label, target_height=400)
            else:
                self.list_preview_label.config(image="", text="未找到人物卡预览图")
        except Exception as e:
            self.list_preview_label.config(image="", text=f"加载失败: {e}")

    def on_import_preview_toggle(self, save=True):
        """导入页预览开关切换时触发"""
        if save:
            self.save_settings()
        if self.show_import_preview.get() and self.pkg_type.get() == PackageType.CHARACTER.value:
            self.frame_import_right.pack(side="right", padx=10, pady=0)
            self.update_import_preview()
        else:
            self.frame_import_right.pack_forget()

    def update_import_preview(self):
        """更新导入页的人物卡预览"""
        if not self.show_import_preview.get() or self.pkg_type.get() != PackageType.CHARACTER.value:
            return

        source = self.source_path.get()
        if not source:
            self.import_preview_label.config(image="", text="请先选择资源包")
            return

        # 在源目录中寻找 PNG
        png_path = None
        for p in Path(source).rglob("*.png"):
            if "userdata\\chara" in str(p).lower():
                png_path = p
                break

        if png_path and png_path.exists():
            # 导入页预览图高度略小于左侧表单的高度 (约 180 像素)
            self.load_image_to_label(png_path, self.import_preview_label, target_height=180)
        else:
            self.import_preview_label.config(image="", text="未找到人物卡预览图")

    def load_image_to_label(self, path, label, target_height=None):
        """加载并缩放图片到 Label"""
        try:
            # 使用 PIL 进行高质量缩放 (如果可用)
            try:
                from PIL import Image, ImageTk
                img = Image.open(str(path))
                
                if target_height:
                    # 按比例缩放
                    w, h = img.size
                    ratio = target_height / h
                    new_w = int(w * ratio)
                    img = img.resize((new_w, target_height), Image.Resampling.LANCZOS)
                
                photo = ImageTk.PhotoImage(img)
                label.config(image=photo, text="")
                label.image = photo
            except ImportError:
                # 回退到 Tkinter 原生 PhotoImage (功能有限)
                img = tk.PhotoImage(file=str(path))
                label.config(image=img, text="")
                label.image = img
        except Exception as e:
            label.config(image="", text=f"图片加载失败: {e}")

    def save_settings(self):
        """保存当前设置到配置文件"""
        config = self.manager.config
        if "gui" not in config:
            config["gui"] = {}

        gui = config["gui"]
        gui[GUIConfigKey.SHOW_CARD_VIEW.value] = self.show_card_view.get()
        gui[GUIConfigKey.SHOW_IMPORT_PREVIEW.value] = self.show_import_preview.get()
        try:
            gui[GUIConfigKey.SELECTED_TAB.value] = self.notebook.index(
                self.notebook.select()
            )
        except:
            pass
        self.manager.save_config(config)

    def on_dry_run_change(self):
        if self.dry_run.get():
            self.cb_create_meta.pack(side="left", padx=20)
        else:
            self.cb_create_meta.pack_forget()
            self.create_meta_on_dry_run.set(False)  # 隐藏时重置为不勾选

    def log(self, message):
        self.log_text.config(state="normal")
        self.log_text.insert("end", message + "\n")
        self.log_text.see("end")
        self.log_text.config(state="disabled")
        self.root.update_idletasks()

    def browse_source(self):
        path = filedialog.askdirectory()
        if path:
            self.source_path.set(path)
            self.auto_detect(Path(path).name)

    def auto_detect(self, folder_name):
        # 尝试匹配女性或男性角色特征 (例如: 名称.HS2ChaF_数字)
        match = re.search(r"^(.*)\.(HS2Cha[FM]_\d+)$", folder_name)
        if match:
            self.name.set(match.group(1))
            self.sid.set(match.group(2))
            self.pkg_type.set(PackageType.CHARACTER.value)
        else:
            # 未检测到标准 SID 格式
            self.name.set(folder_name)
            self.sid.set("")  # 设为 None (空字符串)
            self.pkg_type.set(PackageType.OTHER.value)
        self.on_type_change()

    def start_process(self):
        source = self.source_path.get()
        pkg_type = self.pkg_type.get()
        app_root_val = self.app_root.get()
        meta_dir_val = self.meta_dir.get()

        if pkg_type == PackageType.CHARACTER.value:
            name = self.name.get()
            sid = self.sid.get()

            if not source or not name or not sid:
                messagebox.showerror("错误", "请确保已选择目录并填写名称和 SID")
                return

            # 校验 SID 格式 (例如: HS2ChaF_20251105165109590)
            if not re.match(r"^HS2Cha[FM]_\d+$", sid):
                if not messagebox.askyesno(
                    "格式警告",
                    f"检测到 SID 格式可能不正确: '{sid}'\n\n标准格式通常为 'HS2ChaF_数字'。\n是否继续安装?",
                ):
                    return
        else:
            # 其他类型：使用文件夹名作为名称，生成一个简单的 SID
            if not source:
                messagebox.showerror("错误", "请先选择资源包目录")
                return
            folder_path = Path(source)
            name = folder_path.name
            sid = f"Other_{datetime.now().strftime('%Y%m%d%H%M%S')}"

        # 校验配置路径
        if not app_root_val or not Path(app_root_val).is_dir():
            messagebox.showerror(
                "配置错误",
                f"游戏根目录无效或不存在: {app_root_val}\n请检查 config.json",
            )
            return

        if not meta_dir_val:
            messagebox.showerror("配置错误", "元数据目录未配置，请检查 config.json")
            return

        # 检测是否存在同名或同 SID 的资源包
        existing_packages = self.manager.get_package_list(meta_dir_val)
        for pkg in existing_packages:
            if pkg["name"] == name:
                messagebox.showerror("导入失败", f"已存在名称为 '{name}' 的资源包，请先卸载或更改名称。")
                return
            if pkg["sid"] == sid:
                messagebox.showerror("导入失败", f"已存在 SID 为 '{sid}' 的资源包，请先卸载。")
                return

        # 元数据目录如果不存在可以尝试创建，或者也要求必须存在
        meta_path = Path(meta_dir_val)
        if not meta_path.exists():
            if messagebox.askyesno(
                "目录不存在", f"元数据目录不存在: {meta_dir_val}\n是否尝试创建?"
            ):
                try:
                    meta_path.mkdir(parents=True, exist_ok=True)
                except Exception as e:
                    messagebox.showerror("错误", f"无法创建元数据目录: {e}")
                    return
            else:
                return

        threading.Thread(
            target=self.run_install_thread,
            args=(source, name, sid, pkg_type, self.create_meta_on_dry_run.get()),
            daemon=True,
        ).start()

    def run_install_thread(self, source, name, sid, pkg_type, create_meta_on_dry_run):
        app_root = self.app_root.get()
        meta_dir = self.meta_dir.get()
        dry_run = self.dry_run.get()

        def conflict_callback(rel_dest, old_size, new_size):
            return messagebox.askyesno(
                "文件冲突",
                f"文件已存在:\n{rel_dest}\n\n原大小: {old_size}\n新大小: {new_size}\n是否覆盖?",
            )

        try:
            self.manager.install(
                source=source,
                name=name,
                sid=sid,
                pkg_type=pkg_type,
                app_root=app_root,
                meta_dir=meta_dir,
                dry_run=dry_run,
                create_meta_on_dry_run=create_meta_on_dry_run,
                log_func=self.log,
                conflict_func=conflict_callback,
            )
            messagebox.showinfo("完成", f"资源包 {name} 安装成功！")
        except Exception as e:
            self.log(f"\n发生错误: {str(e)}")
            messagebox.showerror("错误", f"安装过程中出错: {str(e)}")
