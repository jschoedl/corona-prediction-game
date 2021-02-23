import datetime
import math
import os

import numpy as np
from dateutil.relativedelta import relativedelta
from matplotlib import pyplot as plt
from matplotlib.dates import date2num
from matplotlib.ticker import MaxNLocator, FixedLocator

import scores
from constants import IMAGES_PATH, N_PREDICTED_DAYS


def get_locations(starting_date: datetime.date, ending_date: datetime.date, max_n=5):
    delta = ending_date - starting_date
    rel_delta = relativedelta(ending_date, starting_date)
    if rel_delta.years > max_n:
        space = relativedelta(years=rel_delta.years // max_n)
    elif rel_delta.months + rel_delta.years * 12 > max_n:
        space = relativedelta(months=(rel_delta.months + rel_delta.years * 12) // max_n)
    elif delta.days // 7 > max_n:
        space = relativedelta(weeks=delta.days // 7 // max_n)
    elif delta.days > max_n:
        space = relativedelta(days=delta.days // max_n)
    else:
        space = relativedelta(days=1)

    out = []
    recent_date = ending_date
    while recent_date > starting_date:
        out.insert(0, recent_date)
        recent_date -= space

    for i, date in enumerate(out):
        out[i] = date2num(date)

    return out


def visualize(countries: list, predictions: list, img_path, covid_stats, titles=None, offsets=None):
    assert len(countries) == len(predictions), "The number of countries has to be equal to the number of predictions."
    if not titles:
        titles = countries
    if not offsets:
        offsets = [[10, 10]] * len(predictions)
        # days before prediction starts and days after statistics end

    xs, y_actuals, y_preds = [], [], []
    for country, prediction, (beginning_offset, ending_offset) in zip(countries, predictions, offsets):
        data = covid_stats.get("date", "new_cases_smoothed", location=country)
        prediction = scores.get_daily(prediction)

        chart_beginning: np.ndarray = list(prediction.keys())[0] - beginning_offset
        x, y_actual, y_pred = [], [], []

        for str_date, n in data:
            try:
                new_cases = float(n)
                numpy_date = date2num(datetime.date.fromisoformat(str_date))
                if numpy_date > chart_beginning:
                    x.append(datetime.date.fromisoformat(str_date))
                    y_actual.append(new_cases)
                    y_pred.append(prediction[numpy_date] if numpy_date in prediction else float("nan"))
            except ValueError:
                pass
        for dt_date in (datetime.date.fromisoformat(str_date) + datetime.timedelta(days=i) for i in
                        range(ending_offset)):
            numpy_date = date2num(dt_date)
            if numpy_date in prediction:
                x.append(dt_date)
                y_actual.append(float("nan"))
                y_pred.append(prediction[numpy_date])
        xs.append(x)
        y_actuals.append(y_actual)
        y_preds.append(y_pred)

    if len(predictions) < 4:
        cols, rows = 1, len(predictions)
    else:
        cols = math.ceil(len(predictions) ** 0.5)
        rows = math.ceil(len(predictions) / cols)
    fig, axs = plt.subplots(ncols=cols, nrows=rows, figsize=(8 * cols, 4 * rows))

    if len(predictions) == 1:
        axs = [axs]
    else:
        axs = axs.reshape(-1)

    for ax, x, y_actual, y_pred, title in zip(axs, xs, y_actuals, y_preds, titles):
        ax.plot(x, y_actual, label="reported")
        ax.plot(x, y_pred, label="predicted")
        ax.grid(True)
        ax.legend()
        ax.set_title(title)
        ax.xaxis.set_major_locator(MaxNLocator(7))

    plt.savefig(img_path)
    plt.close()


def visualize_for_confirmation(country, predictions, img_path, covid_stats, chart_scale):
    data = covid_stats.get("date", "new_cases_smoothed", location=country)
    x_data = []
    y_data = []
    for date, new_cases in data:
        try:
            n = float(new_cases)
            if n > 0:
                x_data.append(datetime.date.fromisoformat(date))
                y_data.append(n)
        except ValueError:
            pass

    fig, ax = plt.subplots(figsize=(8, 4))
    ax.plot(x_data, y_data)
    ax.plot(predictions.keys(), predictions.values())
    plt.xlim(right=datetime.date.today() + datetime.timedelta(days=N_PREDICTED_DAYS))
    plt.ylim(bottom=0, top=max(y_data) * chart_scale)
    ax.xaxis.set_major_locator(MaxNLocator(7))

    plt.title(f"New Infections {'for the whole' if country == 'World' else 'in'} {country} per Day (smoothed)")
    ax.grid(True)
    plt.savefig(img_path)
    plt.close()


def visualize_for_input(country,
                        covid_stats,
                        end_date=None,
                        chart_scale=3,
                        starting_date=None):
    if end_date is None:
        end_date = datetime.date.today() + datetime.timedelta(days=N_PREDICTED_DAYS)
    if starting_date is None:
        starting_date = datetime.date.today() - datetime.timedelta(days=365)
    os.makedirs(IMAGES_PATH, exist_ok=True)

    # generate new visualisation
    data = covid_stats.get("date", "new_cases_smoothed", location=country)
    x_data = []
    y_data = []
    for date, new_cases in data:
        try:
            date = datetime.date.fromisoformat(date)
            n = float(new_cases)
            if date > starting_date:
                x_data.append(date)
                y_data.append(n)
        except ValueError:
            pass

    fig, ax = plt.subplots(figsize=(8, 4))
    ax.plot(x_data, y_data)
    plt.xlim(right=end_date)
    plt.ylim(bottom=0, top=max(y_data) * chart_scale)
    ax.xaxis.set_major_locator(
        FixedLocator(get_locations(x_data[0], end_date)))

    plt.title(f"New Infections {'for the whole' if country == 'World' else 'in'} {country} per Day (smoothed)")
    ax.grid(True)
    plt.savefig(f"{IMAGES_PATH}/{country}.jpg")

    # drawing area
    x0, y0 = ax.transData.transform((date2num(x_data[-1]), plt.ylim()[0]))
    x1, y1 = ax.transData.transform((plt.xlim()[1], plt.ylim()[1]))

    x_factor = (plt.xlim()[1] - date2num(x_data[-1])) / (x1 - x0)
    y_factor = (plt.ylim()[1] - plt.ylim()[0]) / (y1 - y0)
    plt.close()
    return x0, y0, x1, y1, x_factor, y_factor
