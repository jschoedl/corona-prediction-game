import datetime
import os
from glob import glob

import matplotlib.pyplot as plt
from matplotlib.dates import date2num

from data import UPDATE_HOUR


# TODO: unify with charts.py


def load(country, covid_stats, force=False):
    """
    Make sure that an image for the selected country is present.
    """
    os.makedirs(IMAGES_PATH, exist_ok=True)
    update_path = f"{IMAGES_PATH}/last_update.txt"
    if os.path.exists(update_path):
        with open(update_path) as f:
            content = f.read()
        if content == str((datetime.datetime.today()-datetime.timedelta(hours=UPDATE_HOUR)).date()):
            if not force and os.path.exists(f"{IMAGES_PATH}/{country}.jpg"):
                return
        else:
            for img_path in glob(f"{IMAGES_PATH}/*.jpg"):
                os.remove(img_path)
    else:
        for img_path in glob(f"{IMAGES_PATH}/*.jpg"):
            os.remove(img_path)

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
        f.write(str((datetime.datetime.today()-datetime.timedelta(hours=UPDATE_HOUR)).date()))

    # drawing area
    x0, y0 = ax.transData.transform((date2num(x_data[-1]), plt.ylim()[0]))
    x1, y1 = ax.transData.transform((plt.xlim()[1], plt.ylim()[1]))

    x_factor = (plt.xlim()[1] - date2num(x_data[-1])) / (x1 - x0)
    y_factor = (plt.ylim()[1] - plt.ylim()[0]) / (y1 - y0)
    return x0, y0, x1, y1, x_factor, y_factor


IMAGES_PATH = ".covid_images"
N_PREDICTED_DAYS = 150
