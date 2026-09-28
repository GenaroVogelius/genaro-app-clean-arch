from datetime import date


def format_date_iso(day: date, sep="-"):
    """
    Formats the date in the ISO format (YYYY-MM-DD)
    """
    return day.strftime(f"%Y{sep}%m{sep}%d")
