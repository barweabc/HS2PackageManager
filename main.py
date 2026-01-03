import multiprocessing
import tkinter as tk
from hspm.gui import AddPackageGUI

if __name__ == "__main__":
    # 核心修复：确保在打包或多进程环境下不意外启动 GUI
    multiprocessing.freeze_support()

    # 只有在主进程中才启动 Tkinter 窗口
    if multiprocessing.current_process().name == "MainProcess":
        root = tk.Tk()
        app = AddPackageGUI(root)
        root.mainloop()
