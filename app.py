import os
import gradio as gr
from groq import Groq

client = Groq(api_key=os.environ["GROQ_API_KEY"])


def ai_savol(savol):
    if not savol.strip():
        return "Savolingizni yozing."

    response = client.chat.completions.create(
        model="openai/gpt-oss-20b",
        messages=[
            {
                "role": "system",
                "content": "Sen EduAI AI o'quv yordamchisisan. Javoblarni o'zbek tilida sodda va tushunarli ber."
            },
            {
                "role": "user",
                "content": savol
            }
        ]
    )

    return response.choices[0].message.content


with gr.Blocks(title="EduAI") as app:
    gr.Markdown("# 🎓 EduAI")
    gr.Markdown("### AI o'quv yordamchingiz")

    savol = gr.Textbox(
        label="💬 Savolingiz",
        placeholder="Savolingizni yozing..."
    )

    javob = gr.Textbox(
        label="🤖 EduAI javobi",
        lines=10
    )

    tugma = gr.Button("🤖 Javob olish")

    tugma.click(
        ai_savol,
        inputs=savol,
        outputs=javob
    )


app.launch(
    server_name="0.0.0.0",
    server_port=int(os.environ.get("PORT", 7860))
)

import os
import base64
from datetime import date
from io import BytesIO

import gradio as gr
from groq import Groq
from PIL import Image

client = Groq(api_key=os.environ["GROQ_API_KEY"])
FREE_LIMIT = 10


def check_limit(state):
    today = str(date.today())
    if not state or state.get("date") != today:
        state = {"date": today, "count": 0}

    if state["count"] >= FREE_LIMIT:
        return state, False

    state["count"] += 1
    return state, True


def ask_ai(prompt, system="Sen EduAI o'quv yordamchisisan. O'zbek tilida sodda va tushunarli javob ber."):
    result = client.chat.completions.create(
        model="openai/gpt-oss-20b",
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": prompt}
        ]
    )
    return result.choices[0].message.content


def question_answer(question, state):
    if not question or not question.strip():
        return state, "Savolingizni yozing."

    state, allowed = check_limit(state)
    if not allowed:
        return state, "Bepul limitingiz tugadi. Premium bo'limini ko'ring."

    try:
        return state, ask_ai(question)
    except Exception as e:
        return state, f"Xatolik: {e}"


def teacher_mode(subject, topic, state):
    if not topic or not topic.strip():
        return state, "Mavzuni yozing."

    state, allowed = check_limit(state)
    if not allowed:
        return state, "Bepul limitingiz tugadi. Premium bo'limini ko'ring."

    prompt = (
        f"Fan: {subject}\nMavzu: {topic}\n"
        "O'qituvchi kabi tushuntir. Sodda misollar, bosqichlar "
        "va oxirida 3 ta mashq ber."
    )

    try:
        return state, ask_ai(prompt)
    except Exception as e:
        return state, f"Xatolik: {e}"


def translate_text(text, language, state):
    if not text or not text.strip():
        return state, "Tarjima qilinadigan matnni kiriting."

    state, allowed = check_limit(state)
    if not allowed:
        return state, "Bepul limitingiz tugadi. Premium bo'limini ko'ring."

    prompt = (
        f"Matnni {language} tiliga tarjima qil. "
        f"Faqat tarjimani qaytar, izoh yozma.\n\n{text}"
    )

    try:
        return state, ask_ai(prompt, "Sen aniq tarjima qiladigan tarjimonsan.")
    except Exception as e:
        return state, f"Xatolik: {e}"


def solve_image(image_path, question, state):
    if not image_path:
        return state, "Avval rasm yuklang."

    state, allowed = check_limit(state)
    if not allowed:
        return state, "Bepul limitingiz tugadi. Premium bo'limini ko'ring."

    try:
        image = Image.open(image_path).convert("RGB")
        image.thumbnail((1024, 1024))
        buffer = BytesIO()
        image.save(buffer, format="JPEG")
        encoded = base64.b64encode(buffer.getvalue()).decode("utf-8")

        result = client.chat.completions.create(
            model="meta-llama/llama-4-scout-17b-16e-instruct",
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": question or
                        "Rasmdagi masalani o'zbek tilida tahlil qil va bosqichma-bosqich yech."
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{encoded}"
                        }
                    }
                ]
            }]
        )
        return state, result.choices[0].message.content

    except Exception as e:
        return state, f"Rasm tahlilida xatolik: {e}"


def premium_info():
    return (
        "EduAI Premium\n\n"
        "Premium obunasi hozircha faqat namoyish rejimida.\n"
        "Haqiqiy to'lov, obuna va Premium limitlarini "
        "boshqarish uchun to'lov tizimi va ma'lumotlar bazasi ulanishi kerak."
    )


with gr.Blocks(title="EduAI", theme=gr.themes.Soft()) as app:
    state = gr.State({"date": str(date.today()), "count": 0})

    gr.Markdown("# 🎓 EduAI")
    gr.Markdown("Sizning aqlli o'quv yordamchingiz")

    with gr.Tab("💬 Savol-javob"):
        question = gr.Textbox(label="Savolingiz", lines=3)
        question_btn = gr.Button("Javob olish", variant="primary")
        question_out = gr.Textbox(label="AI javobi", lines=8)
        question_btn.click(
            question_answer,
            inputs=[question, state],
            outputs=[state, question_out]
        )

    with gr.Tab("👨‍🏫 O'qituvchi"):
        subject = gr.Dropdown(
            [
                "Matematika", "Fizika", "Kimyo", "Biologiya",
                "Tarix", "Informatika", "Ingliz tili", "Boshqa"
            ],
            value="Matematika",
            label="Fanni tanlang"
        )
        topic = gr.Textbox(label="Qaysi mavzuni o'rganmoqchisiz?", lines=3)
        teacher_btn = gr.Button("Tushuntirib ber")
        teacher_out = gr.Textbox(label="Dars", lines=8)
        teacher_btn.click(
            teacher_mode,
            inputs=[subject, topic, state],
            outputs=[state, teacher_out]
        )

    with gr.Tab("🌐 Tarjimon"):
        source_text = gr.Textbox(label="Matn", lines=5)
        language = gr.Dropdown(
            ["O'zbek tili", "Rus tili", "Ingliz tili"],
            value="Ingliz tili",
            label="Qaysi tilga tarjima qilinsin?"
        )
        translate_btn = gr.Button("Tarjima qilish")
        translate_out = gr.Textbox(label="Tarjima", lines=6)
        translate_btn.click(
            translate_text,
            inputs=[source_text, language, state],
            outputs=[state, translate_out]
        )

    with gr.Tab("📷 Rasmli masala"):
        uploaded_image = gr.Image(type="filepath", label="Rasm yuklang")
        
        image_question = gr.Textbox(
            label="Savol (ixtiyoriy)",
            placeholder="Masalani yechib bering"
        )
        image_btn = gr.Button("Rasmni tahlil qilish")
        image_out = gr.Textbox(label="Yechim", lines=8)
        image_btn.click(
            solve_image,
            inputs=[uploaded_image, image_question, state],
            outputs=[state, image_out]
        )

    with gr.Tab("⭐ Premium"):
        gr.Markdown(
            "## EduAI Premium\n"
            "- Bepul foydalanish: kuniga 10 ta so'rov\n"
            "- Premium: kengaytirilgan foydalanish imkoniyati\n\n"
            "**Eslatma:** Premium to'lovi hali ulanmagan."
        )
        premium_btn = gr.Button("Premium haqida")
        premium_out = gr.Textbox(label="Ma'lumot")
        premium_btn.click(premium_info, outputs=premium_out)

    gr.Markdown("EduAI — bilim olishni osonlashtiradi 🎓")


app.launch(
    server_name="0.0.0.0",
    server_port=int(os.environ.get("PORT", 7860))
        )
import os
import requests
import gradio as gr
from groq import Groq

client = Groq(api_key=os.environ["GROQ_API_KEY"])

FIREBASE_API_KEY = "AIzaSyC9Ws94kamddXsQou6u8TeJc4w5itu-QBo"
AUTH_URL = "https://identitytoolkit.googleapis.com/v1/accounts"

def firebase_auth(email, password, action):
    endpoint = "signUp" if action == "signup" else "signInWithPassword"
    try:
        response = requests.post(
            f"{AUTH_URL}:{endpoint}?key={FIREBASE_API_KEY}",
            json={
                "email": email,
                "password": password,
                "returnSecureToken": True
            },
            timeout=20
        )
        data = response.json()

        if response.ok:
            return (
                f"✅ Muvaffaqiyatli: {data['email']}",
                data["idToken"],
                data["localId"]
            )

        error = data.get("error", {}).get("message", "Noma'lum xato")
        return f"❌ Xato: {error}", None, None

    except Exception:
        return "❌ Internet yoki Firebase ulanish xatosi.", None, None

def signup(email, password):
    return firebase_auth(email, password, "signup")

def login(email, password):
    return firebase_auth(email, password, "login")

def ai_answer(question, token):
    if not token:
        return "Avval akkauntingizga kiring."
    if not question or not question.strip():
        return "Savolingizni yozing."

    try:
        result = client.chat.completions.create(
            model="openai/gpt-oss-20b",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Sen EduAI o'quv yordamchisisan. "
                        "O'zbek tilida sodda va tushunarli javob ber."
                    )
                },
                {"role": "user", "content": question}
            ]
        )
        return result.choices[0].message.content
    except Exception as e:
        return f"AI xatosi: {e}"

def translate(text, language, token):
    if not token:
        return "Avval akkauntingizga kiring."
    if not text or not text.strip():
        return "Tarjima uchun matn kiriting."

    return ai_answer(
        f"Quyidagi matnni {language} tiliga tarjima qil. "
        f"Faqat tarjimani chiqar:\n{text}",
        token
    )

def solve_image(image, token):
    if not token:
        return "Avval akkauntingizga kiring."
    if image is None:
        return "Avval rasm yuklang."

    try:
        import base64

        with open(image, "rb") as file:
            encoded = base64.b64encode(file.read()).decode("utf-8")

        result = client.chat.completions.create(
            model="meta-llama/llama-4-scout-17b-16e-instruct",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": (
                                "Rasmdagi matn yoki masalani o'qib, "
                                "o'zbek tilida bosqichma-bosqich yech."
                            )
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{encoded}"
                            }
                        }
                    ]
                }
            ]
        )
        return result.choices[0].message.content
    except Exception as e:
        return (
            "Rasmni yechishda xato. Groq hisobingizda vision modeli "
            f"mavjudligini tekshiring.\n{e}"
        )

with gr.Blocks(title="EduAI") as app:
    gr.Markdown("# 🎓 EduAI")
    gr.Markdown("Ro‘yxatdan o‘ting yoki akkauntingizga kiring.")

    token_state = gr.State(None)
