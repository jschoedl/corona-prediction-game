import datetime
import logging

import telegram
from matplotlib.dates import date2num

from data import UPDATE_HOUR


def refresh_scores(database, covid_stats, update: telegram.Update = None, force=False):
    logging.info(f"last scores update: {database['scores_update']}")
    if force or database['scores_update'] != (datetime.datetime.now() - datetime.timedelta(hours=UPDATE_HOUR)).date():
        logging.info("updating..")
        if update:
            update.message.reply_text("Looks like the database is outdated. Let me refresh it! Just wait a few moments,"
                                      " please! This can take up to one minute.")
        for user_id, user_data in database['users'].items():
            for country, prediction in user_data['predictions'].items():
                user_data['scores'][country] = get_score(country, covid_stats, get_daily(prediction))
        database['scores_update'] = (datetime.datetime.now() - datetime.timedelta(hours=UPDATE_HOUR)).date()
    return database


def get_daily(prediction: dict) -> dict:
    current_date, *_, end_date = dates = list(prediction.keys())
    index = 0
    daily_predictions = dict()

    # bugfix for older profiles, do not remove
    if dates[0] > dates[1]:
        current_date = dates[1]

    while current_date < end_date:
        if current_date > dates[index + 1]:
            index += 1
        else:
            timespan = dates[index + 1] - dates[index]
            weight1 = current_date - dates[index]
            weight2 = dates[index + 1] - current_date
            cases = (prediction[dates[index]] * weight1 + prediction[dates[index + 1]] * weight2) / timespan

            if cases < 0: cases = 0

            daily_predictions[int(current_date)] = cases
            current_date += 1
    return daily_predictions


def get_score(country, covid_stats, daily_predictions: dict):
    data = covid_stats.get("date", "new_cases_smoothed", location=country)
    score = 0
    for i, (date_pred, cases_pred) in enumerate(daily_predictions.items()):
        if i:
            for date_actual, cases_actual in data:
                if date_pred == date2num(datetime.date.fromisoformat(date_actual)):
                    try:
                        cases_actual = float(cases_actual)
                    except ValueError:
                        logging.error(
                            f"Could not convert string to float: '{cases_actual}'")
                    else:
                        if cases_actual == 0 or cases_pred == 0:
                            score += cases_actual == cases_pred
                        else:
                            score += min(cases_actual / cases_pred,
                                         cases_pred / cases_actual)
                        break
            else:
                break
    return float(score)
