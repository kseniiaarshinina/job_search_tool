import time
import re
import json
import os
import sys
import numpy as np
import tkinter as tk
import pandas as pd
import pyperclip
import logging
from datetime import datetime

from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException, NoSuchElementException
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

from work_with_jobs import check_job_fits
from utils import GoogleSheetsClient


log = logging.getLogger(__name__)
ch = logging.StreamHandler(sys.stdout)
ch.setLevel(10)
formatter = logging.Formatter("%(asctime)s %(levelname)s - %(message)s")
ch.setFormatter(formatter)
log.addHandler(ch)
log.setLevel(10)


class EasyApplyLinkedin:
    def __init__(self, data):
        """Parameter initialization"""

        self.email = data["email"]
        self.password = data["password"]
        self.keywords = data["keywords"]
        self.location = data["location"]
        self.open_ai_api_key = data["open_ai_api_key"]
        self.work_modes = self.work_mode_conversion(data)
        self.work_fields = data["work fields"]
        self.experience_years = data["years of experience"]
        self.degree = data["degree"]
        self.google_sheets_client = GoogleSheetsClient(
            data["google_api_file"],
            data["name_of_spreadsheet"],
            data["sh status column"],
        )
        options = webdriver.ChromeOptions()
        options.add_argument("start-maximized")
        options.add_argument("disable-infobars")
        options.add_argument("--disable-extensions")
        self.driver = webdriver.Chrome(
            chrome_options=options, service=Service(ChromeDriverManager().install())
        )

    def login_linkedin(self):
        """Log into your personal LinkedIn profile"""

        # go to the LinkedIn login url
        self.driver.get("https://www.linkedin.com/login")

        # introduce email and password and hit enter
        login_email = self.driver.find_element("name", "session_key")
        login_email.clear()
        login_email.send_keys(self.email)
        login_pass = self.driver.find_element("name", "session_password")
        login_pass.clear()
        login_pass.send_keys(self.password)
        login_pass.send_keys(Keys.RETURN)

    def work_mode_conversion(self, data):
        """Convert work mode in LinkedIn to respective numbers"""
        work_mode_to_convert = data["work mode"]
        work_mode_dict = {"On-site": 1, "Remote": 2, "Hybrid": 3}
        work_mode_list = [work_mode_dict[i] for i in work_mode_to_convert]
        return work_mode_list

    def job_search_and_filter(self):
        """Locate job search and provide keywords, locations, modes, etc. there"""

        # find search field and send job names to the search field
        time.sleep(10)
        search_field = self.driver.find_element(
            "css selector", "#global-nav-typeahead > input"
        )
        search_field.click()
        search_field.clear()
        search_field.send_keys(self.keywords)
        search_field.send_keys(Keys.RETURN)
        time.sleep(5)

        # click "Jobs" button to choose to search from jobs
        search_jobs = self.driver.find_element("xpath", "//button[text()='Jobs']")
        search_jobs.click()
        time.sleep(2)

        # search location
        search_location = self.driver.find_element(
            "xpath", "//input[@aria-label='City, state, or zip code']"
        )
        search_location.click()
        search_location.clear()
        search_location.send_keys(self.location)
        search_location.send_keys(Keys.RETURN)
        time.sleep(5)

        # choose work mode
        work_mode_drop_down = self.driver.find_element(
            "xpath", "//button[contains(@aria-label, 'On-site/remote filter.')]"
        )
        work_mode_drop_down.click()
        for work_mode in self.work_modes:
            self.driver.find_element(
                "css selector", f"label[for='workplaceType-{work_mode}']"
            ).click()
        time.sleep(3)

        # show results
        WebDriverWait(self.driver, 20).until(
            EC.element_to_be_clickable(
                (
                    By.XPATH,
                    "/html/body/div[5]/div[3]/div[4]/section/div/section/div/div/div/ul/li[7]/div/div/div/div[1]/div/form/fieldset/div[2]/button[2]",
                )
            )
        ).click()

    def find_all_offers(self):
        """This function finds all the offers on pages according to the search query and peocesses them"""

        # find the total amount of results
        total_results = self.driver.find_element(
            "class name", "display-flex.t-12.t-black--light.t-normal"
        )
        total_results_int = int(total_results.text.split(" ", 1)[0].replace(",", ""))
        log.debug(total_results_int)
        time.sleep(2)

        current_page = 1
        find_pages = self.driver.find_elements(
            "class name",
            "artdeco-pagination__indicator.artdeco-pagination__indicator--number",
        )
        total_pages = find_pages[len(find_pages) - 1].text
        last_page = int(re.sub(r"[^\d.]", "", total_pages))
        # go through each page
        while current_page <= last_page:
            results = self.driver.find_elements(
                "xpath", "//a[contains(@class,'job-card-list__title')]"
            )
            # process each job on the page
            for result in results:
                log.debug(f"This is the job in progress:\n{result.text}")
                hover = ActionChains(self.driver).move_to_element(result)
                hover.click().perform()
                time.sleep(5)
                job_description_body = result.find_element(
                    "xpath", "//div[contains(@class,'scaffold-layout__detail')]"
                )
                # call the method to write down job info and get job description text
                job_description_text = self.get_job_description_info(
                    job_description_body
                )
                # if the function didn't return, then the job has already been processed, skip to next
                if not job_description_text:
                    continue
                job_check = check_job_fits(
                    self.open_ai_api_key,
                    job_description_text,
                    self.work_fields,
                    self.experience_years,
                    self.degree,
                )
                # if the job doesn't meet the requirements set in the function, send the corresponfing status to Google sheets and skip to next
                if not job_check:
                    self.google_sheets_client.write_cell_to_google_sheets(
                        "Not a good fit"
                    )
                    log.debug("Not a good fit")
                    continue
                # if the job is unique and is ok, try to apply
                self.submit_apply(job_description_body, job_check)
            if current_page < last_page:
                next_page = self.driver.find_element(
                    "xpath",
                    "//button[@aria-label='Page " + str(current_page + 1) + "']",
                )
                next_page.click()
                current_page += 1
            else:
                self.close_session()

    def submit_apply(self, job_description, job_name):
        """
        This function:
        - submits the application for the 'Easy Apply' job found or
        - sends application status to Google Sheets if there's 'Apply' option or any error
        """

        # find apply button, skip if already applied to the position
        try:
            apply = job_description.find_element(
                "xpath", "//button[contains(@aria-label, 'Apply to')]"
            )
            time.sleep(1)

            # if 'Easy Apply' in apply button, try to apply for the job
            if apply.text == "Easy Apply":
                apply.click()
                # remember the popup element to later make sure 'Next' button worked right
                popup = self.driver.find_element(
                    "class name", "jobs-easy-apply-content"
                )
                aria_label = popup.get_attribute("aria-label")
                # a loop to go through each popup, unless the popup has questions which need personal attention
                while True:
                    # handling popups with 'Next' button in the popup
                    try:
                        # find 'Next' button
                        next_button = self.driver.find_element(
                            "xpath", "//button[@aria-label='Continue to next step']"
                        )
                        log.debug("'Next' button was fetched")
                        # find setions in the popup (e.g. 'Education', 'Resume') to handle certain sections properly
                        section_names = self.driver.find_elements(
                            "xpath", "//h3[contains(@class, 't-bold')]"
                        )
                        section_name_texts = [
                            section_name.text for section_name in section_names
                        ]
                        log.debug("Names of popup sections were fetched")
                        log.debug(f"Here are the section names: {section_name_texts}")

                        # for future use:
                        # if both 'Resume' and 'Cover letter' are in the popup, send 2 files
                        # if "Resume" and "Cover letter" in section_name_texts:
                        # log.debug("'Resume' and 'Cover letter' headings were found in section names")
                        # time.sleep(3)
                        # upload_resume_button = self.driver.find_element("xpath", "//button[contains(@aria-label, 'Upload resume')]")
                        # log.debug("'Upload resume' button was fetched")
                        # upload_resume_button.send_keys(path)
                        # log.debug("Resume has been sent to 'Upload resume' button")
                        # time.sleep(3)
                        # upload_cover_letter_button = self.driver.find_element("xpath", "//span[.='Upload cover letter']")
                        # log.debug("'Upload cover letter' button was fetched")
                        # upload_cover_letter_button.send_keys("path")
                        # log.debug("Cover letter has been sent to 'Upload cover letter' button")

                        # if 'Resume' is in the popup, select resume
                        if "Resume" in section_name_texts:
                            if job_name == "ML":
                                resume = self.driver.find_element(
                                    "xpath",
                                    "//h3[contains(., 'Kseniia_Arshinina_DS_MLE.pdf')]/ancestor::div",
                                )
                            else:
                                resume = self.driver.find_element(
                                    "xpath",
                                    "//h3[contains(., 'Kseniia_Arshinina_DE_DA.pdf')]/ancestor::div",
                                )
                            resume.find_element(
                                "xpath",
                                "//label[contains(@id, 'jobsDocumentCardToggleLabel')]",
                            ).click
                            log.debug("Resume has been picked")
                            # for future use:
                            # upload_resume_button = self.driver.find_element("xpath", "//input[@name='file']")
                            # log.debug("Single 'Upload resume' button was fetched")
                            # upload_resume_button.send_keys(path)
                            # log.debug("Resume has been sent to single 'Upload resume' button")
                        time.sleep(3)
                        # if no 'Resume' or 'Cover letter' are in the popup, try clicking 'Next' button
                        next_button.click()
                        # get popup element again
                        next_popup = self.driver.find_element(
                            "class name", "jobs-easy-apply-content"
                        )
                        # if the popup element didn't change, most probably there were questions, which
                        # have to be answered by a person, end working on ths job, write according status to Google Sheets
                        if next_popup.get_attribute("aria-label") == aria_label:
                            log.debug(
                                "The popup didn't move when clicking 'Next', so exiting"
                            )
                            time.sleep(3)
                            self.driver.find_element(
                                "xpath", "//button[@aria-label='Dismiss']"
                            ).click()
                            log.debug(
                                "'Dismiss' button has been clicked after clicking 'Next'"
                            )
                            time.sleep(3)
                            self.driver.find_element(
                                "xpath",
                                "//button[@data-control-name='discard_application_confirm_btn']",
                            ).click()
                            log.debug(
                                "'Discard appliation' has been clicked after clicking 'Next'"
                            )
                            time.sleep(3)
                            self.google_sheets_client.write_cell_to_google_sheets(
                                "Fail: Couldn't fill in form"
                            )
                            break
                        # if the script went to the next popup, then 'Next' button click was successful
                        else:
                            aria_label = next_popup.get_attribute("aria-label")
                    # if no 'Next' button was found (which means there might be 'Review' or 'Submit application' buttons instead of 'Next')
                    except NoSuchElementException:
                        # handling popups with 'Review' button in the popup
                        try:
                            # find setions in the popup
                            section_names = self.driver.find_elements(
                                "xpath", "//h3[contains(@class, 't-bold')]"
                            )
                            section_name_texts = [
                                section_name.text for section_name in section_names
                            ]
                            log.debug(
                                "Names of the popup sections with 'Review' button were fetched"
                            )
                            time.sleep(3)
                            # for future use:
                            # same story, if both 'Resume' and 'Cover letter' are in the popup, send 2 files
                            # if "Resume" and "Cover letter" in section_name_texts:
                            #     log.debug("'Resume' and 'Cover letter' headings were found in section names with 'Review' button")
                            #     time.sleep(3)
                            #     upload_resume_button = self.driver.find_element("xpath", "//button[contains(@aria-label, 'Upload resume')]")
                            #     log.debug("'Upload resume' button was fetched in the popup with 'Review' button")
                            #     upload_resume_button.send_keys(path)
                            #     log.debug("Resume has been sent to 'Upload resume' button n the popup with 'Review' button")
                            #     time.sleep(3)
                            #     upload_cover_letter_button = self.driver.find_element("xpath", "//span[.='Upload cover letter']")
                            #     log.debug("'Upload cover letter' button in the popup with 'Review' button was fetched")
                            #     upload_cover_letter_button.send_keys(path)
                            #     log.debug("Cover letter has been sent to 'Upload cover letter' button in the popup with 'Review' button")
                            # here as well, if only 'Resume' is in the popup, send only 1 file
                            if "Resume" in section_name_texts:
                                if job_name == "ML":
                                    resume = self.driver.find_element(
                                        "xpath",
                                        "//h3[contains(., 'Kseniia_Arshinina_DS_MLE.pdf')]/ancestor::div",
                                    )
                                else:
                                    resume = self.driver.find_element(
                                        "xpath",
                                        "//h3[contains(., 'Kseniia_Arshinina_DE_DA.pdf')]/ancestor::div",
                                    )
                                resume.find_element(
                                    "xpath",
                                    "//label[contains(@id, 'jobsDocumentCardToggleLabel')]",
                                ).click
                                log.debug(
                                    "Resume has been picked in popup with 'Review'"
                                )
                                # for future use:
                                # upload_resume_button = self.driver.find_element("css selector", "button[aria-controls='jobs-document-upload-file-input-upload-resume']")
                                # log.debug("Single 'Upload resume' button was fetched in the popup with 'Review' button")
                                # upload_resume_button.send_keys(path)
                                # log.debug("Resume has been sent to single 'Upload resume' button in the popup with 'Review' button")
                            self.driver.find_element(
                                "xpath",
                                "//button[@aria-label='Review your application']",
                            ).click()
                            log.debug("'Review' button has been clicked")
                            # get popup element again
                            next_popup = self.driver.find_element(
                                "class name", "jobs-easy-apply-content"
                            )
                            # if the popup element didn't change, most probably there were additional questions, which
                            # have to be answered by a person, end working on ths job, write according status to Google Sheets
                            if next_popup.get_attribute("aria-label") == aria_label:
                                log.debug(
                                    "The popup didn't move when clicking 'Review', so exiting"
                                )
                                time.sleep(3)
                                self.driver.find_element(
                                    "xpath", "//button[@aria-label='Dismiss']"
                                ).click()
                                log.debug(
                                    "'Dismiss' button has been clicked after clicking 'Review'"
                                )
                                time.sleep(3)
                                self.driver.find_element(
                                    "xpath",
                                    "//button[@data-control-name='discard_application_confirm_btn']",
                                ).click()
                                log.debug(
                                    "'Discard appliation' has been clicked after clicking 'Review'"
                                )
                                time.sleep(3)
                                self.google_sheets_client.write_cell_to_google_sheets(
                                    "Fail: Couldn't fill in form"
                                )
                                break
                            # if the script went to the next popup, then 'Reivew' button click was successful
                            else:
                                aria_label = next_popup.get_attribute("aria-label")
                        # if there are no sections with the right formatting, then the sript has come to the final popup with
                        # 'Submit application' button and the application has been successful
                        except NoSuchElementException:
                            time.sleep(3)
                            self.driver.find_element(
                                "css selector", "label[for='follow-company-checkbox']"
                            ).click()
                            log.debug("Company has been unfollowed")
                            time.sleep(3)
                            self.driver.find_element(
                                "xpath", "//button[@aria-label='Submit application']"
                            ).click()
                            log.debug("The application has been submitted")
                            time.sleep(3)
                            self.driver.find_element(
                                "xpath", "//button[@aria-label='Dismiss']"
                            ).click()
                            log.debug("Final popup has been closed")
                            self.google_sheets_client.write_cell_to_google_sheets(
                                "Applied"
                            )
                            break

            # if 'Apply' in apply button, send the corresponding status to Google Sheets only
            elif apply.text == "Apply":
                self.google_sheets_client.write_cell_to_google_sheets(
                    "Fail: Apply button"
                )
            # if neither 'Apply' nor 'Easy Apply' found, then there was some problem
            else:
                f"There's been some error when fetching apply button, the text of the button is: {apply.text}"
                self.google_sheets_client.write_cell_to_google_sheets("Fail: Error")
        # skip if already applied
        except NoSuchElementException:
            log.debug("You already applied to this job, going to the next one...")
            pass
        time.sleep(1)

    def get_job_description_info(self, job_description):
        """
        Parse job and:
        - get job link and check if this job has already been processed
        - get position name,
        - get company name,
        - get date this job has been found and processed
        - write all of the above to Google Sheets,
        - get job description text,
        """

        job_description.find_element("xpath", "//button[@aria-label='Share']").click()
        time.sleep(5)
        drop_down_menu = job_description.find_element(
            "xpath", "//div[@aria-hidden='false']"
        )
        drop_down_menu.find_element("xpath", "//*[text()='Copy link']").click()
        time.sleep(5)
        job_link = pyperclip.paste()
        time.sleep(5)
        log.debug(job_link)
        job_description.find_element(
            "xpath", "//button[contains(@aria-label, 'Link copied to clipboard.')]"
        ).click()

        if not self.google_sheets_client.check_job_link(job_link):
            return False
        time.sleep(5)

        job_name = job_description.find_element(
            "class name", "t-24.t-bold.jobs-unified-top-card__job-title"
        ).text
        log.debug(job_name)
        time.sleep(5)

        company_name = job_description.find_element(
            "css selector", "span[class='jobs-unified-top-card__company-name']"
        ).text
        log.debug(company_name)
        time.sleep(5)

        job_details = job_description.find_element(
            "xpath", "//div[@id='job-details']"
        ).text
        time.sleep(5)

        date_processed = datetime.now().strftime("%d-%b-%Y")
        gs_row = [company_name, job_name, date_processed, job_link]

        self.google_sheets_client.write_row_to_google_sheets(gs_row)
        self.google_sheets_client.jobs_seen.append(job_link)

        return job_details

    def close_session(self):
        """This function closes the actual session"""

        log.debug("End of the session, see you later!")
        self.driver.close()

    def ongoing_job_search(self):
        pass

    def apply(self):
        """Apply to job offers"""

        self.driver.maximize_window()
        self.login_linkedin()
        time.sleep(5)
        self.job_search_and_filter()
        time.sleep(5)
        self.find_all_offers()
        # self.go_through_offers()
        time.sleep(2)
        self.close_session()


if __name__ == "__main__":

    path = os.path.realpath(__file__)
    dir = os.path.dirname(path)
    dir = dir.replace("src", "config")
    os.chdir(dir)
    with open(f"{dir}/config.json") as config_file:
        data = json.load(config_file)
    bot = EasyApplyLinkedin(data)
    bot.apply()
