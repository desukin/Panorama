# -*- coding: utf-8 -*-
import os
import sys
import numpy as np
from PIL import Image
import math
import time

# ===================== 配置项 =====================
INPUT_DIR = "input"
OUTPUT_DIR = "output"
OUTPUT_SIZE = 512
SAVE_INDIVIDUAL_FACES = True
# ==================================================

def erp_to_cubemap(erp_img, output_size):
    erp_arr = np.array(erp_img)
    h, w = erp_arr.shape[:2]
    faces = [np.zeros((output_size, output_size, 3), dtype=np.uint8) for _ in range(6)]

    face_configs = [
        {"name": "前", "coords": lambda u, v: (1.0, v, u)},
        {"name": "后", "coords": lambda u, v: (-1.0, v, -u)},
        {"name": "左", "coords": lambda u, v: (-u, v, 1.0)},
        {"name": "右", "coords": lambda u, v: (u, v, -1.0)},
        {"name": "上", "coords": lambda u, v: (u, 1.0, v)},
        {"name": "下", "coords": lambda u, v: (u, -1.0, -v)}
    ]

    for face_idx in range(6):
        face_name = face_configs[face_idx]["name"]
        print(f"  正在处理 {face_name} 面...")

        for i in range(output_size):
            if i % 100 == 0:
                print(f"  {face_name}面进度: {i}/{output_size}")

            for j in range(output_size):
                u = 2.0 * i / output_size - 1.0
                v = 2.0 * j / output_size - 1.0
                x, y, z = face_configs[face_idx]["coords"](u, v)

                r = math.sqrt(x*x + y*y + z*z)
                theta = math.atan2(z, x)
                phi = math.asin(y / r) if r != 0 else 0

                erp_x = (theta + math.pi) / (2 * math.pi) * w
                erp_y = (math.pi/2 - phi) / math.pi * h

                erp_x = min(max(0, erp_x), w-1)
                erp_y = min(max(0, erp_y), h-1)

                try:
                    faces[face_idx][j, i] = erp_arr[int(erp_y), int(erp_x)]
                except:
                    faces[face_idx][j, i] = [0, 0, 0]

    return [Image.fromarray(face) for face in faces]

def save_individual_panorama_faces(faces, output_dir):
    panorama_mapping = [
        {"index": 5, "name": "panorama_5", "transform": "rotate90_vertical_flip"},
        {"index": 3, "name": "panorama_1", "transform": "vertical_flip"},
        {"index": 1, "name": "panorama_0", "transform": "vertical_flip"},
        {"index": 2, "name": "panorama_3", "transform": "vertical_flip"},
        {"index": 4, "name": "panorama_4", "transform": "rotate90_horizontal_flip"},
        {"index": 0, "name": "panorama_2", "transform": "vertical_flip"}
    ]

    for mapping in panorama_mapping:
        img = faces[mapping["index"]]
        t = mapping["transform"]

        if t == "vertical_flip":
            img = img.transpose(Image.FLIP_TOP_BOTTOM)
        elif t == "rotate90_horizontal_flip":
            img = img.transpose(Image.ROTATE_90).transpose(Image.FLIP_LEFT_RIGHT)
        elif t == "rotate90_vertical_flip":
            img = img.transpose(Image.ROTATE_90).transpose(Image.FLIP_TOP_BOTTOM)

        path = os.path.join(output_dir, f"{mapping['name']}.png")
        img.save(path, "PNG")
        print(f"    ✓ 已保存 {mapping['name']}.png")

def create_skybox(faces, output_size):
    skybox = Image.new('RGB', (3 * output_size, 2 * output_size))
    layout = [
        {"f": 5, "p": (0,0), "t": "rotate90_vertical_flip"},
        {"f": 4, "p": (1,0), "t": "rotate90_horizontal_flip"},
        {"f": 0, "p": (2,0), "t": "vertical_flip"},
        {"f": 2, "p": (0,1), "t": "vertical_flip"},
        {"f": 1, "p": (1,1), "t": "vertical_flip"},
        {"f": 3, "p": (2,1), "t": "vertical_flip"}
    ]

    for item in layout:
        img = faces[item["f"]]
        t = item["t"]

        if t == "vertical_flip":
            img = img.transpose(Image.FLIP_TOP_BOTTOM)
        elif t == "rotate90_horizontal_flip":
            img = img.transpose(Image.ROTATE_90).transpose(Image.FLIP_LEFT_RIGHT)
        elif t == "rotate90_vertical_flip":
            img = img.transpose(Image.ROTATE_90).transpose(Image.FLIP_TOP_BOTTOM)

        x, y = item["p"]
        skybox.paste(img, (x * output_size, y * output_size))

    return skybox

def process(input_path, out_dir, size, save_faces):
    print(f"开始处理：{os.path.basename(input_path)}")
    img = Image.open(input_path).convert("RGB")
    print(f"原图尺寸：{img.size[0]}x{img.size[1]}")

    faces = erp_to_cubemap(img, size)
    os.makedirs(out_dir, exist_ok=True)

    if save_faces:
        print("\n正在保存6张全景图...")
        save_individual_panorama_faces(faces, out_dir)

    print("\n正在生成天空盒...")
    sky = create_skybox(faces, size)
    sky.save(os.path.join(out_dir, "sky0.png"), "PNG")
    print("✓ 天空盒已保存：sky0.png")
    return True

def main():
    print("="*50)
    print("     ERP全景图 → MC天空盒 纯命令行版")
    print("="*50)

    if not os.path.exists(INPUT_DIR):
        os.makedirs(INPUT_DIR)
        print(f"\n已创建 input 文件夹，请放入全景图后重试")
        return

    exts = ('.png','.jpg','.jpeg','.bmp','.tiff','.webp')
    files = []
    for f in os.listdir(INPUT_DIR):
        if f.lower().endswith(exts):
            p = os.path.join(INPUT_DIR, f)
            files.append((p, os.path.getmtime(p)))

    if not files:
        print("\ninput 文件夹中没有找到图片！")
        return

    files.sort(key=lambda x:x[1], reverse=True)
    latest = files[0][0]
    print(f"\n自动选择最新图片：{os.path.basename(latest)}")

    t0 = time.time()
    process(latest, OUTPUT_DIR, OUTPUT_SIZE, SAVE_INDIVIDUAL_FACES)

    print(f"\n✅ 全部完成！耗时 {time.time()-t0:.2f}s")
    print(f"输出目录：{os.path.abspath(OUTPUT_DIR)}")

if __name__ == "__main__":
    main()