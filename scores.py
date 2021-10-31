import datetime
import logging

from matplotlib.dates import date2num


def get_daily(prediction: dict) -> dict:
    """Convert a raw prediction into a series of numbers, one for each predicted day."""
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
            weight1 = dates[index + 1] - current_date
            weight2 = current_date - dates[index]
            cases = (prediction[dates[index]] * weight1 + prediction[dates[index + 1]] * weight2) / timespan

            if cases < 0: cases = 0

            daily_predictions[int(current_date)] = cases
            current_date += 1
    return daily_predictions


def get_score(country, covid_stats, daily_predictions: dict) -> (float, float, float):
    """Get the total and daily score of a user."""
    data = covid_stats.get("date", "new_cases_smoothed", location=country)
    score = days = last_score = 0
    for i, (date_pred, cases_pred) in enumerate(daily_predictions.items()):
        for date_actual, cases_actual in data:
            if date_pred == date2num(datetime.date.fromisoformat(date_actual)):
                try:
                    cases_actual = float(cases_actual)
                except ValueError:
                    logging.error(
                        f"No valid data for {country} available.")
                else:
                    if cases_actual == 0 or cases_pred == 0:
                        last_score = cases_actual == cases_pred
                    else:
                        last_score = min(cases_actual / cases_pred,cases_pred / cases_actual)
                    score += last_score
                    days += 1
                    break
        else:
            break
    return float(score), float(score)/(days if score else 1), float(last_score), days
