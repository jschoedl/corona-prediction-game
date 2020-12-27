import datetime

import matplotlib.pyplot as plt
from matplotlib.dates import date2num

import images
import scores


# TODO: unify visualisation functions


def visualize_all(predictions: dict, img_path, covid_stats):
    xs, y_actuals, y_preds = [], [], []
    for country, prediction in predictions.items():
        data = covid_stats.get("date", "new_cases_smoothed", location=country)
        prediction = scores.get_daily(prediction)
        x, y_actual, y_pred = [], [], []
        for date, n in data:
            date: str
            try:
                if (as_num := date2num(datetime.date.fromisoformat(date))) in prediction:
                    new_cases = float(n)
                    x.append(datetime.date.fromisoformat(date))
                    y_actual.append(new_cases)
                    y_pred.append(prediction[as_num])
            except ValueError:
                pass
        xs.append(x)
        y_actuals.append(y_actual)
        y_preds.append(y_pred)

    size = int(len(predictions) ** 0.5 + 0.99999999)
    fig, axs = plt.subplots(nrows=size, ncols=size, figsize=(8 * size, 4 * size))
    if size == 1:
        axs = [axs]
    else:
        axs = axs.reshape(-1)
    for country, ax, x, y_actual, y_pred in zip(predictions.keys(), axs, xs, y_actuals, y_preds):
        ax.plot(x, y_actual)
        ax.plot(x, y_pred)
        ax.grid(True)
        ax.set_title(f"Reported Infections (blue) vs. Your Prediction (orange) in {country}")

    plt.savefig(img_path)


def visualize_afterwards(country, predictions, img_path, covid_stats):
    data = covid_stats.get("date", "new_cases_smoothed", location=country)
    predictions = scores.get_daily(predictions)
    x_a, y_actual_a = [], []
    x_b, y_actual_b, y_pred_b = [], [], []
    for date, n in data:
        date: str
        try:
            new_cases = float(n)
            if new_cases > 0:
                x_a.append(datetime.date.fromisoformat(date))
                y_actual_a.append(new_cases)
            if (as_num := date2num(datetime.date.fromisoformat(date))) in predictions:
                x_b.append(datetime.date.fromisoformat(date))
                y_actual_b.append(new_cases)
                y_pred_b.append(predictions[as_num])
        except ValueError:
            pass

    fig, (ax_a, ax_b) = plt.subplots(2, figsize=(8, 8))

    ax_a.plot(x_a, y_actual_a)
    ax_a.plot(predictions.keys(), predictions.values())
    ax_a.grid(True)
    ax_a.set_title(
        f"New Infections {'for the whole' if country == 'World' else 'in'} {country} per Day (smoothed)")

    ax_b.plot(x_b, y_actual_b)
    ax_b.plot(x_b, y_pred_b)
    ax_b.grid(True)
    ax_b.set_title("Reported Infections (blue) vs. Your Prediction (orange)")

    plt.savefig(img_path)


def visualize(country, predictions, img_path, covid_stats):
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
    plt.xlim(right=datetime.date.today() + datetime.timedelta(days=images.N_PREDICTED_DAYS))
    plt.ylim(top=max(y_data) * 3)

    plt.title(f"New Infections {'for the whole' if country == 'World' else 'in'} {country} per Day (smoothed)")
    ax.grid(True)
    plt.savefig(img_path)
