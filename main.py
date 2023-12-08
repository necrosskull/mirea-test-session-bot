import json
import logging
import re
import datetime
from telegram import ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters
from decode import decode_teachers
from config import TELEGRAM_TOKEN
from lazy_logger import lazy_logger
from semester_start import get_semester_start_date_from_period

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

MONTHS = {
    1: "Января",
    2: "Февраля",
    3: "Марта",
    4: "Апреля",
    5: "Мая",
    6: "Июня",
    7: "Июля",
    8: "Августа",
    9: "Сентября",
    10: "Октября",
    11: "Ноября",
    12: "Декабря"
}

GROUP_PATTERN = r'[А-Яа-я]{4}-\d{2}-\d{2}'
EXAM_PATTERN = r'экз (.+)|Экз (.+)|ЭКЗ (.+)'


def load_exams_from_file():
    with open('data/test_session.json', 'r', encoding='utf-8') as f:
        exams = json.load(f)
    return exams


exams = load_exams_from_file()


def start(update, context):
    context.bot.send_message(chat_id=update.effective_chat.id,
                             text="Привет!\nНа период сессии включен режим сессии.\n\n"
                                  "Доступен поиск по преподавателям и группам.\n"
                                  "Введи фамилию преподавателя или группу.\n\n"
                                  "Примеры: \n"
                                  "`Иванов И.А.`\n"
                                  "`Иванов`\n"
                                  "`ИВБО-07-22`", parse_mode='Markdown')


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

    exam_ids = find_exam_ids(query, exams, mode)

    if not exam_ids:
        context.bot.send_message(chat_id=update.effective_chat.id,
                                 text="По вашему запросу ничего не найдено")
        return

    unique_exams = create_unique_exams(exam_ids, exams)
    sorted_exams = sort_exams(unique_exams)

    if mode == 'teacher':
        context.user_data['teacher'] = query
        surnames_count = check_same_surnames(sorted_exams, update, context)
        if surnames_count:
            return

    send_exam_info(update, context, sorted_exams, mode)


def check_same_surnames(sorted_exams, update, context):
    surnames = list(set([exam[1]['teacher'] for exam in sorted_exams]))
    surnames_str = ', '.join(decode_teachers(surnames))
    for surname in surnames:
        if context.user_data['teacher'] == surname.lower():
            return
    surnames_count = len(surnames)
    if surnames_count > 1:
        keyboard = [[surname] for surname in surnames]
        reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)
        context.bot.send_message(chat_id=update.effective_chat.id,
                                 text=f"По запросу ({context.user_data['teacher'][:-1].title()}) найдено несколько "
                                      f"преподавателей:\n\n({surnames_str})"
                                      f"\n\nУточните запрос:",
                                 reply_markup=reply_markup)
        return surnames_count


def determine_search_mode(query):
    if re.match(GROUP_PATTERN, query):
        return 'group'
    return 'teacher'


def prepare_teacher_query(query):
    if " " not in query:
        query += " "
    return query.lower()


def find_exam_ids(query, exams, mode):
    if mode == 'teacher':
        exam_ids = [exam_id for exam_id, teacher in exams['teachers'].items() if query in teacher.lower()]
    else:
        exam_ids = [exam_id for exam_id, group in exams['group'].items() if query == group.lower()]
    return exam_ids


def create_unique_exams(exam_ids, exams):
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
                'room': exams['room'][exam_id] if exams['room'][exam_id] else "",
                'campus': exams['campus'][exam_id][0] if exams['campus'][exam_id] else "",
                'weekday': exams['weekday'][exam_id],
                'weeks': exams['weeks'][exam_id],
                'time_start': exams['time_start'][exam_id],
                'time_end': exams['time_end'][exam_id],
                'type': exams['type'][exam_id] if exams['type'][exam_id] else ""
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
        context.bot.send_message(chat_id=update.effective_chat.id, text=chunk, reply_markup=ReplyKeyboardRemove())


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
    teachers = ", ".join(decode_teachers([teacher]))
    lesson = exam[1]['exam']
    num = exam[1]['num']
    time_start = datetime.datetime.strptime(time_start, "%H:%M:%S").strftime("%H:%M")
    time_end = datetime.datetime.strptime(time_end, "%H:%M:%S").strftime("%H:%M")

    if weeks.isdigit():

        semester_start = get_semester_start_date_from_period()
        int_weekday = WEEKDAYS.get(weekday.lower())
        start_weekday = semester_start.weekday() + 1
        weekday_difference = int_weekday - start_weekday
        days_to_add = (int(weeks) - 1) * 7

        target_date = semester_start + datetime.timedelta(days=days_to_add + weekday_difference)

        month_name = MONTHS[target_date.month]
        date = target_date.day
    else:
        date = ""
        month_name = ""

    formatted_time = f"{time_start} – {time_end}"
    exam_info += f'📅 Неделя: {weeks}\n'
    exam_info += f"📆 Дата: {date} {month_name}\n"
    exam_info += f"📆 День недели: {weekday}\n"
    exam_info += f'📝 Пара № {num} в ⏰ {formatted_time}\n'
    exam_info += f"🏫 Аудитории: {room} ({campus})\n"
    exam_info += f'📝 {lesson}\n'
    if len(groups) > 0:
        exam_info += f'👥 Группы: {groups}\n'
    if exam[1]['type']:
        exam_info += f'📚 Тип: {exam[1]["type"]}\n'
    if len(teachers) > 0:
        exam_info += f"👨🏻‍🏫 Преподаватели: {teachers}\n\n"
    else:
        exam_info += "\n"

    return exam_info


def main():
    updater = Updater(TELEGRAM_TOKEN, use_context=True)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler('start', start, run_async=True))
    dp.add_handler(CommandHandler('help', start, run_async=True))
    dp.add_handler(CommandHandler('about', start, run_async=True))
    dp.add_handler(MessageHandler(Filters.text, search, run_async=True))

    updater.start_polling()
    updater.idle()


if __name__ == '__main__':
    main()
