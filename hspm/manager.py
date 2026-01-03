import json
import shutil
import sys
import tomllib
from datetime import datetime
from pathlib import Path
from .models import PackageStatus

class PackageManager:
    """处理资源包安装、元数据管理和配置的核心逻辑类"""

    def __init__(self):
        # 配置文件路径: 用户目录/.config/HS2PackageManager/config.json
        self.config_dir = Path.home() / ".config" / "HS2PackageManager"
        self.config_path = self.config_dir / "config.json"
        self.config = self.load_config()
        self.version = self._load_version()

    def _load_version(self):
        """从 pyproject.toml 读取版本号"""
        try:
            # 优先尝试从打包后的资源目录读取
            if hasattr(sys, "_MEIPASS"):
                pyproject_path = Path(sys._MEIPASS) / "pyproject.toml"
            else:
                # 注意：这里路径可能需要调整，因为现在在 hspm/ 目录下
                pyproject_path = Path(__file__).parent.parent / "pyproject.toml"

            if pyproject_path.exists():
                with open(pyproject_path, "rb") as f:
                    data = tomllib.load(f)
                    return data.get("project", {}).get("version", "0.1.0")
        except Exception as e:
            print(f"读取版本号失败: {e}")
        return "0.1.0"

    def load_config(self):
        if not self.config_dir.exists():
            try:
                self.config_dir.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                print(f"创建配置目录失败: {e}")

        if self.config_path.exists():
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return data if data else {}
            except Exception as e:
                print(f"加载配置失败: {e}")
        return {}

    def save_config(self, config_data):
        """保存配置到文件"""
        try:
            self.config_dir.mkdir(parents=True, exist_ok=True)
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(config_data, f, indent=4, ensure_ascii=False)
            self.config = config_data
            return True
        except Exception as e:
            print(f"保存配置失败: {e}")
            return False

    def get_package_list(self, meta_dir):
        """获取所有已安装资源包的元数据列表"""
        packages = []
        meta_path = Path(meta_dir)
        if not meta_path.exists():
            return packages

        for json_file in meta_path.glob("*.json"):
            try:
                with open(json_file, "r", encoding="utf-8") as f:
                    data = json.load(f)

                parts = json_file.stem.split(".")
                is_dry_run = data.get("dry_run", False)
                status = data.get("status")
                if status is None:
                    status = (
                        PackageStatus.DRY_RUN.value
                        if is_dry_run
                        else PackageStatus.NORMAL.value
                    )

                packages.append(
                    {
                        "name": data.get(
                            "name", parts[0] if len(parts) > 0 else "未知"
                        ),
                        "sid": data.get("sid", parts[1] if len(parts) > 1 else "未知"),
                        "type": data.get("type", "未知"),
                        "created_at": data.get("created_at", ""),
                        "file_count": len(data.get("news", [])),
                        "status": status,
                        "meta_path": str(json_file),
                    }
                )
            except Exception as e:
                print(f"读取元数据失败 {json_file}: {e}")
        return packages

    def get_dest_path(self, relpath: Path, sid: str, name: str, app_root: Path):
        """计算目标安装路径"""
        a = relpath.parts
        if not a:
            return None

        if a[0] == "mods":
            insert = sid or name
            return app_root / "mods" / "MyMods" / insert / Path(*a[1:])

        if a[0] == "UserData":
            if len(a) > 2 and a[1] == "chara" and a[2] == "female":
                return app_root / "UserData" / "chara" / "female" / name / Path(*a[3:])

        if a[0] == "abdata":
            if len(a) > 2 and a[1] == "chara" and a[2] == "thumb":
                return None  # skip thumbnails
            return app_root / relpath

        return None

    def install(
        self,
        source,
        name,
        sid,
        pkg_type,
        app_root,
        meta_dir,
        dry_run=False,
        create_meta_on_dry_run=False,
        log_func=None,
        conflict_func=None,
    ):
        """执行安装逻辑"""
        root = Path(source)
        app_root = Path(app_root)
        meta_dir = Path(meta_dir)
        items = []
        dirs = []

        def _log(msg):
            if log_func:
                log_func(msg)

        _log(f"开始处理: {name} ({sid})")
        if dry_run:
            _log("--- 模拟运行模式 ---")

        for path in root.rglob("*"):
            if not path.is_file():
                continue

            relpath = path.relative_to(root)
            dest = self.get_dest_path(relpath, sid, name, app_root)
            src_stat = path.stat()
            mtime_float = src_stat.st_mtime
            mtime_int = int(mtime_float * 1_000_000)
            mtime_iso = datetime.fromtimestamp(mtime_float).isoformat()

            if dest is None:
                _log(f"跳过: {relpath} (无目标路径或规则跳过)")
                items.append(
                    {
                        "status": "skipped",
                        "source": str(relpath),
                        "dest": None,
                        "mtime": mtime_int,
                        "message": "global skip rule",
                        "timestamp": mtime_iso,
                    }
                )
                continue

            rel_dest = dest.relative_to(app_root)
            overwrite = False

            if dest.exists():
                src_size = src_stat.st_size
                dest_size = dest.stat().st_size
                if src_size == dest_size:
                    _log(f"跳过: {relpath} (文件已存在且大小相同)")
                    items.append(
                        {
                            "status": "skipped",
                            "source": str(relpath),
                            "dest": str(rel_dest),
                            "mtime": mtime_int,
                            "message": "same size",
                            "timestamp": mtime_iso,
                        }
                    )
                    continue

                # 处理冲突
                if conflict_func:
                    if conflict_func(rel_dest, dest_size, src_size):
                        overwrite = True
                    else:
                        _log(f"跳过: {relpath} (用户选择不覆盖)")
                        items.append(
                            {
                                "status": "skipped",
                                "source": str(relpath),
                                "dest": str(rel_dest),
                                "mtime": mtime_int,
                                "message": "user chose not to overwrite",
                                "timestamp": mtime_iso,
                            }
                        )
                        continue
                else:
                    _log(f"跳过: {relpath} (文件冲突且未提供处理回调)")
                    continue

            action_prefix = "模拟" if dry_run else ""
            action = f"{action_prefix}覆盖" if overwrite else f"{action_prefix}复制"
            _log(f"{action}: {relpath} -> {rel_dest}")

            # 检查并记录目录创建
            current_parent = dest.parent
            dirs_to_create: list[Path] = []
            while not current_parent.exists() and current_parent != app_root:
                dirs_to_create.append(current_parent)
                current_parent = current_parent.parent

            for d in reversed(dirs_to_create):
                if not dry_run:
                    d.mkdir(exist_ok=True)
                    _log(f"创建目录: {d.relative_to(app_root)}")

                rel_d = d.relative_to(app_root)
                if str(rel_d) not in [x["dest"] for x in dirs]:
                    dirs.append(
                        {
                            "dest": str(rel_d),
                            "timestamp": datetime.now().isoformat(),
                        }
                    )

            itd = {
                "status": "overwritten" if overwrite else "copied",
                "source": str(relpath),
                "dest": str(rel_dest),
                "mtime": mtime_int,
                "timestamp": mtime_iso,
            }

            if not dry_run:
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(str(path), str(dest))
                # 核心修复：记录目标文件在安装后的实际时间戳，确保删除校验一致
                itd["mtime"] = int(dest.stat().st_mtime * 1_000_000)

            items.append(itd)

        # 保存元数据
        # 逻辑：正式安装始终保存；模拟安装仅在勾选了创建选项时保存
        should_save_meta = not dry_run or (dry_run and create_meta_on_dry_run)

        if should_save_meta:
            outdata = {
                "name": name,
                "sid": sid,
                "type": pkg_type,
                "status": (
                    PackageStatus.DRY_RUN.value
                    if dry_run
                    else PackageStatus.NORMAL.value
                ),
                "source_path": str(root) if dry_run else None,
                "created_at": datetime.now().isoformat(),
                "news": [
                    d["dest"] for d in items if d["status"] in ("copied", "overwritten")
                ],
                "dirs": dirs,
                "files": items,
            }
            meta_dir.mkdir(parents=True, exist_ok=True)
            outfile = meta_dir / f"{name}.{sid}.json"
            outfile.write_text(
                json.dumps(outdata, indent=4, ensure_ascii=False), encoding="utf-8"
            )

        if dry_run:
            if create_meta_on_dry_run:
                _log("\n模拟安装完成！元数据（模拟记录）已保存。")
            else:
                _log("\n模拟安装完成！(未保存元数据)")
        else:
            _log("\n安装完成！元数据已保存。")

        return True

    def delete_package(self, meta_path, app_root):
        """删除资源包及其相关文件和目录"""
        meta_path = Path(meta_path)
        app_root = Path(app_root)

        if not meta_path.exists():
            return False, "元数据文件不存在"

        try:
            with open(meta_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            status = data.get("status")
            # 兼容旧数据：如果没有 status 字段，则看 dry_run 字段
            if status is None:
                status = (
                    PackageStatus.DRY_RUN.value
                    if data.get("dry_run")
                    else PackageStatus.NORMAL.value
                )

            is_dry_run = status == PackageStatus.DRY_RUN.value
            conflicts = []

            # 只有 NORMAL 状态才执行物理删除逻辑
            if status == PackageStatus.NORMAL.value:
                # 1. 删除文件
                items = data.get("files", [])
                for item in items:
                    if item.get("status") in ("copied", "overwritten"):
                        dest_path = app_root / item.get("dest")
                        if dest_path.exists() and dest_path.is_file():
                            # 比较时间戳，如果不一致说明被其他资源包修改过
                            current_mtime = int(dest_path.stat().st_mtime * 1_000_000)
                            recorded_mtime = item.get("mtime")

                            if (
                                recorded_mtime is not None
                                and current_mtime != recorded_mtime
                            ):
                                # 时间戳不一致，保留文件
                                print(
                                    f"[DEBUG] 文件时间戳不一致，保留文件: {dest_path}"
                                )
                                item["reason"] = "timestamp_mismatch"
                                item["current_mtime"] = current_mtime
                                conflicts.append(item)
                            else:
                                # 时间戳一致，可以删除
                                print(f"[DEBUG] 准备删除文件: {dest_path}")
                                dest_path.unlink()
                        else:
                            # 文件不存在，视为已删除
                            pass

                # 2. 删除目录 (仅在没有冲突文件的情况下尝试)
                if not conflicts:
                    dirs = data.get("dirs", [])
                    for d_info in reversed(dirs):
                        d_path = app_root / d_info.get("dest")
                        if d_path.exists() and d_path.is_dir():
                            # 只有目录为空时才删除，避免误删其他资源包的文件
                            try:
                                if not any(d_path.iterdir()):
                                    print(f"[DEBUG] 准备删除空目录: {d_path}")
                                    d_path.rmdir()
                            except:
                                pass

            # 3. 处理元数据文件
            if conflicts:
                # 有文件未成功删除，更新 meta 文件并保留
                data["status"] = PackageStatus.CONFLICT.value
                data["delete_conflicts"] = conflicts
                data["delete_attempt_time"] = datetime.now().isoformat()
                print(f"[DEBUG] 准备更新元数据 (记录冲突详情): {meta_path}")
                with open(meta_path, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=4, ensure_ascii=False)
                return (
                    True,
                    f"卸载完成，但有 {len(conflicts)} 个文件因被修改而保留。元数据已更新。",
                )
            else:
                print(f"[DEBUG] 准备删除元数据: {meta_path}")
                meta_path.unlink()
                msg = "模拟记录已移除" if is_dry_run else "资源包已成功卸载"
                return True, msg
        except Exception as e:
            return False, f"删除失败: {str(e)}"
