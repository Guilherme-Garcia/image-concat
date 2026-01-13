# Updated app.py to support PyInstaller bundling and auto-open browser for packaged exe.
import os
import sys
import io
import threading
import time
import webbrowser
from flask import Flask, render_template, request, jsonify, send_file, abort
from werkzeug.utils import secure_filename
from PIL import Image

ALLOWED_EXT = {'.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp'}

# When bundled by PyInstaller:
# - bundle_dir is where PyInstaller extracts templates/static (sys._MEIPASS)
# - run_dir is where we want to store persistent data (next to the exe)
if getattr(sys, 'frozen', False):
    bundle_dir = getattr(sys, '_MEIPASS', os.path.abspath(os.path.dirname(__file__)))
    run_dir = os.path.dirname(sys.executable)
else:
    bundle_dir = os.path.abspath(os.path.dirname(__file__))
    run_dir = bundle_dir

TEMPLATES_DIR = os.path.join(bundle_dir, 'templates')
STATIC_DIR = os.path.join(bundle_dir, 'static')

# Create the Flask app pointing to bundled templates/static
app = Flask(__name__, template_folder=TEMPLATES_DIR, static_folder=STATIC_DIR)

APP_ROOT = run_dir
UPLOADS_DIR = os.path.join(APP_ROOT, "uploads")
OUTPUTS_DIR = os.path.join(APP_ROOT, "outputs")

# Ensure these directories exist at runtime (so PyInstaller build won't fail if created first)
os.makedirs(UPLOADS_DIR, exist_ok=True)
os.makedirs(OUTPUTS_DIR, exist_ok=True)


def allowed_filename(fn: str) -> bool:
    _, ext = os.path.splitext(fn.lower())
    return ext in ALLOWED_EXT


def safe_path_within(base: str, target: str) -> str:
    full = os.path.abspath(os.path.join(base, target))
    if os.path.commonpath([base, full]) != base:
        raise ValueError("Path outside allowed base")
    return full


def open_image_from_path(path: str) -> Image.Image:
    return Image.open(path).convert("RGBA")


def scale_image(im: Image.Image, max_w: int = None, max_h: int = None) -> Image.Image:
    if max_w is None and max_h is None:
        return im
    w, h = im.size
    if max_w is not None and max_h is not None:
        ratio = min(max_w / w, max_h / h)
    elif max_w is not None:
        ratio = max_w / w
    else:
        ratio = max_h / h
    if ratio <= 0:
        return im
    new_w = max(1, int(w * ratio))
    new_h = max(1, int(h * ratio))
    if new_w == w and new_h == h:
        return im
    return im.resize((new_w, new_h), Image.LANCZOS)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/list_folder", methods=["POST"])
def list_folder():
    folder = request.form.get("folder", "")
    try:
        target = safe_path_within(APP_ROOT, folder)
    except Exception:
        return jsonify({"ok": False, "error": "Invalid folder path"}), 400

    if not os.path.isdir(target):
        return jsonify({"ok": False, "error": "Folder does not exist"}), 400

    items = []
    for name in sorted(os.listdir(target)):
        if allowed_filename(name):
            items.append(name)
    return jsonify({"ok": True, "images": items})


@app.route("/thumbnail/<path:folder>/<filename>")
def thumbnail(folder, filename):
    try:
        folder_path = safe_path_within(APP_ROOT, folder)
    except Exception:
        abort(404)
    full = os.path.join(folder_path, filename)
    if not os.path.isfile(full) or not allowed_filename(filename):
        abort(404)
    try:
        im = Image.open(full).convert("RGBA")
        im.thumbnail((240, 240))
        buf = io.BytesIO()
        im.save(buf, format="PNG")
        buf.seek(0)
        return send_file(buf, mimetype="image/png")
    except Exception:
        abort(404)


@app.route("/concatenate", methods=["POST"])
def concatenate():
    mode = request.form.get("mode", "upload")
    orientation = request.form.get("orientation", "horizontal")
    output_name = request.form.get("output_name", "output.png").strip()
    if output_name == "":
        output_name = "output.png"
    if not os.path.splitext(output_name)[1]:
        output_name += ".png"
    output_name = secure_filename(output_name)

    resize_mode = request.form.get("resize_mode", "none")
    try:
        max_w = int(request.form.get("max_width")) if request.form.get("max_width") else None
    except ValueError:
        max_w = None
    try:
        max_h = int(request.form.get("max_height")) if request.form.get("max_height") else None
    except ValueError:
        max_h = None

    alignment = request.form.get("alignment", "center")

    images = []
    temp_saved_files = []

    try:
        if mode == "upload":
            files = request.files.getlist("images")
            if not files:
                return jsonify({"ok": False, "error": "No files uploaded"}), 400
            for f in files:
                filename = secure_filename(f.filename)
                if filename == "" or not allowed_filename(filename):
                    continue
                save_path = os.path.join(UPLOADS_DIR, filename)
                base, ext = os.path.splitext(filename)
                i = 1
                while os.path.exists(save_path):
                    save_path = os.path.join(UPLOADS_DIR, f"{base}_{i}{ext}")
                    i += 1
                f.save(save_path)
                temp_saved_files.append(save_path)
                images.append(open_image_from_path(save_path))
        else:
            folder = request.form.get("folder", "")
            selected = request.form.getlist("selected[]")
            try:
                folder_path = safe_path_within(APP_ROOT, folder)
            except Exception:
                return jsonify({"ok": False, "error": "Invalid folder path"}), 400
            if not os.path.isdir(folder_path):
                return jsonify({"ok": False, "error": "Folder not found"}), 400
            if not selected:
                return jsonify({"ok": False, "error": "No server-side images selected"}), 400
            for name in selected:
                if not allowed_filename(name):
                    continue
                full = os.path.join(folder_path, name)
                if not os.path.isfile(full):
                    continue
                images.append(open_image_from_path(full))

        if not images:
            return jsonify({"ok": False, "error": "No valid images found"}), 400

        if resize_mode == "match_height":
            target_h = max(im.height for im in images)
            images = [scale_image(im, max_h=target_h) for im in images]
        elif resize_mode == "match_width":
            target_w = max(im.width for im in images)
            images = [scale_image(im, max_w=target_w) for im in images]
        elif resize_mode == "fit_max":
            if max_w is None and max_h is None:
                pass
            else:
                images = [scale_image(im, max_w=max_w, max_h=max_h) for im in images]

        widths = [im.width for im in images]
        heights = [im.height for im in images]

        if orientation == "horizontal":
            total_w = sum(widths)
            max_h = max(heights)
            canvas = Image.new("RGBA", (total_w, max_h), (255, 255, 255, 255))
            x = 0
            for im in images:
                if alignment == "start":
                    y = 0
                elif alignment == "end":
                    y = max_h - im.height
                else:
                    y = (max_h - im.height) // 2
                canvas.paste(im, (x, y), im)
                x += im.width
        else:
            total_h = sum(heights)
            max_w2 = max(widths)
            canvas = Image.new("RGBA", (max_w2, total_h), (255, 255, 255, 255))
            y = 0
            for im in images:
                if alignment == "start":
                    x = 0
                elif alignment == "end":
                    x = max_w2 - im.width
                else:
                    x = (max_w2 - im.width) // 2
                canvas.paste(im, (x, y), im)
                y += im.height

        save_option = request.form.get("save_option", "download")
        if save_option == "save":
            save_folder = request.form.get("save_folder", "outputs")
            try:
                dest_root = safe_path_within(APP_ROOT, save_folder)
            except Exception:
                return jsonify({"ok": False, "error": "Invalid save folder"}), 400
            os.makedirs(dest_root, exist_ok=True)
            out_path = os.path.join(dest_root, output_name)
            _, ext = os.path.splitext(output_name.lower())
            if ext in {".jpg", ".jpeg"}:
                canvas.convert("RGB").save(out_path)
            else:
                canvas.save(out_path)
            return jsonify({"ok": True, "saved": True, "path": os.path.relpath(out_path, APP_ROOT)})
        else:
            buf = io.BytesIO()
            _, ext = os.path.splitext(output_name.lower())
            if ext in {".jpg", ".jpeg"}:
                canvas.convert("RGB").save(buf, format="JPEG")
                mimetype = "image/jpeg"
            else:
                canvas.save(buf, format="PNG")
                mimetype = "image/png"
            buf.seek(0)
            return send_file(buf, as_attachment=True, download_name=output_name, mimetype=mimetype)
    finally:
        for p in temp_saved_files:
            try:
                os.remove(p)
            except Exception:
                pass


def open_browser_delayed(url, delay=0.8):
    try:
        time.sleep(delay)
        webbrowser.open(url)
    except Exception:
        pass


if __name__ == "__main__":
    host = "127.0.0.1"
    port = 5000
    url = f"http://{host}:{port}/"
    try:
        threading.Thread(target=open_browser_delayed, args=(url, 0.8), daemon=True).start()
    except Exception:
        pass
    app.run(host=host, port=port, debug=False, use_reloader=False)