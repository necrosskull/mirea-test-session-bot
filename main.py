import json
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters
from config import TELEGRAM_TOKEN
import logging
from datetime import datetime
from lazy_logger import lazy_logger
import re

weekdays = {
    'понедельник': 1,
    'вторник': 2,
    'среда': 3,
    'четверг': 4,
    'пятница': 5,
    'суббота': 6,
    'воскресенье': 7
}

group_pattern = r'[А-Яа-я]{4}-\d{2}-\d{2}'
exam_pattern = r'экз (.+)|Экз (.+)|ЭКЗ (.+)'
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)


def start(update, context):
    context.bot.send_message(chat_id=update.effective_chat.id,
                             text="Привет!\nНа период сессии включен режим экзаменов.\n"
                                  "Некоторые функции могут быть недоступны.\n"
                                  "Введи фамилию преподавателя.\n")


def search(update, context):
    with open('data/exams.json', 'r', encoding='utf-8') as f:
        exams = json.load(f)

    mode = 'teacher'

    query = update.message.text

    if re.match(group_pattern, query):
        mode = 'group'

    if mode == 'teacher':
        if " " not in query:
            query += " "

    if len(query) < 3:
        context.bot.send_message(chat_id=update.effective_chat.id, text="Слишком короткий запрос")
        return

    lazy_logger.info(json.dumps({"type": "request", "query": query.lower(), **update.message.from_user.to_dict()},
                                ensure_ascii=False))

    if mode == 'teacher':
        exam_ids = [exam_id for exam_id, teacher in exams['teachers'].items() if query.lower() in teacher.lower()]
    else:
        exam_ids = [exam_id for exam_id, group in exams['group'].items() if query.lower() == group.lower()]

    if not exam_ids:
        context.bot.send_message(chat_id=update.effective_chat.id,
                                 text="По вашему запросу ничего не найдено")
        return

    unique_exams = {}
    try:
        for exam_id in exam_ids:
            if (exams['weekday'][exam_id], exams['time_start'][exam_id], exams['weeks'][exam_id]) in unique_exams:
                unique_exams[(exams['weekday'][exam_id], exams['time_start'][exam_id],
                              exams['weeks'][exam_id])]['group'].append(exams['group'][exam_id])
            else:
                unique_exams[(exams['weekday'][exam_id], exams['time_start'][exam_id],
                              exams['weeks'][exam_id])] = {
                    'exam': exams['lesson'][exam_id],
                    'group': [exams['group'][exam_id]],
                    'num': exams['lesson_num'][exam_id],
                    'teacher': exams['teachers'][exam_id],
                    'room': exams['room'][exam_id],
                    'campus': exams['campus'][exam_id][0],
                    'weekday': exams['weekday'][exam_id],
                    'weeks': exams['weeks'][exam_id],
                    'time_start': exams['time_start'][exam_id],
                    'time_end': exams['time_end'][exam_id],
                    'type': exams['type'][exam_id]
                }

        sorted_exams = sorted(unique_exams.items(), key=lambda x: (x[1]['weeks'], weekdays[x[1]['weekday']],
                                                                   x[1]['time_start']))
        text = ""
        blocks = []

        if mode == 'teacher':
            surnames = list(set([exam[1]['teacher'] for exam in sorted_exams]))
            surnames_str = ', '.join(surnames)
            if len(surnames) > 1:
                context.bot.send_message(chat_id=update.effective_chat.id,
                                         text=f"По запросу ({query}) найдено несколько преподавателей:\n\n({surnames_str})"
                                              f"\n\nУточните запрос")
                return

        for exam in sorted_exams:
            groups = ', '.join(exam[1]['group'])
            weekday = exam[1]['weekday'].title()
            time_start = exam[1]['time_start']
            time_end = exam[1]['time_end']
            weeks = exam[1]['weeks']
            campus = exam[1]['campus']
            room = exam[1]['room']
            teacher = exam[1]['teacher']
            teachers = ", ".join([teacher])
            lesson = exam[1]['exam']
            num = exam[1]['num']
            time_start = datetime.strptime(time_start, "%H:%M:%S").strftime("%H:%M")
            time_end = datetime.strptime(time_end, "%H:%M:%S").strftime("%H:%M")

            formatted_time = f"{time_start} – {time_end}"
            text += f'📅 Недели: {weeks}\n'
            text += f"📆 День недели: {weekday}\n"
            text += f'📝 Пара № {num} в ⏰ {formatted_time}\n'
            text += f"🏫 Аудитории: {room} ({campus})\n"
            text += f'📝 {lesson}\n'
            if len(groups) > 0:
                text += f'👥 Группы: {groups}\n'
            if exam[1]['type']:
                text += f'📚 Тип: {exam[1]["type"]}\n'
            text += f"👨🏻‍🏫 Преподаватели: {teachers}\n\n"

            blocks.append(text)
            text = ""
            chunk = ""
            first = True
            for block in blocks:
                if len(chunk) + len(block) <= 4096:
                    chunk += block
                else:
                    if first:
                        context.bot.send_message(chat_id=update.effective_chat.id, text=chunk)
                        first = False
                    else:
                        context.bot.send_message(chat_id=update.effective_chat.id, text=chunk)

                    chunk = block

        context.bot.send_message(chat_id=update.effective_chat.id, text=chunk)

    except Exception as e:
        print(e)
        context.bot.send_message(chat_id=update.effective_chat.id,
                                 text="Произошла ошибка, попробуйте повторить попытку позже")


def main():
    updater = Updater(TELEGRAM_TOKEN, use_context=True)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler('start', start, run_async=True))
    dp.add_handler(CommandHandler('help', start, run_async=True))
    dp.add_handler(MessageHandler(Filters.text, search, run_async=True))

    updater.start_polling()

    updater.idle()


if __name__ == '__main__':
    main()
