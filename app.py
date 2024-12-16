import os
import datetime
import uuid
from dotenv import load_dotenv
from flask import Flask, request, send_from_directory, render_template, url_for, abort
from PIL import Image, ImageOps, ImageDraw
import qrcode
import io

load_dotenv()  # 加载.env

app = Flask(__name__, static_folder='static', static_url_path='/static')

# 配置参数
BASE_URL = os.getenv('BASE_URL', 'https://example.com/').rstrip('/')
HOST = os.getenv('HOST', '127.0.0.1')
PORT = os.getenv('PORT', 5000)
# 上传目录
UPLOAD_FOLDER = os.path.join(app.static_folder, 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB

ALLOWED_EXT = {'png', 'jpg', 'jpeg'}

def allowed_file(filename):
    ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else ''
    return ext in ALLOWED_EXT

def resize_image_if_needed(img):
    # 检查尺寸，若任一边超过2000px则按比例缩放
    w, h = img.size
    max_size = 1500
    if w > max_size or h > max_size:
        # 确定缩放比例
        if w > h:
            # 宽为长边
            ratio = max_size / float(w)
        else:
            # 高为长边
            ratio = max_size / float(h)
        new_w = int(w * ratio)
        new_h = int(h * ratio)
        img = img.resize((new_w, new_h), Image.LANCZOS)
    return img

def compute_average_brightness(img_region):
    # 将图像区域转为灰度并计算平均亮度
    gray = img_region.convert('L')
    hist = gray.histogram()
    # 计算总像素
    total_pixels = img_region.size[0] * img_region.size[1]
    # 计算加权和：sum(value * count)
    brightness = sum(i * hist[i] for i in range(256)) / total_pixels
    return brightness

def generate_qr_code(url, fg_color, bg_color, size):
    # 生成QR code
    qr = qrcode.QRCode(
        version=1,
        box_size=10,
        border=0
    )
    qr.add_data(url)
    qr.make(fit=True)
    img_qr = qr.make_image(fill_color=fg_color, back_color=bg_color).convert('RGBA')
    # 调整QR code大小至指定size
    img_qr = img_qr.resize((size, size), Image.LANCZOS)
    return img_qr

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        file = request.files.get('file')
        if file and allowed_file(file.filename):
            # 获取文件扩展名
            ext = file.filename.rsplit('.', 1)[1].lower()
            # 构建目录 年/月/日
            now = datetime.datetime.now()
            sub_dir = os.path.join(str(now.year), str(now.month), str(now.day))
            target_dir = os.path.join(UPLOAD_FOLDER, sub_dir)
            os.makedirs(target_dir, exist_ok=True)

            # 使用UUID命名文件
            filename_uuid = str(uuid.uuid4()) + '.' + ext
            file_path = os.path.join(target_dir, filename_uuid)

            # 保存原始未压缩的图片
            file.stream.seek(0)
            try:
                img = Image.open(file.stream)
                img.save(file_path, quality=100)
            except Exception:
                return "无效的图片文件", 400

            if img.format.lower() not in ALLOWED_EXT:
                return "文件格式不允许", 400

            # 生成二维码的URL
            relative_path = os.path.join(sub_dir, filename_uuid)
            temp_path = os.path.join('uploads', sub_dir, filename_uuid).replace('\\', '/')
            resource_url = f"{BASE_URL}/{url_for('static', filename=temp_path)}"

            # 对图片进行压缩
            img = resize_image_if_needed(img)

            # 添加二维码
            processed_img = img
            w, h = processed_img.size
            short_side = min(w, h)
            qr_size = int(short_side * 0.15)
            margin_w = int(w * 0.02)
            margin_h = int(h * 0.02)

            # 计算放置位置：右下角
            qr_x = w - margin_w - qr_size
            qr_y = h - margin_h - qr_size

            # 生成二维码
            qr_img = generate_qr_code(resource_url, "black", "white", qr_size)

            # 将二维码贴到图像上
            processed_img.paste(qr_img, (qr_x, qr_y), qr_img)

            # 保存处理后的图像
            processed_filename_uuid = str(uuid.uuid4()) + '.' + ext
            processed_file_path = os.path.join(target_dir, processed_filename_uuid)
            processed_img.save(processed_file_path, quality=50, optimize=True)

            # 返回页面显示原图和带二维码的图
            original_url = url_for('static', filename=os.path.join('uploads', sub_dir, filename_uuid).replace('\\', '/'))
            processed_url = url_for('static', filename=os.path.join('uploads', sub_dir, processed_filename_uuid).replace('\\', '/'))
            return render_template('index.html', original_url=original_url, processed_url=processed_url, resource_url=resource_url)
        else:
            return "文件不合法或缺失", 400

    return render_template('index.html')

if __name__ == "__main__":
    app.run(debug=True, host=HOST, port=PORT)