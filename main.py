import asyncio
import random

from aiogram import Bot, Dispatcher
from aiogram.filters import Command
from aiogram.types import Message, PollAnswer

from openpyxl import load_workbook

TOKEN = "8362385287:AAHFnDyohylaB8Pv7iMo1mWd0kSEaqWN_Q0"

bot = Bot(TOKEN)
dp = Dispatcher()

# =========================================
# LOAD QUESTIONS
# =========================================


def load_questions(path):
    wb = load_workbook(path)
    ws = wb.active

    questions = []

    for row in ws.iter_rows(min_row=2, values_only=True):
        (
            _,
            topic,
            question,
            ideal_answer,
            explanation,
            common_mistakes,
            follow_up,
            difficulty,
        ) = row

        questions.append(
            {
                "topic": topic,
                "question": question,
                "answer": ideal_answer,
                "explanation": explanation,
                "mistakes": common_mistakes,
                "follow_up": follow_up,
                "difficulty": difficulty,
            }
        )

    return questions


QUESTIONS = load_questions("Data_Analytics_Interview_100.xlsx")

print(f"Loaded questions: {len(QUESTIONS)}")

# =========================================
# USERS
# =========================================

users = {}

# =========================================
# START COMMAND
# =========================================


@dp.message(Command("start"))
async def start_test(message: Message):

    questions = QUESTIONS[:]

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

    user = users[user_id]

    index = user["index"]

    if index >= len(user["questions"]):
        score = user["score"]

        await bot.send_message(
            chat_id,
            f"🎉 Test tugadi!\n\n"
            f"✅ To'g'ri javoblar: {score}\n"
            f"❌ Noto'g'ri javoblar: {len(user['questions']) - score}\n"
            f"📊 Jami: {len(user['questions'])}",
        )

        del users[user_id]

        return

    q = user["questions"][index]

    poll = await bot.send_poll(
        chat_id=chat_id,
        question=q["question"],
        options=q["options"],
        type="quiz",
        correct_option_id=q["correct_index"],
        is_anonymous=False,
        explanation=f"✅ To'g'ri javob: {q['options'][q['correct_index']]}",
    )

    # SAVE POLL ID
    q["poll_id"] = poll.poll.id


# =========================================
# POLL ANSWER
# =========================================


@dp.poll_answer()
async def handle_poll_answer(poll_answer: PollAnswer):

    user_id = poll_answer.user.id

    if user_id not in users:
        return

    user = users[user_id]

    index = user["index"]

    if index >= len(user["questions"]):
        return

    q = user["questions"][index]

    # CHECK POLL
    if q["poll_id"] != poll_answer.poll_id:
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

    print("Bot started...")

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
