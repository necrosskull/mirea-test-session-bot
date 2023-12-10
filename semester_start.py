import datetime


class Period:
    def __init__(self, year_start, year_end, semester):
        self.year_start = year_start
        self.year_end = year_end
        self.semester = semester


def get_semester_start_date(year_start, year_end, semester):
    if semester == 1:
        start_date = datetime.date(year_start, 9, 1)
        if start_date.weekday() == 6:
            start_date += datetime.timedelta(days=1)
        return start_date

    start_date = datetime.date(year_end, 2, 1)
    start_date += datetime.timedelta(days=8)

    if start_date.weekday() == 6:
        start_date += datetime.timedelta(days=1)

    return start_date


def get_period(date: datetime.date) -> Period:
    if date.month >= 7:
        return Period(date.year, date.year + 1, 1)
    else:
        return Period(date.year - 1, date.year, 2)


def get_semester_start_date_from_period():
    current_date = datetime.date.today()
    period = get_period(current_date)
    semester_start_date = get_semester_start_date(period.year_start, period.year_end, period.semester)
    return semester_start_date
