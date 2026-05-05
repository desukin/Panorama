# -*- coding: utf-8 -*-
import os
import sys
import numpy as np
import math
import glob
import time
from PIL import Image

# ===================== 配置（无需修改）=====================
DEFAULT_INPUT_DIR = "input"
DEFAULT_OUTPUT_DIR = "output"

# 输出顺序映射：panorama_0..5
OUTPUT_ORDER = [
    ("front", "panorama_0.png"),
    ("right", "panorama_1.png"),
    ("back",  "panorama_2.png"),
    ("left",  "panorama_3.png"),
    ("up",    "panorama_4.png"),
    ("down",  "panorama_5.png"),
]

# ===================== 核心工具函数 =====================
def ensure_dirs():
    os.makedirs(DEFAULT_INPUT_DIR, exist_ok=True)
    os.makedirs(DEFAULT_OUTPUT_DIR, exist_ok=True)

def load_image_safe(path):
    try:
        return Image.open(path).convert("RGB")
    except Exception as e:
        print(f"[错误] 无法打开图片：{path}\n{e}")
        sys.exit(1)

def square_center_crop(img, target_side=None):
    w, h = img.size
    if target_side is None:
        side = min(w, h)
        left = (w - side) // 2
        top = (h - side) // 2
        return img.crop((left, top, left + side, top + side))

    if w < h:
        new_w = target_side
        new_h = int(h * (target_side / w))
    else:
        new_h = target_side
        new_w = int(w * (target_side / h))
    img_resized = img.resize((new_w, new_h), Image.LANCZOS)

    left = (new_w - target_side) // 2
    top = (new_h - target_side) // 2
    return img_resized.crop((left, top, left + target_side, top + target_side))

def create_equirectangular(images, output_size=(4096, 2048)):
    width, height = output_size
    equirectangular = Image.new('RGB', (width, height))
    cube_faces = {k: np.array(v) for k, v in images.items()}
    face_size = images['front'].size[0]

    for y in range(height):
        for x in range(width):
            theta = 2.0 * math.pi * (x / width - 0.5)
            phi = math.pi * (y / height - 0.5)
            cos_phi = math.cos(phi)
            x3d = cos_phi * math.cos(theta)
            y3d = math.sin(phi)
            z3d = cos_phi * math.sin(theta)

            abs_x, abs_y, abs_z = abs(x3d), abs(y3d), abs(z3d)
            if abs_x >= abs_y and abs_x >= abs_z:
                face = 'right' if x3d > 0 else 'left'
            elif abs_y >= abs_x and abs_y >= abs_z:
                face = 'up' if y3d > 0 else 'down'
            else:
                face = 'front' if z3d > 0 else 'back'

            if face == 'front':
                u = (x3d / abs_z + 1) / 2
                v = (1 - y3d / abs_z) / 2
            elif face == 'back':
                u = (-x3d / abs_z + 1) / 2
                v = (1 - y3d / abs_z) / 2
            elif face == 'right':
                u = (-z3d / abs_x + 1) / 2
                v = (1 - y3d / abs_x) / 2
            elif face == 'left':
                u = (z3d / abs_x + 1) / 2
                v = (1 - y3d / abs_x) / 2
            elif face == 'up':
                u = (x3d / abs_y + 1) / 2
                v = (z3d / abs_y + 1) / 2
            elif face == 'down':
                u = (x3d / abs_y + 1) / 2
                v = (-z3d / abs_y + 1) / 2

            u_px = min(int(u * face_size), face_size - 1)
            v_px = min(int(v * face_size), face_size - 1)
            color = cube_faces[face][v_px, u_px]
            equirectangular.putpixel((x, y), tuple(color))
    return equirectangular

def create_mc_skybox(images, face_size):
    skybox = Image.new('RGB', (3 * face_size, 2 * face_size))
    mapping = [
        (0, 0, 'down'),
        (1, 0, 'up'),
        (2, 0, 'back'),
        (0, 1, 'left'),
        (1, 1, 'front'),
        (2, 1, 'right')
    ]
    for x, y, face in mapping:
        skybox.paste(images[face], (x * face_size, y * face_size))
    return skybox

# ===================== 命令行主逻辑 =====================
def main():
    print("=" * 60)
    print("        MC 六面体全景生成器 - 纯命令行版")
    print("  支持 Windows CMD / PowerShell / Linux / macOS 终端")
    print("=" * 60)
    ensure_dirs()

    # 1. 自动加载 input 下最新6张图
    print(f"\n[1/4] 正在扫描 {DEFAULT_INPUT_DIR}/ 文件夹...")
    exts = ["png", "jpg", "jpeg"]
    files = []
    for ext in exts:
        files += glob.glob(os.path.join(DEFAULT_INPUT_DIR, f"*.{ext}"))
    if len(files) < 6:
        print(f"[错误] input 文件夹不足6张图片，当前：{len(files)} 张")
        sys.exit(1)

    files.sort(key=lambda x: os.path.getmtime(x), reverse=True)
    latest = files[:6]
    face_names = ["down", "up", "left", "back", "right", "front"]
    img_paths = dict(zip(face_names, latest))
    print(f"✅ 已加载6张图片：")
    for k, p in img_paths.items():
        print(f"   {k:5s}: {os.path.basename(p)}")

    # 2. 读取尺寸
    print(f"\n[2/4] 读取尺寸...")
    front_img = load_image_safe(img_paths["front"])
    target_side = min(front_img.size)
    print(f"✅ 自动使用尺寸：{target_side} × {target_side}")

    # 3. 加载并处理图片
    print(f"\n[3/4] 处理图片（裁剪/标准化）...")
    processed = {}
    for key in face_names:
        img = load_image_safe(img_paths[key])
        processed[key] = square_center_crop(img, target_side)

    # 4. 生成输出
    print(f"\n[4/4] 生成全景文件...")
    for key, out_name in OUTPUT_ORDER:
        out_path = os.path.join(DEFAULT_OUTPUT_DIR, out_name)
        processed[key].save(out_path, "PNG")

    # 生成等距圆柱图
    eq = create_equirectangular(processed, (target_side*4, target_side*2))
    eq = eq.transpose(Image.FLIP_LEFT_RIGHT).transpose(Image.FLIP_TOP_BOTTOM)
    eq_path = os.path.join(DEFAULT_OUTPUT_DIR, "output.png")
    eq.save(eq_path, "PNG")

    # 生成MC天空盒
    sky = create_mc_skybox(processed, target_side)
    sky_path = os.path.join(DEFAULT_OUTPUT_DIR, "sky0.png")
    sky.save(sky_path, "PNG")

    # 完成
    print("\n" + "="*60)
    print("✅ 全部生成完成！")
    print(f"📁 输出目录：{os.path.abspath(DEFAULT_OUTPUT_DIR)}")
    print(f"📄 输出文件：6张全景图 + output.png + sky0.png")
    print("="*60)

if __name__ == "__main__":
    main()