import asyncio
import copy
import logging
import os
import random

from aiogram import Bot, Dispatcher
from aiogram.filters import Command
from aiogram.types import Message, PollAnswer
from dotenv import load_dotenv
from openpyxl import load_workbook

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

# =========================================
# CONFIG
# =========================================

load_dotenv()

TOKEN = os.environ.get("BOT_TOKEN")
if not TOKEN:
    raise RuntimeError(
        "BOT_TOKEN topilmadi. Loyiha papkasida .env fayl yarating va "
        "ichiga BOT_TOKEN=your_token_here deb yozing."
    )

QUESTIONS_FILE = os.environ.get("QUESTIONS_FILE", "jismoniy_tarbiya_testlari.xlsx")

bot = Bot(TOKEN)
dp = Dispatcher()

# =========================================
# LOAD QUESTIONS
# =========================================


def load_questions(path: str) -> list[dict]:
    wb = load_workbook(path)
    ws = wb.active

    questions = []
    skipped = 0

    for row_num, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
        try:
            _, question, a, b, c, d, correct, *_ = row

            if not question:
                skipped += 1
                continue

            options = [
                ("A", str(a).strip()),
                ("B", str(b).strip()),
                ("C", str(c).strip()),
                ("D", str(d).strip()),
            ]

            correct = str(correct).strip().upper()

            if correct not in ("A", "B", "C", "D"):
                logger.warning("Row %d: noto'g'ri correct qiymati (%r), o'tkazib yuborildi", row_num, correct)
                skipped += 1
                continue

            random.shuffle(options)

            poll_options = [x[1] for x in options]
            correct_index = next(i for i, x in enumerate(options) if x[0] == correct)

            questions.append(
                {
                    "question": str(question).strip(),
                    "options": poll_options,
                    "correct_index": correct_index,
                }
            )

        except Exception:
            logger.exception("Row %d: qatorni o'qishda xatolik, o'tkazib yuborildi", row_num)
            skipped += 1

    logger.info("Yuklandi: %d ta savol, o'tkazib yuborildi: %d", len(questions), skipped)
    return questions


QUESTIONS = load_questions(QUESTIONS_FILE)

if not QUESTIONS:
    raise RuntimeError(
        f"'{QUESTIONS_FILE}' faylidan bironta ham savol yuklanmadi. "
        "Fayl yo'li va ustunlar tartibini tekshiring."
    )

# =========================================
# USERS (in-memory session state)
# =========================================

users: dict[int, dict] = {}

# =========================================
# START COMMAND
# =========================================


@dp.message(Command("start"))
async def start_test(message: Message):
    # MUHIM: deepcopy - aks holda barcha userlar bitta xotiradagi
    # savol obyektlarini ulashadi va poll_id/score bir-birini buzadi.
    questions = copy.deepcopy(QUESTIONS)
    random.shuffle(questions)

    users[message.from_user.id] = {
        "questions": questions,
        "index": 0,
        "score": 0,
    }

    await message.answer(f"✅ Quiz boshlandi!\n\nJami savollar: {len(questions)}")

    await send_question(user_id=message.from_user.id, chat_id=message.chat.id)


# =========================================
# SEND QUESTION
# =========================================


async def send_question(user_id: int, chat_id: int):
    user = users.get(user_id)
    if user is None:
        return

    index = user["index"]

    if index >= len(user["questions"]):
        score = user["score"]
        total = len(user["questions"])

        await bot.send_message(
            chat_id,
            f"🎉 Test tugadi!\n\n"
            f"✅ To'g'ri javoblar: {score}\n"
            f"❌ Noto'g'ri javoblar: {total - score}\n"
            f"📊 Jami: {total}",
        )

        del users[user_id]
        return

    q = user["questions"][index]

    try:
        poll = await bot.send_poll(
            chat_id=chat_id,
            question=q["question"],
            options=q["options"],
            type="quiz",
            correct_option_id=q["correct_index"],
            is_anonymous=False,
            explanation=f"✅ To'g'ri javob: {q['options'][q['correct_index']]}",
        )
    except Exception:
        logger.exception("Poll yuborishda xatolik (user_id=%s, index=%s)", user_id, index)
        await bot.send_message(chat_id, "⚠️ Savolni yuborishda xatolik yuz berdi, keyingisiga o'tamiz.")
        user["index"] += 1
        await send_question(user_id=user_id, chat_id=chat_id)
        return

    q["poll_id"] = poll.poll.id


# =========================================
# POLL ANSWER
# =========================================


@dp.poll_answer()
async def handle_poll_answer(poll_answer: PollAnswer):
    user_id = poll_answer.user.id

    user = users.get(user_id)
    if user is None:
        return

    index = user["index"]

    if index >= len(user["questions"]):
        return

    q = user["questions"][index]

    if q.get("poll_id") != poll_answer.poll_id:
        # Eski/qoldiq poll javobi - e'tiborsiz qoldiramiz
        return

    if not poll_answer.option_ids:
        # User javobni bekor qildi
        return

    selected = poll_answer.option_ids[0]

    if selected == q["correct_index"]:
        user["score"] += 1

    user["index"] += 1

    await asyncio.sleep(0.5)

    await send_question(user_id=user_id, chat_id=user_id)


# =========================================
# MAIN
# =========================================


async def main():
    logger.info("Bot ishga tushdi...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
