# job_search_tool
## A tool to apply to jobs as automatically as possible

To start using this tool you will need to:
1. Install all the packages in the requirements
2. Download a chromedriver
3. Set up your Google API to be able to use Google Sheets
4. Write your info in config.json file

### Fields in config.json file:
- "email" - your email as login to LinkedIn
- "password" - your password to LinkedIn
- "keywords" - list of desired positions to search for, e.g. Machine Learning Engineer
- "location" - list of desired locations, e.g. United States
- "work mode" - list of LinkedIn work modes: "On-Site", "Hybrid", "Remote"
- "date posted" - LinkedIn date posted options: "Any time", "Past week", "Past 24 hours", "Past month"
- "work fields" - the field of your job, e.g. machine learning
- "years of experience" - the number of years of experience that you have
- "degree" - education degree that you have, 3 options: "Bachelor", "Master", "PhD"
- "driver_path" - a path to your chromedriver
- "open_ai_api_key" - your personal key for using openai library
- "google_api_file" - a path to the json file with your Google API configurations
- "name_of_spreadsheet" - name of the Google Sheet that you are going to use for this tool
- "sh status column" - a letter of the column in your Google Sheet where all job lonks will be recorded (should be the 5th column, "E")
