import json
import os
import pygsheets


def path_compiler(dir_name_current, dir_name_new, file_name, file_type):
    path = os.path.realpath(__file__)
    dir = os.path.dirname(path)
    dir = dir.replace(dir_name_current, dir_name_new)
    os.chdir(dir)
    if file_type == "json":
        with open(f"{dir}/{file_name}") as f:
            return json.load(f)
    elif file_type == "csv":
        return f"{dir}/{file_name}"


class GoogleSheetsClient:
    def __init__(self, google_api_file, name_of_spreadsheet, status_column):
        self.gc = pygsheets.authorize(service_file=google_api_file)
        self.spreadsheet = self.gc.open(name_of_spreadsheet)
        self.worksheet = self.spreadsheet[0]
        self.jobs_seen = self.worksheet.get_col(4, include_tailing_empty=False)[1:]
        self.status_column = status_column

    def write_row_to_google_sheets(self, row):
        self.worksheet.insert_rows(1, number=1, values=row)

    def write_cell_to_google_sheets(self, value):
        cell = self.worksheet.cell(f"{self.status_column}2")
        cell.value = value

    def check_job_link(self, job_link):
        if job_link in self.jobs_seen:
            return False
        else:
            return True
