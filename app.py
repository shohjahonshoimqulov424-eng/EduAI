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
