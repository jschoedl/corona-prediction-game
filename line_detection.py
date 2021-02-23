import datetime
import logging

import numpy as np
from PIL import Image
from matplotlib.dates import date2num

import charts
from constants import LINE_THRESHOLD


def evaluate(prediction_path, country, drawing_area, covid_stats):
    pred_image = Image.open(prediction_path)
    country_image = Image.open(f"{charts.IMAGES_PATH}/{country}.jpg")
    if not pred_image.size == country_image.size:
        logging.error("The size of the submitted image is not equal to the original size.")
        return "The size of the submitted image is not equal to the original size. Please try again."

    size = pred_image.size[1], pred_image.size[0]
    pred_data = np.sum(np.array(pred_image.getdata()), axis=1).reshape(size)
    country_data = np.sum(np.array(country_image.getdata()), axis=1).reshape(size)

    x0, y0, x1, y1, x_factor, y_factor = drawing_area
    diff = np.abs(pred_data - country_data).T[int(x0):int(x1), int(y0):int(y1)]
    x_offset = x0 % 1
    y_offset = y0 % 1

    line_pixels = []
    for row in diff:
        if np.max(row) < 150:
            line_pixels.append(np.array([]))
        else:
            line_pixels.append(np.argwhere(row >= np.max(row) * LINE_THRESHOLD))

    for i in line_pixels:
        if len(i):
            break
    else:
        logging.error("No line was found.")
        return "No line was found. Please try again."

    thicknesses = []
    for column in line_pixels:
        if len(column) > 1:
            thicknesses.append(max(column) - min(column))
    line_thickness = np.median(thicknesses)

    line = []
    for row in line_pixels:
        if not len(row):
            line.append(float("nan"))
        else:
            line.append(np.min(row) + line_thickness / 2)

    data = covid_stats.get("date", "new_cases_smoothed", location=country)

    for i in range(1, 4):
        try:
            last_date, last_value = date2num(data[-i][0]), float(data[-i][1])
            break
        except ValueError:
            logging.error(f"No data for {country} available (attempt {i}).")
    else:
        raise ValueError(f"There is no readable data for {country}.")

    raw_predictions = dict()
    raw_predictions[date2num(datetime.date.today())] = last_value
    last = None
    for i, point in enumerate(line):
        if not np.isnan(point):
            cases = (y1 - y0 - y_offset - point) * y_factor
            if cases < 0: cases = 0
            last = raw_predictions[date2num(datetime.date.today()) +
                                   (x_offset + i) * x_factor] = cases
    if not line or last is None:
        return "No line was found. Please try again."

    raw_predictions[date2num(datetime.date.today() + datetime.timedelta(days=charts.N_PREDICTED_DAYS))] = last
    return raw_predictions
