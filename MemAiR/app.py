from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from PIL import Image, ImageDraw, ImageFont
from gigachat import GigaChat
from gigachat.models import Chat, Messages, MessagesRole
import re
import os
import base64
import time
import io
import requests

app = Flask(__name__)
app.secret_key = "change-me-in-production"

# --- НАСТРОЙКИ GIGACHAT ---
GIGACHAT_CREDENTIALS = "MDFhMTdhYTEtMmNlYy03YzAyLWFlYzYtNGU0NDEyZTg4YmUzOjVkYjNlMjUzLTQ4NTktNDg5OS1iMzQ2LTQyMWZhYzBlNzE5Yg=="

# --- ЖЕСТКАЯ ПРИВЯЗКА ПУТЕЙ ---
# Получаем абсолютный путь к папке, где лежит app.py
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Строим путь к папке uploads относительно BASE_DIR
app.config['UPLOAD_FOLDER'] = os.path.join(BASE_DIR, 'static', 'uploads')
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Указываем Flask, где искать статические файлы (css, js, images)
app.static_folder = os.path.join(BASE_DIR, 'static')


USERS = {}  
PROJECTS = [
    {"id": 1, "title": "Кот в костюме", "author": "Максим Иванов", "author_email": "max@mail.ru", "status": "published", "score": 70, "likes": 342, "dislikes": 2, "image": "mem1.webp"},
    {"id": 2, "title": "Команда MemAIr", "author": "Сергей Чекмасов", "author_email": "sergey@mail.ru", "status": "published", "score": 100, "likes": 128, "dislikes": 5, "image": "mem2.png"},
    {"id": 3, "title": "Мем про Шрека", "author": "Артем Ефимов", "author_email": "artem@mail.ru", "status": "published", "score": 87, "likes": 215, "dislikes": 12, "image": "mem3.gif"},
]

def login_required(f):
    @wraps(f)
    def wrapper(*a, **kw):
        if "email" not in session:
            return redirect(url_for("login"))
        return f(*a, **kw)
    return wrapper

@app.route("/")
def feed():
    sort_type = request.args.get('sort', 'fresh')
    items = [p for p in PROJECTS if p["status"] == "published"]
    
    if sort_type == 'popular':
        items.sort(key=lambda x: x['likes'], reverse=True)
    elif sort_type == 'ai':
        items.sort(key=lambda x: x['score'], reverse=True)
    else:
        items.sort(key=lambda x: x['id'], reverse=True)
        
    user = USERS.get(session.get("email"))
    return render_template("feed.html", items=items, user=user, current_sort=sort_type)

@app.route("/editor")
def editor():
    user = USERS.get(session.get("email"))
    return render_template("editor.html", user=user)

@app.route("/ai")
def ai():
    user = USERS.get(session.get("email"))
    return render_template("ai.html", user=user)

@app.route("/register", methods=["GET", "POST"])
def register():
    errors, form = {}, {}
    if request.method == "POST":
        form = {k: request.form.get(k, "").strip() for k in ("name", "email")}
        pw, pw2 = request.form.get("password", ""), request.form.get("password2", "")
        
        if len(form["name"]) < 2: errors["name"] = "Введите имя (минимум 2 символа)"
        if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", form["email"]): errors["email"] = "Некорректный e-mail"
        elif form["email"].lower() in USERS: errors["email"] = "Этот e-mail уже зарегистрирован"
        if len(pw) < 6: errors["password"] = "Пароль — минимум 6 символов"
        if pw != pw2: errors["password2"] = "Пароли не совпадают"
        if not request.form.get("agree"): errors["agree"] = "Нужно принять условия"
        
        if not errors:
            email = form["email"].lower()
            USERS[email] = {
                "name": form["name"], 
                "hash": generate_password_hash(pw),
                "avatar": None, 
                "achievements": ["Новичок"]
            }
            session["email"] = email
            return redirect(url_for("feed"))
            
    return render_template("register.html", errors=errors, form=form, user=None)

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        u = USERS.get(request.form.get("email", "").lower())
        if u and check_password_hash(u["hash"], request.form.get("password", "")):
            session["email"] = request.form["email"].lower()
            return redirect(url_for("feed"))
        flash("Неверный e-mail или пароль")
    return render_template("login.html", user=None)

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("feed"))

@app.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    email = session["email"]
    user = USERS.get(email)
    
    if request.method == "POST":
        new_name = request.form.get("name", "").strip()
        if len(new_name) >= 2:
            user["name"] = new_name
            
            file = request.files.get("avatar_file")
            if file and file.filename != '':
                filename = secure_filename(file.filename)
                filename = f"{email.split('@')[0]}_{filename}"
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(filepath)
                user["avatar"] = url_for('static', filename=f'uploads/{filename}')
            
            if "Стилист" not in user["achievements"]:
                user["achievements"].append("Стилист")
                
            flash("Профиль успешно обновлен!")
            return redirect(url_for("profile"))

    my_projects = [p for p in PROJECTS if p["author_email"] == email]
    return render_template("profile.html", user=user, email=email, my_projects=my_projects)

@app.route("/projects")
@login_required
def projects():
    email = session["email"]
    user = USERS.get(email)
    my_items = [p for p in PROJECTS if p["author_email"] == email]
    return render_template("projects.html", items=my_items, user=user)

@app.route("/projects/<int:project_id>/publish", methods=["POST"])
@login_required
def publish_project(project_id):
    email = session["email"]
    for p in PROJECTS:
        if p["id"] == project_id and p["author_email"] == email:
            p["status"] = "published"
            break
    return redirect(url_for("projects"))


# ==========================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ДЛЯ AI
# ==========================================

def generate_image_gigachat(prompt_text):
    """Генерация картинки через встроенную функцию text2image в GigaChat"""
    try:
        giga = GigaChat(
            base_url="https://api.giga.chat/v1",
            credentials=GIGACHAT_CREDENTIALS,
            verify_ssl_certs=False,
            model="GigaChat-2" # Используем стабильную модель для рисования
        )
        
        payload = Chat(
            messages=[
                Messages(role=MessagesRole.SYSTEM, content="Ты — Василий Кандинский. Ты генерируешь изображения по запросу пользователя."),
                Messages(role=MessagesRole.USER, content=prompt_text)
            ],
            function_call="auto"
        )
        
        response = giga.chat(payload)
        answer_text = response.choices[0].message.content
        
        match = re.search(r'<img src="([^"]+)"', answer_text)
        
        if match:
            file_id = match.group(1)
            image = giga.get_image(file_id)
            
            if isinstance(image.content, bytes):
                return base64.b64encode(image.content).decode('utf-8')
            else:
                return image.content
        
        print(f"ОТВЕТ GIGACHAT БЕЗ КАРТИНКИ: {answer_text}")
        return None
        
    except Exception as e:
        print(f"ОШИБКА ГЕНЕРАЦИИ GIGACHAT: {e}")
        return None

def overlay_text_on_image(image_base64, text):
    """Накладывает текст на картинку и возвращает путь к файлу"""
    image_data = base64.b64decode(image_base64)
    img = Image.open(io.BytesIO(image_data)).convert("RGB")
    
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Supplemental/Impact.ttf", size=60)
    except:
        font = ImageFont.load_default()
    
    draw = ImageDraw.Draw(img)
    text = text.upper()
    
    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    x = (img.width - text_width) / 2
    y = 20 
    
    stroke_width = 4
    for dx in range(-stroke_width, stroke_width + 1):
        for dy in range(-stroke_width, stroke_width + 1):
            draw.text((x + dx, y + dy), text, font=font, fill="black")
            
    draw.text((x, y), text, font=font, fill="white")
    
    filename = f"ai_meme_{int(time.time())}.jpg"
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    img.save(filepath)
    
    return url_for('static', filename=f'uploads/{filename}')


# ==========================================
# МАРШРУТ AI-ЧАТА
# ==========================================

@app.route("/api/ai/chat", methods=["POST"])
def ai_chat():
    data = request.get_json()
    user_text = data.get("text", "").strip()
    image_base64 = data.get("image")

    if not user_text and not image_base64:
        return jsonify({"error": "Пустой запрос"}), 400

    lower_text = user_text.lower()

    try:
        giga = GigaChat(
            base_url="https://api.giga.chat/v1",
            credentials=GIGACHAT_CREDENTIALS,
            verify_ssl_certs=False,
            model="GigaChat-2"
        )

        # 1. СЦЕНАРИЙ: Работа с прикрепленной картинкой
        if image_base64:
            image_bytes = base64.b64decode(image_base64)
            uploaded_file = giga.upload_file(("uploaded_image.jpg", image_bytes))
            
            system_prompt = "Ты — помощник по мемам. Опиши картинку и, если пользователь просит, придумай к ней смешную подпись."
            user_prompt = user_text if user_text else "Что на этой картинке? Придумай к ней смешную подпись."
            
            payload = Chat(
                messages=[
                    Messages(role=MessagesRole.SYSTEM, content=system_prompt),
                    Messages(role=MessagesRole.USER, content=user_prompt, 
                             attachments=[{"id": uploaded_file.id_}])
                ]
            )
            response = giga.chat(payload)
            answer = response.choices[0].message.content.strip()
            
            return jsonify({"answer": answer})

        # 2. СЦЕНАРИЙ: Создание полноценного мема
        elif "создай мем" in lower_text or "сделай мем" in lower_text:
            response = giga.chat({
                "messages": [
                    {"role": "system", "content": "Ты — генератор коротких мемных подписей. Отвечай ТОЛЬКО текстом подписи."},
                    {"role": "user", "content": lower_text}
                ]
            })
            caption = response.choices[0].message.content.strip()
            
            prompt_for_bg = lower_text.replace("создай мем", "").replace("сделай мем", "").strip()
            image_b64 = generate_image_gigachat(prompt_for_bg)
            
            if image_b64:
                meme_url = overlay_text_on_image(image_b64, caption)
                return jsonify({"meme_url": meme_url, "caption": caption})
            else:
                return jsonify({"answer": f"Придумал текст: {caption}, но не смог нарисовать фон."})

        # 3. СЦЕНАРИЙ: Просто генерация картинки
        elif any(word in lower_text for word in ["нарисуй", "сгенерируй картинку", "создай картинку", "картинку с", "сгенерируй мем"]):
            prompt = lower_text
            for word in ["нарисуй", "сгенерируй картинку", "создай картинку", "картинку с", "сгенерируй мем"]:
                prompt = prompt.replace(word, "")
            prompt = prompt.strip()
            if not prompt: prompt = "забавный мем"
            
            image_b64 = generate_image_gigachat(prompt)
            if image_b64:
                return jsonify({"image": image_b64})
            return jsonify({"answer": "Не удалось сгенерировать картинку."})

        # 4. СЦЕНАРИЙ: Обычный текстовый чат
        else:
            response = giga.chat({
                "messages": [
                    {"role": "system", "content": "Ты — креативный помощник по мемам. Отвечай кратко, с юмором."},
                    {"role": "user", "content": user_text}
                ]
            })
            answer = response.choices[0].message.content
            return jsonify({"answer": answer})

    except Exception as e:
        print(f"ОШИБКА GIGACHAT: {e}")
        return jsonify({"error": f"Ошибка GigaChat: {str(e)}"}), 500

# ==========================================
# МАРШРУТ РЕДАКТОРА
# ==========================================

@app.route("/api/stickers")
def api_stickers():
    """Возвращает список файлов из static/stickers/"""
    stickers_dir = os.path.join(app.static_folder, "stickers")
    if not os.path.exists(stickers_dir):
        return jsonify([])
    
    files = [
        f for f in os.listdir(stickers_dir)
        if f.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp'))
    ]
    files.sort()
    urls = [url_for('static', filename=f'stickers/{f}') for f in files]
    return jsonify(urls)

if __name__ == "__main__":
    app.run(debug=True, port=5001)