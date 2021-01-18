import datetime
import logging

from matplotlib.dates import date2num


def get_daily(prediction: dict) -> dict:
    current_date, *_, end_date = dates = list(prediction.keys())
    index = 0
    daily_predictions = dict()

    # bugfix for older profiles
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
                            f"No valid data for {country} available.")
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

