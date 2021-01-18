import datetime
import glob
import os
import warnings

import requests

TEMP_DIR = ".covid_data"

# This dataset is kept up to date by Our World in Data. More about their sources can be found here:
# https://github.com/owid/covid-19-data/tree/master/public/data#our-data-sources
# Please check out the information regarding the license as well.
CSV_SOURCE = "https://covid.ourworldindata.org/data/owid-covid-data.csv"


class Data:
    def __init__(self):
        self.last_update = None
        self.titles = []
        self.values = ()

        self.update()

    def check_refresh(self) -> bool:
        """
        Check whether the currently used data is outdated.
        """
        return datetime.datetime.now().date() != self.last_update

    def refresh(self) -> bool:
        """
        Run self.update if the currently used data is outdated.
        :return: True if self.update was executed, otherwise False.
        """
        if self.check_refresh():
            self.update()
            return True
        return False

    def update(self):
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
        self.values = tuple(line[:-1].split(",") for line in lines[1:])

    def get(self, *titles, refresh_database=True, **filters) -> list:
        """
        Return certain information from the dataset.

        Column titles and explanations:
        https://github.com/owid/covid-19-data/blob/master/public/data/owid-covid-codebook.csv

        :param titles: titles of the columns to return
        :param filters: values in certain columns to search for
        :param refresh_database: run self.refresh to make sure the database is up to date
        :return: list with rows, whereas each row is a list of values in order of the given column titles
        """
        if refresh_database:
            self.refresh()

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

