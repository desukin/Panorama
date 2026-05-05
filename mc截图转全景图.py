# -*- coding: utf-8 -*-

import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from PIL import Image, ImageTk
import numpy as np
import math
import glob
import time

# 默认目录与文件名
DEFAULT_INPUT_DIR = "input"
DEFAULT_OUTPUT_DIR = "output"
DEFAULT_FILES = {
    "front": os.path.join(DEFAULT_INPUT_DIR, "front.png"),
    "right": os.path.join(DEFAULT_INPUT_DIR, "right.png"),
    "back":  os.path.join(DEFAULT_INPUT_DIR, "back.png"),
    "left":  os.path.join(DEFAULT_INPUT_DIR, "left.png"),
    "up":    os.path.join(DEFAULT_INPUT_DIR, "up.png"),
    "down":  os.path.join(DEFAULT_INPUT_DIR, "down.png"),
}

# 输出顺序映射：panorama_0..5
OUTPUT_ORDER = [
    ("front", "panorama_0.png"),
    ("right", "panorama_1.png"),
    ("back",  "panorama_2.png"),
    ("left",  "panorama_3.png"),
    ("up",    "panorama_4.png"),
    ("down",  "panorama_5.png"),
]

def ensure_dirs():
    os.makedirs(DEFAULT_INPUT_DIR, exist_ok=True)
    os.makedirs(DEFAULT_OUTPUT_DIR, exist_ok=True)

def load_image_safe(path):
    try:
        return Image.open(path).convert("RGB")
    except Exception as e:
        raise RuntimeError(f"无法打开图片：{path}\n{e}")

def square_center_crop(img, target_side=None):
    """
    等比缩放使短边 = target_side（如提供），然后居中裁剪成正方形。
    若 target_side 为 None，则先不缩放，直接对最小边居中裁剪。
    最后若 target_side 存在，再统一缩放到 target_side x target_side。
    """
    w, h = img.size

    if target_side is None:
        # 直接按最小边裁剪
        side = min(w, h)
        left = (w - side) // 2
        top = (h - side) // 2
        img_sq = img.crop((left, top, left + side, top + side))
        return img_sq

    # 先等比缩放：使短边达到 target_side
    if w < h:
        new_w = target_side
        new_h = int(h * (target_side / w))
    else:
        new_h = target_side
        new_w = int(w * (target_side / h))
    img_resized = img.resize((new_w, new_h), Image.LANCZOS)

    # 再从中心裁出 target_side 的正方形
    left = (new_w - target_side) // 2
    top = (new_h - target_side) // 2
    img_sq = img_resized.crop((left, top, left + target_side, top + target_side))
    return img_sq

def create_equirectangular(images, output_size=(4096, 2048)):
    """
    创建等距圆柱投射图（2:1 全景图）
    images: 字典，包含六张处理后的正方形图像
    output_size: 输出图像尺寸 (width, height)
    """
    width, height = output_size
    equirectangular = Image.new('RGB', (width, height))
    
    # 将六张图像转换为numpy数组以便快速访问
    cube_faces = {
        'front': np.array(images['front']),
        'right': np.array(images['right']),
        'back': np.array(images['back']),
        'left': np.array(images['left']),
        'up': np.array(images['up']),
        'down': np.array(images['down'])
    }
    
    face_size = images['front'].size[0]  # 假设所有面都是相同尺寸的正方形
    
    # 映射立方体面到球面坐标
    for y in range(height):
        for x in range(width):
            # 将像素坐标转换为球面坐标
            theta = 2.0 * math.pi * (x / width - 0.5)  # -π 到 π
            phi = math.pi * (y / height - 0.5)         # -π/2 到 π/2
            
            # 将球面坐标转换为立方体坐标
            cos_phi = math.cos(phi)
            x3d = cos_phi * math.cos(theta)
            y3d = math.sin(phi)
            z3d = cos_phi * math.sin(theta)
            
            # 确定在哪个立方体面上
            abs_x = abs(x3d)
            abs_y = abs(y3d)
            abs_z = abs(z3d)
            
            if abs_x >= abs_y and abs_x >= abs_z:
                if x3d > 0:
                    face = 'right'
                else:
                    face = 'left'
            elif abs_y >= abs_x and abs_y >= abs_z:
                if y3d > 0:
                    face = 'up'
                else:
                    face = 'down'
            else:
                if z3d > 0:
                    face = 'front'
                else:
                    face = 'back'
            
            # 将3D坐标映射到2D平面（修正上下翻转问题）
            if face == 'front':
                u = (x3d / abs_z + 1) / 2
                v = (1 - y3d / abs_z) / 2  # 修正：1 - y3d/abs_z
            elif face == 'back':
                u = (-x3d / abs_z + 1) / 2
                v = (1 - y3d / abs_z) / 2  # 修正：1 - y3d/abs_z
            elif face == 'right':
                u = (-z3d / abs_x + 1) / 2
                v = (1 - y3d / abs_x) / 2  # 修正：1 - y3d/abs_x
            elif face == 'left':
                u = (z3d / abs_x + 1) / 2
                v = (1 - y3d / abs_x) / 2  # 修正：1 - y3d/abs_x
            elif face == 'up':
                u = (x3d / abs_y + 1) / 2
                v = (z3d / abs_y + 1) / 2
            elif face == 'down':
                u = (x3d / abs_y + 1) / 2
                v = (-z3d / abs_y + 1) / 2
            
            # 将UV坐标转换为像素坐标
            u_px = min(int(u * face_size), face_size - 1)
            v_px = min(int(v * face_size), face_size - 1)
            
            # 获取颜色并设置到等距圆柱图上
            color = cube_faces[face][v_px, u_px]
            equirectangular.putpixel((x, y), tuple(color))
    
    return equirectangular

def create_mc_skybox(images, face_size):
    """
    创建MC天空盒输出图，按照指定顺序拼接
    第一行：5 4 2
    第二行：3 0 1
    """
    # 创建一个3x2的网格，每个单元格大小为face_size
    skybox = Image.new('RGB', (3 * face_size, 2 * face_size))
    
    # 定义映射关系：网格位置 -> 图像名称
    # 第一行：5 4 2 → down, up, back
    # 第二行：3 0 1 → left, front, right
    mapping = [
        (0, 0, 'down'),   # 第一行第一列: down (5)
        (1, 0, 'up'),     # 第一行第二列: up (4)
        (2, 0, 'back'),   # 第一行第三列: back (2)
        (0, 1, 'left'),   # 第二行第一列: left (3)
        (1, 1, 'front'),  # 第二行第二列: front (0)
        (2, 1, 'right')   # 第二行第三列: right (1)
    ]
    
    # 将图像粘贴到对应位置
    for x, y, face in mapping:
        img = images[face]
        skybox.paste(img, (x * face_size, y * face_size))
    
    return skybox

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("MC 六面体全景生成器（front/right/back/left/up/down → panorama_0..5）")
        self.geometry("880x560")
        ensure_dirs()

        # 变量
        self.paths = {
            key: tk.StringVar(value=DEFAULT_FILES[key]) for key in DEFAULT_FILES
        }
        self.fov_var = tk.StringVar(value="90")  # 视场角，信息提示用，不做重投影
        self.size_var = tk.StringVar(value="")   # 目标输出尺寸（留空=自动取第一张图最小边）

        # UI
        self._build_ui()

        # 预览图缓存（避免被回收）
        self.preview_images = {}

    def _build_ui(self):
        main = ttk.Frame(self, padding=10)
        main.pack(fill=tk.BOTH, expand=True)

        # 左侧：参数区
        left = ttk.Frame(main)
        left.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))

        ttk.Label(left, text="输入六面截图路径（默认 input/ 文件夹）：", font=("Segoe UI", 10, "bold")).pack(anchor="w")

        for key in ["front", "right", "back", "left", "up", "down"]:
            row = ttk.Frame(left)
            row.pack(fill=tk.X, pady=3)
            ttk.Label(row, text=key.ljust(5), width=8).pack(side=tk.LEFT)
            entry = ttk.Entry(row, textvariable=self.paths[key], width=48)
            entry.pack(side=tk.LEFT, padx=5)
            ttk.Button(row, text="浏览", command=lambda k=key: self._browse(k)).pack(side=tk.LEFT)

        # 刷新按钮
        refresh_btn = ttk.Button(left, text="刷新输入", command=self.refresh_inputs)
        refresh_btn.pack(pady=5)

        # 视场角 & 尺寸
        sep = ttk.Separator(left)
        sep.pack(fill=tk.X, pady=8)

        f1 = ttk.Frame(left); f1.pack(fill=tk.X, pady=2)
        ttk.Label(f1, text="视场角 (°)：").pack(side=tk.LEFT)
        ttk.Entry(f1, textvariable=self.fov_var, width=8, state="readonly").pack(side=tk.LEFT, padx=5)
        ttk.Label(f1, text="（固定90°，仅做信息提示）", foreground="#666").pack(side=tk.LEFT)

        f2 = ttk.Frame(left); f2.pack(fill=tk.X, pady=2)
        ttk.Label(f2, text="输出尺寸：").pack(side=tk.LEFT)
        ttk.Entry(f2, textvariable=self.size_var, width=8).pack(side=tk.LEFT, padx=5)
        ttk.Label(f2, text="留空=取第一张图的最小边", foreground="#666").pack(side=tk.LEFT)

        # 按钮
        btns = ttk.Frame(left); btns.pack(fill=tk.X, pady=10)
        ttk.Button(btns, text="预览", command=self.preview).pack(side=tk.LEFT, padx=5)
        ttk.Button(btns, text="生成", command=self.generate).pack(side=tk.LEFT, padx=5)

        # 右侧：预览区
        right = ttk.Frame(main, relief=tk.GROOVE, padding=8)
        right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        ttk.Label(right, text="预览（按输出顺序显示：前、右、后、左、上、下）", font=("Segoe UI", 10, "bold")).pack(anchor="w")
        self.canvas = tk.Canvas(right, bg="#222", height=420)
        self.canvas.pack(fill=tk.BOTH, expand=True, pady=6)

        # 底部说明
        info = ttk.Label(
            right,
            text=(
                "说明：将六张图标准化为正方形并按 Minecraft 标准命名导出到 output/。\n"
                "若输入非正方形：会等比缩放→居中裁剪为正方形→统一缩放至目标尺寸，避免拉伸。\n"
                "同时会生成 B 站全景视频用的等距圆柱投射图：output.png\n"
                "以及 MC 天空盒输出图：opti天空盒.png\n"
                "支持格式：PNG, JPG, JPEG"
            ),
            foreground="#666"
        )
        info.pack(anchor="w")

    def _browse(self, key):
        path = filedialog.askopenfilename(
            title=f"选择 {key} 图片",
            filetypes=[("图片文件", "*.png;*.jpg;*.jpeg"), ("PNG 图片", "*.png"), ("JPG 图片", "*.jpg;*.jpeg"), ("所有文件", "*.*")]
        )
        if path:
            self.paths[key].set(path)

    def refresh_inputs(self):
        """刷新输入，自动加载input目录中最新的6张图片"""
        try:
            # 获取input目录中所有支持的图片文件
            extensions = ["png", "jpg", "jpeg"]
            image_files = []
            for ext in extensions:
                pattern = os.path.join(DEFAULT_INPUT_DIR, f"*.{ext}")
                image_files.extend(glob.glob(pattern))
            
            # 按修改时间排序（最新的在前）
            image_files.sort(key=lambda x: os.path.getmtime(x), reverse=True)
            
            # 取最新的6张图片
            if len(image_files) < 6:
                messagebox.showwarning("警告", f"input目录中只有{len(image_files)}张图片，需要6张才能生成全景图")
                return
            
            latest_images = image_files[:6]
            
            # 按照下、上、左、后、右、前的顺序分配
            face_order = ["down", "up", "left", "back", "right", "front"]
            for i, img_path in enumerate(latest_images):
                if i < len(face_order):
                    face = face_order[i]
                    self.paths[face].set(img_path)
            
            messagebox.showinfo("刷新成功", f"已加载最新的6张图片到对应的面")
            
        except Exception as e:
            messagebox.showerror("刷新失败", f"刷新输入时出错：{str(e)}")

    def _read_target_size(self):
        s = self.size_var.get().strip()
        if s:
            try:
                n = int(s)
                if n <= 0:
                    raise ValueError
                return n
            except:
                messagebox.showerror("错误", "输出尺寸必须为正整数或留空。")
                return None

        # 留空：读取 front 的最小边
        front_path = self.paths["front"].get().strip()
        if not os.path.isfile(front_path):
            messagebox.showerror("错误", f"未找到 front 图片：{front_path}")
            return None
        img = load_image_safe(front_path)
        return min(img.size)

    def _load_all_images(self):
        imgs = {}
        for key in ["front", "right", "back", "left", "up", "down"]:
            p = self.paths[key].get().strip()
            if not os.path.isfile(p):
                raise RuntimeError(f"未找到 {key} 图片：{p}")
            imgs[key] = load_image_safe(p)
        return imgs

    def preview(self):
        try:
            target_side = self._read_target_size()
            if target_side is None:
                return
            imgs = self._load_all_images()

            # 清空画布
            self.canvas.delete("all")
            self.preview_images.clear()

            # 6张图以 3x2 网格显示
            cols, rows = 3, 2
            pad = 10
            # 计算每格缩略图边长（尽量大）
            c_w = int((self.canvas.winfo_width() - (cols + 1) * pad) / cols) or 180
            c_h = int((self.canvas.winfo_height() - (rows + 1) * pad) / rows) or 180
            thumb_side = min(c_w, c_h)

            positions = []
            for r in range(rows):
                for c in range(cols):
                    x = pad + c * (thumb_side + pad)
                    y = pad + r * (thumb_side + pad)
                    positions.append((x, y))

            # 按输出顺序绘制
            labels = ["front", "right", "back", "left", "up", "down"]
            for i, (key, _) in enumerate(OUTPUT_ORDER):
                img_sq = square_center_crop(imgs[key], target_side=None)  # 仅裁成正方形给预览
                img_th = img_sq.resize((thumb_side, thumb_side), Image.LANCZOS)
                tkimg = ImageTk.PhotoImage(img_th)
                self.preview_images[key] = tkimg  # 防回收

                x, y = positions[i]
                # 背板
                self.canvas.create_rectangle(
                    x - 2, y - 2, x + thumb_side + 2, y + thumb_side + 2,
                    fill="#111", outline="#555"
                )
                # 图像
                self.canvas.create_image(x, y, anchor="nw", image=tkimg)
                # 标签
                self.canvas.create_text(
                    x + 6, y + 6, anchor="nw", text=f"{i}: {key}",
                    fill="#ffffff", font=("Segoe UI", 9, "bold")
                )

            # FOV 提示（不做重投影）
            try:
                fov_val = float(self.fov_var.get().strip())
            except:
                fov_val = 90.0
            
            if abs(fov_val - 90) > 1e-6:
                messagebox.showinfo(
                    "提示",
                    "当前 FOV ≠ 90°。本工具不做投影变换，仅整理/裁剪/命名；\n"
                    "请确保你的六张图本身就是对应立方体朝向的视角，否则全景可能不准确。"
                )

        except Exception as e:
            messagebox.showerror("预览失败", str(e))

    def generate(self):
        try:
            target_side = self._read_target_size()
            if target_side is None:
                return

            imgs = self._load_all_images()
            os.makedirs(DEFAULT_OUTPUT_DIR, exist_ok=True)

            processed_imgs = {}
            for key, out_name in OUTPUT_ORDER:
                img = imgs[key]
                img_sq = square_center_crop(img, target_side=target_side)
                out_path = os.path.join(DEFAULT_OUTPUT_DIR, out_name)
                img_sq.save(out_path, format="PNG")
                processed_imgs[key] = img_sq

            # 生成等距圆柱投射图
            equirectangular = create_equirectangular(processed_imgs, output_size=(target_side * 4, target_side * 2))
            
            # 对最终结果进行水平翻转和垂直翻转
            equirectangular = equirectangular.transpose(Image.FLIP_LEFT_RIGHT)
            equirectangular = equirectangular.transpose(Image.FLIP_TOP_BOTTOM)
            
            equirectangular_path = os.path.join(DEFAULT_OUTPUT_DIR, "output.png")
            equirectangular.save(equirectangular_path, format="PNG")
            
            # 生成MC天空盒输出图
            mc_skybox = create_mc_skybox(processed_imgs, target_side)
            mc_skybox_path = os.path.join(DEFAULT_OUTPUT_DIR, "sky0.png")
            mc_skybox.save(mc_skybox_path, format="PNG")

            messagebox.showinfo(
                "完成",
                f"已输出 6 张立方体全景图到：{os.path.abspath(DEFAULT_OUTPUT_DIR)}\n"
                f"文件：panorama_0.png ~ panorama_5.png\n"
                f"同时生成了 B 站全景视频用的等距圆柱投射图：output.png\n"
                f"以及 MC 天空盒输出图：opti天空盒.png\n"
            )

        except Exception as e:
            messagebox.showerror("生成失败", str(e))

if __name__ == "__main__":
    app = App()
    app.mainloop()