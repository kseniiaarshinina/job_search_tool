import openai
import nltk
import re
import pandas as pd


def check_job_fits(
    open_ai_api_key, job_description, work_fields, experience_years, degree
):
    """
    Check that the job meets required field of work, years of experience and education degree
    """
    work_fields = ", ".join(work_fields)
    right_job = gpt_answers(
        open_ai_api_key,
        job_description,
        f"Is this text about {work_fields}? Answer yes or no\n",
    )
    if right_job == "No":
        return False
    text = clean_text(job_description)
    if get_experience(text) > experience_years:
        return False
    if not check_degree(degree, text):
        return False

    return ML_or_DE(open_ai_api_key, job_description)


def gpt_answers(open_ai_api_key, text, question):
    """
    Sending prompt to GPT and getting an answer
    """
    openai.api_key = open_ai_api_key
    response = openai.Completion.create(
        engine="text-davinci-002",
        prompt=f"{question}\n" + text,
        temperature=0.6,
        top_p=1,
        max_tokens=64,
        frequency_penalty=0,
        presence_penalty=0,
    )
    return response.choices[0].text


def clean_text(text):
    """
    Clean text from unnecessary symbols, tokenize it and split into separate sentences
    """
    tokenizer = nltk.data.load("tokenizers/punkt/english.pickle")
    regex_cleaned_text = re.sub(r"·", "", text)
    # Format words and remove unwanted characters
    # text = re.sub(r'https?:\/\/.*[\r\n]*', '', text, flags=re.MULTILINE)
    # text = re.sub(r'\<a href', ' ', text)
    # text = re.sub(r'\ufeff', '', text)
    # text = re.sub(r'&amp;', '', text)
    # text = re.sub(r'[_"\-;%()|+&=*%,!?:#$@\[\]/]', ' ', text)
    # text = re.sub(r'<br />', ' ', text)
    # text = re.sub(r'\'', ' ', text)
    tokenized_text = tokenizer.tokenize(regex_cleaned_text)
    text = []
    for sentence in tokenized_text:
        text.extend(sentence.split("\n\n"))
    text = [
        re.sub(r"\n", "", item.lstrip("o ").lstrip(" ")) for item in text if item != ""
    ]
    return text


def get_experience(text):
    """
    Get the number of years of experience needed from the job description
    """
    match_list = []
    number_match_list = []
    for sentence in text:
        match = re.findall(r"(?:^|\W)experience(?:$|\W)", sentence, flags=re.IGNORECASE)
        if match:
            match_list.append(sentence)
    max_number_of_years = 0
    for exp_sent in match_list:
        num_match = re.findall(r"[0-9]+", exp_sent)
        if num_match:
            num_match = [int(num) for num in num_match]
            if max(num_match) > max_number_of_years:
                max_number_of_years = max(num_match)
            number_match_list.append(exp_sent)
    return max_number_of_years


def check_degree(degree, text):
    """
    Get the lowest degree needed for the position. If none found, the job description's degree is automatically ok
    """
    bachelor_list = []
    master_list = []
    phd_list = []
    for sentence in text:
        bachelor = re.findall(r"(?:^|\W)Bachelor(?:$|\W)|(?:^|\W)BS(?:$|\W)", sentence)
        master = re.findall(r"(?:^|\W)Master(?:$|\W)|(?:^|\W)MS(?:$|\W)", sentence)
        phd = re.findall(r"(?:^|\W)PhD(?:$|\W)", sentence)
        bachelor_list.extend(bachelor)
        master_list.extend(master)
        phd_list.extend(phd)

    if degree == "PhD":
        return True
    elif degree == "Master":
        if len(master_list) > 0 or len(bachelor_list) > 0:
            return True
        elif len(phd_list) > 0:
            return False
        else:
            return True
    elif degree == "Bachelor":
        if len(bachelor_list) > 0:
            return True
        elif len(phd_list) > 0 or len(master_list) > 0:
            return False
        else:
            return True


def ML_or_DE(open_ai_api_key, text):
    """
    This funtion helps undesrtand which CV has to be sent in the appliation
    """
    prompt = "Does this text desribe machine learning engineer/data scientist or data engineer/data analyst?\n"
    answer = gpt_answers(open_ai_api_key, text, prompt)
    ML = re.findall(
        r"(?:^|\W)Machine learning engineer(?:$|\W)|(?:^|\W)data scientist(?:$|\W)|(?:^|\W)AI(?:$|\W)",
        answer,
        flags=re.IGNORECASE,
    )
    DE = re.findall(
        r"(?:^|\W)data engineer(?:$|\W)|(?:^|\W)data analyst(?:$|\W)",
        answer,
        flags=re.IGNORECASE,
    )
    if ML:
        return "ML"
    elif DE:
        return "DE"
    else:
        return "Random"
