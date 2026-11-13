"""Bounded images for host Vision; originals remain untouched."""
import hashlib
import io
from pathlib import Path
from PIL import Image, ImageOps, ImageDraw

IMAGE_EXT = {'.jpg', '.jpeg', '.png', '.webp', '.bmp', '.tif', '.tiff'}
VIDEO_EXT = {'.mp4', '.mov', '.avi', '.mkv', '.webm'}


def digest(path):
    with open(path, 'rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def open_image(path):
    with Image.open(path) as original:
        return ImageOps.exif_transpose(original).convert('RGB')


def prepare(path, output):
    kind = 'video' if path.suffix.lower() in VIDEO_EXT else 'photo'
    if kind == 'video':
        import cv2
        cap = cv2.VideoCapture(str(path))
        try:
            fps = cap.get(cv2.CAP_PROP_FPS)
            count = cap.get(cv2.CAP_PROP_FRAME_COUNT)
            if not cap.isOpened() or fps <= 0 or count <= 0:
                raise ValueError('Cannot decode video')
            frames = []
            for fraction in (0.1, 0.3, 0.5, 0.7, 0.9, 0.98):
                cap.set(cv2.CAP_PROP_POS_FRAMES, int((count - 1) * fraction))
                ok, frame = cap.read()
                if not ok:
                    raise ValueError('Cannot decode sampled video frame')
                image = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
                frames.append((f'{int(count / fps * fraction)}s', image))
            img = sheet(frames, columns=3)
        finally:
            cap.release()
    else:
        img = open_image(path)
    width, height = img.size
    small = img.convert('L').resize((9, 8))
    gray = [small.getpixel((x,y)) for y in range(8) for x in range(9)]
    dhash = sum((gray[y*9+x] > gray[y*9+x+1]) << (y*8+x)
                for y in range(8) for x in range(8))
    img.thumbnail((1200, 1200))
    img.save(output, 'JPEG', quality=85)
    return kind, width, height, f'{dhash:016x}'


def sheet(items, columns=3):
    canvas = Image.new('RGB', (columns*320, ((len(items)+columns-1)//columns)*272), '#202020')
    draw = ImageDraw.Draw(canvas)
    for i, (label, image) in enumerate(items):
        image = image.copy()
        image.thumbnail((310, 240))
        x, y = (i % columns)*320, (i//columns)*272
        canvas.paste(image, (x+(320-image.width)//2, y+25+(240-image.height)//2))
        draw.text((x+8, y+6), label, fill='white')
    return canvas


def detail(path, size=1200, crop=None):
    img = open_image(path)
    if crop is not None:
        if (len(crop) != 4 or any(type(v) not in (int, float) for v in crop)
                or not 0 <= crop[0] < crop[2] <= 1 or not 0 <= crop[1] < crop[3] <= 1):
            raise ValueError('crop must be [left,top,right,bottom], normalized 0..1')
        w, h = img.size
        img = img.crop((int(crop[0]*w), int(crop[1]*h), max(int(crop[0]*w)+1,int(crop[2]*w)), max(int(crop[1]*h)+1,int(crop[3]*h))))
    img.thumbnail((size, size))
    data = io.BytesIO()
    img.save(data, 'JPEG', quality=88)
    return data.getvalue()
