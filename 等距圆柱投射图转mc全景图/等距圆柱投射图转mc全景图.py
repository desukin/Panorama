import os
import sys
import numpy as np
from PIL import Image
import math
import time
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                             QLabel, QLineEdit, QPushButton, QTextEdit, QFileDialog, QMessageBox,
                             QGroupBox, QProgressBar, QSpinBox, QCheckBox)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QFont, QTextCursor

class ConversionThread(QThread):
    """处理图像转换的线程"""
    progress_signal = pyqtSignal(str)
    finished_signal = pyqtSignal(bool, str)
    
    def __init__(self, input_dir, output_dir, output_size, save_individual_faces):
        super().__init__()
        self.input_dir = input_dir
        self.output_dir = output_dir
        self.output_size = output_size
        self.save_individual_faces = save_individual_faces
        self.is_running = True
        
    def run(self):
        try:
            # 获取输入目录中最新的图像文件
            supported_formats = ('.png', '.jpg', '.jpeg', '.bmp', '.tiff', '.webp')
            input_files = []
            for file in os.listdir(self.input_dir):
                if file.lower().endswith(supported_formats):
                    file_path = os.path.join(self.input_dir, file)
                    input_files.append((file_path, os.path.getmtime(file_path)))
            
            if not input_files:
                self.finished_signal.emit(False, f"在 {self.input_dir} 目录中没有找到支持的图像文件")
                return
            
            # 按修改时间排序，获取最新的文件
            input_files.sort(key=lambda x: x[1], reverse=True)
            latest_file = input_files[0][0]
            
            self.progress_signal.emit(f"找到最新文件: {os.path.basename(latest_file)}")
            self.progress_signal.emit("=" * 50)
            
            start_time = time.time()
            
            # 处理单个文件
            success = self.process_image(latest_file, self.output_dir, self.output_size)
            
            # 显示处理时间
            total_time = time.time() - start_time
            self.progress_signal.emit(f"处理完成，耗时: {total_time:.2f}秒")
            
            self.finished_signal.emit(success, f"处理完成: {os.path.basename(latest_file)}")
            
        except Exception as e:
            self.finished_signal.emit(False, f"转换过程中发生错误: {str(e)}")
    
    def stop(self):
        self.is_running = False
        
    def erp_to_cubemap(self, erp_img, output_size):
        """将ERP等距圆柱投影图像转换为立方体贴图"""
        # 将ERP图像转换为numpy数组
        erp_arr = np.array(erp_img)
        h, w = erp_arr.shape[:2]
        
        # 创建六个面的空白图像
        faces = []
        for _ in range(6):
            faces.append(np.zeros((output_size, output_size, 3), dtype=np.uint8))
        
        # 定义面的顺序和对应的3D坐标映射（修正后的顺序）
        face_configs = [
            {"name": "前", "coords": lambda u, v: (1.0, v, u)},      # 前面: x=1
            {"name": "后", "coords": lambda u, v: (-1.0, v, -u)},    # 后面: x=-1
            {"name": "左", "coords": lambda u, v: (-u, v, 1.0)},     # 左面: z=1
            {"name": "右", "coords": lambda u, v: (u, v, -1.0)},     # 右面: z=-1
            {"name": "上", "coords": lambda u, v: (u, 1.0, v)},      # 上面: y=1
            {"name": "下", "coords": lambda u, v: (u, -1.0, -v)}     # 下面: y=-1
        ]
        
        # 对于输出图像的每个像素
        for face_idx in range(6):
            if not self.is_running:
                break
                
            face_name = face_configs[face_idx]["name"]
            self.progress_signal.emit(f"  正在处理 {face_name} 面...")
            
            for i in range(output_size):
                if not self.is_running:
                    break
                    
                # 每处理10行更新一次进度
                if i % 10 == 0:
                    self.progress_signal.emit(f"  {face_name}面进度: {i}/{output_size} 行")
                
                for j in range(output_size):
                    # 将2D坐标转换为3D立方体坐标
                    u = 2.0 * i / output_size - 1.0
                    v = 2.0 * j / output_size - 1.0
                    
                    # 根据当前面选择适当的3D坐标
                    coord_func = face_configs[face_idx]["coords"]
                    x, y, z = coord_func(u, v)
                    
                    # 将3D坐标转换为球面坐标
                    r = math.sqrt(x*x + y*y + z*z)
                    theta = math.atan2(z, x)  # 经度角度
                    phi = math.asin(y / r) if r != 0 else 0  # 纬度角度
                    
                    # 将球面坐标转换为ERP坐标
                    erp_x = (theta + math.pi) / (2 * math.pi) * w
                    erp_y = (math.pi/2 - phi) / math.pi * h
                    
                    # 确保坐标在图像范围内
                    erp_x = min(max(0, erp_x), w-1)
                    erp_y = min(max(0, erp_y), h-1)
                    
                    # 从ERP图像中取样
                    try:
                        faces[face_idx][j, i] = erp_arr[int(erp_y), int(erp_x)]
                    except:
                        # 如果取样失败，使用黑色
                        faces[face_idx][j, i] = [0, 0, 0]
        
        # 将numpy数组转换回PIL图像
        face_imgs = []
        for face_arr in faces:
            face_imgs.append(Image.fromarray(face_arr))
        
        return face_imgs
    
    def save_individual_panorama_faces(self, faces, output_dir):
        """保存6张单独的panorama图片"""
        # faces顺序: [前, 后, 左, 右, 上, 下]
        # panorama顺序: [下, 右, 后, 左, 上, 前] (panorama_0和panorama_5互换)
        
        panorama_mapping = [
            {"index": 5, "name": "panorama_5", "desc": "下", "transform": "rotate90_vertical_flip"},    # 下面 - 逆时针90度+垂直翻转
            {"index": 3, "name": "panorama_1", "desc": "右", "transform": "vertical_flip"},             # 右面 - 垂直翻转
            {"index": 1, "name": "panorama_0", "desc": "后", "transform": "vertical_flip"},             # 后面 - 垂直翻转
            {"index": 2, "name": "panorama_3", "desc": "左", "transform": "vertical_flip"},             # 左面 - 垂直翻转
            {"index": 4, "name": "panorama_4", "desc": "上", "transform": "rotate90_horizontal_flip"},  # 上面 - 逆时针90度+水平翻转
            {"index": 0, "name": "panorama_2", "desc": "前", "transform": "vertical_flip"}              # 前面 - 垂直翻转
        ]
        
        for mapping in panorama_mapping:
            face_img = faces[mapping["index"]]
            
            # 应用相应的变换
            if mapping["transform"] == "vertical_flip":
                face_img = face_img.transpose(Image.FLIP_TOP_BOTTOM)
                self.progress_signal.emit(f"    ✓ 已垂直翻转 {mapping['desc']}面")
            elif mapping["transform"] == "rotate90_horizontal_flip":
                # 逆时针旋转90度 + 水平翻转
                face_img = face_img.transpose(Image.ROTATE_90)
                face_img = face_img.transpose(Image.FLIP_LEFT_RIGHT)
                self.progress_signal.emit(f"    ✓ 已逆时针90度+水平翻转 {mapping['desc']}面")
            elif mapping["transform"] == "rotate90_vertical_flip":
                # 逆时针旋转90度 + 垂直翻转
                face_img = face_img.transpose(Image.ROTATE_90)
                face_img = face_img.transpose(Image.FLIP_TOP_BOTTOM)
                self.progress_signal.emit(f"    ✓ 已逆时针90度+垂直翻转 {mapping['desc']}面")
            
            output_path = os.path.join(output_dir, f"{mapping['name']}.png")
            face_img.save(output_path, format="PNG")
            self.progress_signal.emit(f"    ✓ 已保存 {mapping['desc']}面: {mapping['name']}.png")
        
    def create_skybox(self, faces, output_size):
        """
        将六个面的立方体贴图组合成天空盒格式
        第一行：5 4 2 (下, 上, 后)
        第二行：3 0 1 (左, 前, 右)
        """
        self.progress_signal.emit("  正在组合天空盒图像...")
        
        # 天空盒布局 (3x2网格)
        skybox_width = 3 * output_size
        skybox_height = 2 * output_size
        
        # 创建RGB画布
        skybox = Image.new('RGB', (skybox_width, skybox_height))
        
        # faces顺序: [前, 后, 左, 右, 上, 下]
        # 天空盒顺序: 
        # 第一行：5(下) 4(上) 2(后) -> [5, 4, 1]
        # 第二行：3(左) 0(前) 1(右) -> [2, 0, 3]
        
        # 定义天空盒布局映射
        skybox_layout = [
            # 第一行
            {"face_index": 5, "name": "下", "position": (0, 0), "transform": "rotate90_vertical_flip"},  # 下面 - 逆时针90度+垂直翻转
            {"face_index": 4, "name": "上", "position": (1, 0), "transform": "rotate90_horizontal_flip"},  # 上面 - 逆时针90度+水平翻转
            {"face_index": 0, "name": "后", "position": (2, 0), "transform": "vertical_flip"},   # 后面 - 垂直翻转
            # 第二行
            {"face_index": 2, "name": "左", "position": (0, 1), "transform": "vertical_flip"},   # 左面 - 垂直翻转
            {"face_index": 1, "name": "前", "position": (1, 1), "transform": "vertical_flip"},   # 前面 - 垂直翻转
            {"face_index": 3, "name": "右", "position": (2, 1), "transform": "vertical_flip"}    # 右面 - 垂直翻转
        ]
        
        for item in skybox_layout:
            face_img = faces[item["face_index"]]
            
            # 应用相应的变换
            if item["transform"] == "vertical_flip":
                face_img = face_img.transpose(Image.FLIP_TOP_BOTTOM)
                self.progress_signal.emit(f"    ✓ 已垂直翻转 {item['name']}面")
            elif item["transform"] == "rotate90_horizontal_flip":
                # 逆时针旋转90度 + 水平翻转
                face_img = face_img.transpose(Image.ROTATE_90)
                face_img = face_img.transpose(Image.FLIP_LEFT_RIGHT)
                self.progress_signal.emit(f"    ✓ 已逆时针90度+水平翻转 {item['name']}面")
            elif item["transform"] == "rotate90_vertical_flip":
                # 逆时针旋转90度 + 垂直翻转
                face_img = face_img.transpose(Image.ROTATE_90)
                face_img = face_img.transpose(Image.FLIP_TOP_BOTTOM)
                self.progress_signal.emit(f"    ✓ 已逆时针90度+垂直翻转 {item['name']}面")
            
            x, y = item["position"]
            skybox.paste(face_img, (x * output_size, y * output_size))
            self.progress_signal.emit(f"    ✓ 已放置{item['name']}面")
        
        return skybox
    
    def process_image(self, input_path, output_dir, output_size):
        """处理单个图像文件"""
        try:
            if not self.is_running:
                return False
                
            start_time = time.time()
            
            # 打开图像
            self.progress_signal.emit(f"[{time.strftime('%H:%M:%S')}] 开始处理: {os.path.basename(input_path)}")
            erp_img = Image.open(input_path)
            
            # 显示图像信息
            self.progress_signal.emit(f"  原图尺寸: {erp_img.size[0]}x{erp_img.size[1]}")
            self.progress_signal.emit(f"  输出尺寸: 每个面 {output_size}x{output_size}")
            
            # 转换为RGB模式（确保处理所有类型的图像）
            if erp_img.mode != 'RGB':
                erp_img = erp_img.convert('RGB')
                self.progress_signal.emit("  已转换为RGB模式")
            
            # 转换为立方体贴图
            self.progress_signal.emit("  开始转换ERP到立方体贴图...")
            face_imgs = self.erp_to_cubemap(erp_img, output_size)
            
            if not self.is_running:
                return False
                
            self.progress_signal.emit("  ✓ 立方体贴图转换完成")
            
            # 创建输出目录
            os.makedirs(output_dir, exist_ok=True)
            
            # 先保存6张单独的panorama图片
            if self.save_individual_faces:
                self.progress_signal.emit("  正在保存6张单独的panorama图片...")
                self.save_individual_panorama_faces(face_imgs, output_dir)
                self.progress_signal.emit("  ✓ 6张panorama图片保存完成")
            
            # 再创建天空盒图像
            self.progress_signal.emit("  正在生成天空盒图像...")
            skybox = self.create_skybox(face_imgs, output_size)
            
            # 保存天空盒图像
            skybox_path = os.path.join(output_dir, "sky0.png")
            skybox.save(skybox_path, format="PNG")
            
            # 计算处理时间
            processing_time = time.time() - start_time
            self.progress_signal.emit(f"  ✓ 已保存天空盒: sky0.png")
            self.progress_signal.emit(f"  ✓ 处理完成，耗时: {processing_time:.2f}秒")
            
            return True
            
        except Exception as e:
            self.progress_signal.emit(f"  ✗ 处理 {os.path.basename(input_path)} 时出错: {e}")
            return False


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("等距圆柱投射全景图转天空盒转换器")
        self.setGeometry(100, 100, 800, 600)
        
        # 创建中央部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # 创建主布局
        layout = QVBoxLayout(central_widget)
        
        # 创建输入组
        input_group = QGroupBox("输入设置")
        input_layout = QVBoxLayout()
        
        # 输入目录
        input_dir_layout = QHBoxLayout()
        input_dir_layout.addWidget(QLabel("输入目录:"))
        self.input_dir_edit = QLineEdit("input")
        input_dir_layout.addWidget(self.input_dir_edit)
        self.input_dir_btn = QPushButton("浏览...")
        self.input_dir_btn.clicked.connect(self.browse_input_dir)
        input_dir_layout.addWidget(self.input_dir_btn)
        input_layout.addLayout(input_dir_layout)
        
        # 刷新按钮
        self.refresh_btn = QPushButton("刷新最新文件")
        self.refresh_btn.clicked.connect(self.refresh_latest_file)
        input_layout.addWidget(self.refresh_btn)
        
        # 当前文件显示
        self.current_file_label = QLabel("最新文件: 无")
        input_layout.addWidget(self.current_file_label)
        
        # 输出目录
        output_dir_layout = QHBoxLayout()
        output_dir_layout.addWidget(QLabel("输出目录:"))
        self.output_dir_edit = QLineEdit("output")
        output_dir_layout.addWidget(self.output_dir_edit)
        self.output_dir_btn = QPushButton("浏览...")
        self.output_dir_btn.clicked.connect(self.browse_output_dir)
        output_dir_layout.addWidget(self.output_dir_btn)
        input_layout.addLayout(output_dir_layout)
        
        # 输出尺寸
        size_layout = QHBoxLayout()
        size_layout.addWidget(QLabel("输出尺寸:"))
        self.size_spin = QSpinBox()
        self.size_spin.setRange(64, 4096)
        self.size_spin.setValue(512)
        self.size_spin.setSingleStep(64)
        size_layout.addWidget(self.size_spin)
        size_layout.addWidget(QLabel("像素"))
        size_layout.addStretch()
        input_layout.addLayout(size_layout)
        
        # 是否保存单独的面
        self.save_faces_checkbox = QCheckBox("保存6张单独的panorama图片")
        self.save_faces_checkbox.setChecked(True)
        input_layout.addWidget(self.save_faces_checkbox)
        
        input_group.setLayout(input_layout)
        layout.addWidget(input_group)
        
        # 创建按钮
        button_layout = QHBoxLayout()
        self.start_btn = QPushButton("开始转换")
        self.start_btn.clicked.connect(self.start_conversion)
        self.start_btn.setStyleSheet("QPushButton { background-color: #4CAF50; color: white; font-weight: bold; }")
        button_layout.addWidget(self.start_btn)
        
        self.stop_btn = QPushButton("停止转换")
        self.stop_btn.clicked.connect(self.stop_conversion)
        self.stop_btn.setEnabled(False)
        self.stop_btn.setStyleSheet("QPushButton { background-color: #f44336; color: white; font-weight: bold; }")
        button_layout.addWidget(self.stop_btn)
        
        layout.addLayout(button_layout)
        
        # 创建输出组
        output_group = QGroupBox("转换进度")
        output_layout = QVBoxLayout()
        
        self.output_text = QTextEdit()
        self.output_text.setReadOnly(True)
        font = QFont("Consolas", 9)
        self.output_text.setFont(font)
        output_layout.addWidget(self.output_text)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        output_layout.addWidget(self.progress_bar)
        
        output_group.setLayout(output_layout)
        layout.addWidget(output_group)
        
        # 初始化转换线程
        self.conversion_thread = None
        
        # 刷新最新文件
        self.refresh_latest_file()
        
    def browse_input_dir(self):
        directory = QFileDialog.getExistingDirectory(self, "选择输入目录", self.input_dir_edit.text())
        if directory:
            self.input_dir_edit.setText(directory)
            self.refresh_latest_file()
            
    def browse_output_dir(self):
        directory = QFileDialog.getExistingDirectory(self, "选择输出目录", self.output_dir_edit.text())
        if directory:
            self.output_dir_edit.setText(directory)
            
    def refresh_latest_file(self):
        """刷新并显示最新的文件"""
        input_dir = self.input_dir_edit.text()
        if not os.path.exists(input_dir):
            self.current_file_label.setText("最新文件: 目录不存在")
            return
            
        supported_formats = ('.png', '.jpg', '.jpeg', '.bmp', '.tiff', '.webp')
        input_files = []
        for file in os.listdir(input_dir):
            if file.lower().endswith(supported_formats):
                file_path = os.path.join(input_dir, file)
                input_files.append((file_path, os.path.getmtime(file_path)))
        
        if not input_files:
            self.current_file_label.setText("最新文件: 无")
            return
            
        # 按修改时间排序，获取最新的文件
        input_files.sort(key=lambda x: x[1], reverse=True)
        latest_file = input_files[0][0]
        self.current_file_label.setText(f"最新文件: {os.path.basename(latest_file)}")
            
    def start_conversion(self):
        input_dir = self.input_dir_edit.text()
        output_dir = self.output_dir_edit.text()
        output_size = self.size_spin.value()
        save_individual_faces = self.save_faces_checkbox.isChecked()
        
        if not os.path.exists(input_dir):
            QMessageBox.warning(self, "错误", "输入目录不存在！")
            return
            
        # 清空输出文本
        self.output_text.clear()
        
        # 创建输出目录
        os.makedirs(output_dir, exist_ok=True)
        
        # 禁用开始按钮，启用停止按钮
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.progress_bar.setVisible(True)
        
        # 创建并启动转换线程
        self.conversion_thread = ConversionThread(input_dir, output_dir, output_size, save_individual_faces)
        self.conversion_thread.progress_signal.connect(self.update_progress)
        self.conversion_thread.finished_signal.connect(self.conversion_finished)
        self.conversion_thread.start()
        
    def stop_conversion(self):
        if self.conversion_thread and self.conversion_thread.isRunning():
            self.conversion_thread.stop()
            self.conversion_thread.wait()
            self.output_text.append("用户停止了转换过程")
            
    def conversion_finished(self, success, message):
        # 启用开始按钮，禁用停止按钮
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.progress_bar.setVisible(False)
        
        if success:
            self.output_text.append(message)
        else:
            self.output_text.append(f"错误: {message}")
            
    def update_progress(self, message):
        self.output_text.append(message)
        # 自动滚动到底部
        self.output_text.moveCursor(QTextCursor.End)
        
    def closeEvent(self, event):
        # 确保在关闭窗口时停止转换线程
        if self.conversion_thread and self.conversion_thread.isRunning():
            self.conversion_thread.stop()
            self.conversion_thread.wait()
        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())