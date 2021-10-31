import datetime
import logging
import numpy as np
from PIL import Image
from matplotlib.dates import date2num

import charts
import constants
from constants import LINE_THRESHOLD
from data import CPGameData


def evaluate(prediction_path: str, country: str, drawing_area: tuple, covid_stats: CPGameData) -> dict:
    """
    Detect a line and convert it into numerical values.
    :param prediction_path: path containing an image with the drawn line
    :param country: predicted country
    :param drawing_area: postition and scaling of the relevant area in the prediction image in the format (x0, y0, x1, y1, x_factor, y_factor)
    :param covid_stats: Covid-19-statistics
    :return: dictionary in the format date: prediction
    """
    pred_image = Image.open(prediction_path)
    country_image = Image.open(f"{constants.IMAGES_PATH}/{country}.jpg")
    if not pred_image.size == country_image.size:
        logging.error("The size of the submitted image is not equal to the original size.")
        return "The size of the submitted image is not equal to the original size. Please try again."

    size = pred_image.size[1], pred_image.size[0]
    pred_data = np.sum(np.array(pred_image.getdata()), axis=1).reshape(size)
    country_data = np.sum(np.array(country_image.getdata()), axis=1).reshape(size)

    # calculate the difference between original chart and prediction
    x0, y0, x1, y1, x_factor, y_factor = drawing_area
    diff = np.abs(pred_data - country_data).T[int(x0):int(x1), int(y0):int(y1)]
    x_offset = x0 % 1
    y_offset = y0 % 1

    line_pixels = []
    for column in diff:
        if np.max(column) < 150:
            # ignore noise
            line_pixels.append(np.array([]))
        else:
            # store all pixels with a significant difference
            line_pixels.append(np.argwhere(column >= np.max(column) * LINE_THRESHOLD))

    for i in line_pixels:
        if len(i):
            break
    else:
        logging.error("No line was found.")
        return "No line was found. Please try again."

    # estimate the line thickness
    thicknesses = []
    for column in line_pixels:
        if len(column) > 1:
            thicknesses.append(max(column) - min(column))
    line_thickness = np.quantile(thicknesses, 0.2)

    line = []
    for column in line_pixels:
        if not len(column):
            line.append(float("nan"))
        else:
            # In case the user is drawing two lines above each other, taking the mean of the y values is not sufficient.
            # Therefore, take the lowest value of the column and add half of the typical thickness.
            line.append(np.min(column) + line_thickness / 2)

    data = covid_stats.get("date", "new_cases_smoothed", location=country)

    # find the latest readable case statistics
    for i in range(1, 4):
        try:
            last_date, last_value = date2num(datetime.date.fromisoformat(data[-i][0])), float(data[-i][1])
            break
        except ValueError:
            logging.error(f"No data for {country} available (attempt {i}).")
    else:
        raise ValueError(f"There is no readable data for {country}.")

    # map predicted values with their date and scale them according to the chart
    predictions = dict()
    predictions[date2num(datetime.date.today())] = last_value
    last = None
    for i, point in enumerate(line):
        if not np.isnan(point):
            cases = (y1 - y0 - y_offset - point) * y_factor
            if cases < 0: cases = 0
            last = predictions[date2num(datetime.date.today()) +
                                   (x_offset + i) * x_factor] = cases
    if not line or last is None:
        return "No line was found. Please try again."

    # map the last prediction with the last date in case the line did not fill the whole chart horizontally
    predictions[date2num(datetime.date.today() + datetime.timedelta(days=charts.N_PREDICTED_DAYS))] = last
    return predictions
