import datetime
import math
import os
from glob import glob

import numpy as np
from matplotlib import pyplot as plt
from matplotlib.dates import date2num

import scores


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

    plt.savefig(img_path)


def visualize_for_confirmation(country, predictions, img_path, covid_stats):
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
    plt.ylim(top=max(y_data) * 3)

    plt.title(f"New Infections {'for the whole' if country == 'World' else 'in'} {country} per Day (smoothed)")
    ax.grid(True)
    plt.savefig(img_path)


def visualize_for_input(country, covid_stats, force=False):
    os.makedirs(IMAGES_PATH, exist_ok=True)
    update_path = f"{IMAGES_PATH}/last_update.txt"

    # return if cached
    if os.path.exists(update_path):
        with open(update_path) as f:
            content = f.read()
        if content == str(datetime.datetime.today().date()):
            if not force and os.path.exists(f"{IMAGES_PATH}/{country}.jpg"):
                return
        else:
            for img_path in glob(f"{IMAGES_PATH}/*.jpg"):
                os.remove(img_path)
    else:
        for img_path in glob(f"{IMAGES_PATH}/*.jpg"):
            os.remove(img_path)

    # generate new visualisation
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
    plt.xlim(right=datetime.date.today() + datetime.timedelta(days=N_PREDICTED_DAYS))
    plt.ylim(top=max(y_data) * 3)

    plt.title(f"New Infections {'for the whole' if country == 'World' else 'in'} {country} per Day (smoothed)")
    ax.grid(True)
    plt.savefig(f"{IMAGES_PATH}/{country}.jpg")
    with open(f"{IMAGES_PATH}/last_update.txt", "w") as f:
        f.write(str(datetime.datetime.today().date()))

    # drawing area
    x0, y0 = ax.transData.transform((date2num(x_data[-1]), plt.ylim()[0]))
    x1, y1 = ax.transData.transform((plt.xlim()[1], plt.ylim()[1]))

    x_factor = (plt.xlim()[1] - date2num(x_data[-1])) / (x1 - x0)
    y_factor = (plt.ylim()[1] - plt.ylim()[0]) / (y1 - y0)
    return x0, y0, x1, y1, x_factor, y_factor


IMAGES_PATH = ".covid_images"
N_PREDICTED_DAYS = 150
