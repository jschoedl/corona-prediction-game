import datetime
import math
import os

import numpy as np
from dateutil.relativedelta import relativedelta
from matplotlib import pyplot as plt
from matplotlib.dates import date2num
from matplotlib.ticker import FixedLocator

import scores
from constants import N_PREDICTED_DAYS


def get_locations(starting_date: datetime.date, ending_date: datetime.date, max_n=5, min_n=3):
    delta = ending_date - starting_date
    rel_delta = relativedelta(ending_date, starting_date)
    if rel_delta.years > min_n:
        space = relativedelta(years=math.ceil(rel_delta.years / max_n))
    elif rel_delta.months + rel_delta.years * 12 > min_n:
        space = relativedelta(months=math.ceil((rel_delta.months + rel_delta.years * 12) / max_n))
    else:
        space = relativedelta(days=math.ceil(delta.days / max_n))

    out = []
    recent_date = ending_date
    while recent_date > starting_date:
        out.insert(0, recent_date)
        recent_date -= space

    for i, date in enumerate(out):
        out[i] = date2num(date)

    return out


def visualize(countries: list,
              covid_stats,
              img_path: str,
              predictions: list = None,
              titles=None,
              offsets=None,
              mode=None,
              chart_scale=None,
              end_date=None,
              ):
    res = None

    if titles is None:
        if mode in ("input", "confirmation"):
            titles = [f"New Infections {'for the whole' if country == 'World' else 'in'} {country} per Day " \
                      f"(smoothed)" for country in countries]
        else:
            titles = countries

    if offsets is None:
        # days before prediction starts and days after statistics end
        if mode in ("input", "confirmation"):
            offsets = [[365, N_PREDICTED_DAYS]] * len(countries)
        else:
            offsets = [[10, 10]] * len(countries)

    if predictions is None:
        predictions = [None]*len(countries)

    if end_date is None:
        end_date = datetime.date(year=3000, day=1, month=1)

    xs, y_actuals, y_preds, last_actuals = [], [], [], []
    for country, prediction, (beginning_offset, ending_offset) in zip(countries, predictions, offsets):
        data = covid_stats.get("date", "new_cases_smoothed", location=country)
        if prediction is None:
            chart_beginning: np.ndarray = date2num(datetime.datetime.today()) - beginning_offset
            prediction = tuple()
        else:
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
            if dt_date <= end_date:
                numpy_date = date2num(dt_date)
                x.append(dt_date)
                y_actual.append(float("nan"))
                y_pred.append(prediction[numpy_date] if numpy_date in prediction else float("nan"))
        xs.append(x)
        y_actuals.append(y_actual)
        y_preds.append(y_pred)
        last_actuals.append(datetime.date.fromisoformat(str_date))

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

    for ax, x, y_actual, y_pred, title, last_actual in zip(axs, xs, y_actuals, y_preds, titles, last_actuals):
        ax.plot(x, y_actual, label="reported")
        ax.plot(x, y_pred, label="predicted")
        if mode in ("input", "confirmation"):
            plt.xlim(right=x[-1])
            plt.ylim(bottom=0, top=(np.nanmax((np.nanmax(y_actual), np.nanmax(y_pred)))) * chart_scale)
        else:
            ax.legend()
        ax.grid(True)
        ax.set_title(title)
        ax.xaxis.set_major_locator(FixedLocator(get_locations(x[0], x[-1])))

        if mode == "input":
            # drawing area
            assert len(axs) == 1, f"Cannot only generate input for one chart (got {len(axs)})"
            x0, y0 = ax.transData.transform((date2num(last_actual), plt.ylim()[0]))
            x1, y1 = ax.transData.transform((plt.xlim()[1], plt.ylim()[1]))

            x_factor = (plt.xlim()[1] - date2num(last_actual)) / (x1 - x0)
            y_factor = (plt.ylim()[1] - plt.ylim()[0]) / (y1 - y0)
            res = x0, y0, x1, y1, x_factor, y_factor

    os.makedirs(os.path.dirname(img_path), exist_ok=True)
    plt.savefig(img_path)
    plt.close()

    return res
