import json
import logging
import re
from datetime import datetime

from telegram.ext import Updater, CommandHandler, MessageHandler, Filters

from config import TELEGRAM_TOKEN
from lazy_logger import lazy_logger

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)

WEEKDAYS = {
    'понедельник': 1,
    'вторник': 2,
    'среда': 3,
    'четверг': 4,
    'пятница': 5,
    'суббота': 6,
    'воскресенье': 7
}

GROUP_PATTERN = r'[А-Яа-я]{4}-\d{2}-\d{2}'
EXAM_PATTERN = r'экз (.+)|Экз (.+)|ЭКЗ (.+)'


def start(update, context):
    context.bot.send_message(chat_id=update.effective_chat.id,
                             text="Привет!\nНа период сессии включен режим экзаменов.\n"
                                  "Некоторые функции могут быть недоступны.\n"
                                  "Введи фамилию преподавателя.\n")


def search(update, context):
    query = update.message.text
    mode = determine_search_mode(query)

    if mode == 'teacher':
        query = prepare_teacher_query(query)
    elif mode == 'group':
        query = query.lower()

    if len(query) < 3:
        context.bot.send_message(chat_id=update.effective_chat.id, text="Слишком короткий запрос")
        return

    lazy_logger.info(json.dumps({"type": "request", "query": query.lower(), **update.message.from_user.to_dict()},
                                ensure_ascii=False))

    exams = load_exams_from_file()

    exam_ids = find_exam_ids(query, exams, mode)

    if not exam_ids:
        context.bot.send_message(chat_id=update.effective_chat.id,
                                 text="По вашему запросу ничего не найдено")
        return

    unique_exams = group_exams_by_time(exam_ids, exams)
    sorted_exams = sort_exams(unique_exams)
    send_exam_info(update, context, sorted_exams, mode)


def determine_search_mode(query):
    if re.match(GROUP_PATTERN, query):
        return 'group'
    return 'teacher'


def prepare_teacher_query(query):
    if " " not in query:
        query += " "
    return query.lower()


def load_exams_from_file():
    with open('data/exams.json', 'r', encoding='utf-8') as f:
        exams = json.load(f)
    return exams


def find_exam_ids(query, exams, mode):
    if mode == 'teacher':
        exam_ids = [exam_id for exam_id, teacher in exams['teachers'].items() if query in teacher.lower()]
    else:
        exam_ids = [exam_id for exam_id, group in exams['group'].items() if query == group.lower()]
    return exam_ids


def group_exams_by_time(exam_ids, exams):
    unique_exams = {}
    for exam_id in exam_ids:
        key = (exams['weekday'][exam_id], exams['time_start'][exam_id], exams['weeks'][exam_id])
        if key in unique_exams:
            unique_exams[key]['group'].append(exams['group'][exam_id])
        else:
            unique_exams[key] = {
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
    return unique_exams


def sort_exams(unique_exams):
    return sorted(unique_exams.items(), key=lambda x: (x[1]['weeks'], WEEKDAYS[x[1]['weekday']], x[1]['time_start']))


def send_exam_info(update, context, sorted_exams, mode):
    chunks = []
    chunk = ""

    for exam in sorted_exams:
        exam_info = format_exam_info(exam, mode)
        if len(chunk) + len(exam_info) <= 4096:
            chunk += exam_info
        else:
            chunks.append(chunk)
            chunk = exam_info

    if chunk:
        chunks.append(chunk)

    for chunk in chunks:
        context.bot.send_message(chat_id=update.effective_chat.id, text=chunk)


def format_exam_info(exam, mode):
    exam_info = ""
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
    exam_info += f'📅 Недели: {weeks}\n'
    exam_info += f"📆 День недели: {weekday}\n"
    exam_info += f'📝 Пара № {num} в ⏰ {formatted_time}\n'
    exam_info += f"🏫 Аудитории: {room} ({campus})\n"
    exam_info += f'📝 {lesson}\n'
    if len(groups) > 0:
        exam_info += f'👥 Группы: {groups}\n'
    if exam[1]['type']:
        exam_info += f'📚 Тип: {exam[1]["type"]}\n'
    exam_info += f"👨🏻‍🏫 Преподаватели: {teachers}\n\n"

    return exam_info


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
