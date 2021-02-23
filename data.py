import datetime
import glob
import os
import warnings

import requests

from constants import CSV_SOURCE, TEMP_DIR


class CPGameData(dict):
    def __init__(self, source: dict):
        self.last_update = None
        self.titles = []
        self.values = ()

        self.update_stats()
        super().__init__(source)

    def update_stats(self):
        """
        Load or update the statistics for Covid-19.

        If no data has been downloaded for the current day, all csv files in TEMP_DIR are deleted and a new record is
        downloaded. In any case the values are read from the csv file for the current day.
        """
        path = f"{TEMP_DIR}/{datetime.datetime.now().date()}.csv"
        if not os.path.exists(path):
            os.makedirs(TEMP_DIR, exist_ok=True)
            for file in glob.glob(f"{TEMP_DIR}/*.csv"):
                os.remove(file)
            data = requests.get(CSV_SOURCE)
            with open(path, "w") as f:
                f.write(data.text)
        self.last_update = datetime.datetime.now().date()

        with open(path) as f:
            lines = f.readlines()
        self.titles = lines[0][:-1].split(",")
        self.values = tuple(line[:-1].split(",")[:7] for line in lines[1:])  # discard right part of the table

    def get(self, *titles, **filters) -> list:
        """
        Return certain information from the dataset.

        Column titles and explanations:
        https://github.com/owid/covid-19-data/blob/master/public/data/owid-covid-codebook.csv

        :param titles: titles of the columns to return
        :param filters: values in certain columns to search for
        :return: list with rows, whereas each row is a list of values in order of the given column titles
        """

        for filter_title in filters.keys():
            if filter_title not in self.titles:
                warnings.warn(f"'{filter_title}' is not a valid filter and will be ignored.", stacklevel=2)

        res = []
        res_indices = [self.titles.index(arg) for arg in titles]

        def filter_row(values):
            return [values[i] for i in res_indices]

        for row in self.values:
            for title, value in zip(self.titles, row):
                if title in filters.keys() and value != str(filters[title]):
                    break
            else:
                res.append(filter_row(row))

        return res
