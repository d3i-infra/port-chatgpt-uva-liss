"""
ChatGPT

This module provides an example flow of a ChatGPT data donation study

Assumptions:
It handles DDPs in the english language with filetype JSON.
"""
import logging
from collections import Counter
from typing import Tuple

import pandas as pd

import port.api.props as props
import port.api.d3i_props as d3i_props
from port.api.d3i_props import ExtractionResult
import port.helpers.extraction_helpers as eh
import port.helpers.validate as validate
from port.helpers.extraction_helpers import ZipArchiveReader
from port.helpers.flow_builder import FlowBuilder

from port.helpers.validate import (
    DDPCategory,
    DDPFiletype,
    Language,
)

logger = logging.getLogger(__name__)

DDP_CATEGORIES = [
    DDPCategory(
        id="json",
        ddp_filetype=DDPFiletype.JSON,
        language=Language.EN,
        known_files=[
            "chat.html", 
            "conversations.json",
            "message_feedback.json",
            "model_comparisons.json",
            "user.json"
        ]
    )
]


def conversations_to_df(reader: ZipArchiveReader, errors: Counter)  -> pd.DataFrame:
    result = reader.json("conversations.json")
    if not result.found:
        return pd.DataFrame()
    conversations = result.data

    datapoints = []
    out = pd.DataFrame()

    try:
        for conversation in conversations:
            title = conversation["title"]
            conversation_id = conversation["conversation_id"]
            first_question = None
            first_answer = None
            for _, turn in conversation["mapping"].items():

                denested_d = eh.dict_denester(turn)
                is_hidden = eh.find_item(denested_d, "is_visually_hidden_from_conversation")
                content_type = eh.find_item(denested_d, "content_type")
                role = eh.find_item(denested_d, "role")
                if (content_type != "text") or (is_hidden == "True") or (role not in ["user", "assistant"]):
                    continue
                message = "".join(eh.find_items(denested_d, "part"))
                # In some cases, an assistant's response is empty
                if (role == "assistant") and (not message):
                    continue
                model = eh.find_item(denested_d, "-model_slug")
                time = eh.epoch_to_iso(eh.find_item(denested_d, "create_time"))
                # Is first question or answer?
                id = eh.find_item(denested_d, "id")
                if (role == "user") and (not first_question):
                    first_question = id
                elif (role == "assistant") and (not first_answer):
                    first_answer = id
                datapoint = {
                    "conversation title": title,
                    "role": role,
                    "message": message,
                    "model": model,
                    "time": time,
                    "conversation_id": conversation_id,
                    "is_first": True if ((first_question == id) or (first_answer == id)) else False  # Label first qa pair
                }
                datapoints.append(datapoint)

        out = pd.DataFrame(datapoints)

    except Exception as e:
        logger.error("Data extraction error: %s", e)
        
    return out


def extraction(chatgpt_zip: str, validation) -> ExtractionResult:
    """
    Add your table definitions below in the list
    """
    errors = Counter()
    reader = ZipArchiveReader(chatgpt_zip, validation.archive_members, errors)
    tables = [
        d3i_props.PropsUIPromptConsentFormTableViz(
            id="chatgpt_conversations",
            data_frame=conversations_to_df(reader, errors),
            title=props.Translatable({
                "en": "Your conversations with ChatGPT",
                "nl": "Uw gesprekken met ChatGPT"
            }),
            description=props.Translatable({
                "en": "In this table you find your conversations with ChatGPT sorted by time. Below, you find a wordcloud, where the size of the words represents how frequent these words have been used in the conversations.", 
                "nl": "In this table you find your conversations with ChatGPT sorted by time. Below, you find a wordcloud, where the size of the words represents how frequent these words have been used in the conversations.", 
            }),
            visualizations=[
                {
                    "title": {
                        "en": "Your messages in a wordcloud", 
                        "nl": "Your messages in a wordcloud"
                    },
                    "type": "wordcloud",
                    "textColumn": "message",
                    "tokenize": True,
                }
            ]
        ),
    ]

    tables_to_render = [table for table in tables if not table.data_frame.empty]

    return ExtractionResult(
        tables=tables_to_render,
        errors=errors,
    )



def select_three_qas(donated_data: list[dict])  -> list[Tuple[str, str]]:
    """
    Code to extract first, middle and last message sent by the user and corresponding answer by ChatGPT
    The extra effort is made here to make sure the answers is actually a follow up of the question 
    and to make sure the question is the first in the conversation
    """

    # Only consider conversations where the first qa pair wasn't deleted
    conversations = pd.DataFrame(donated_data)
    conversations = conversations[conversations.is_first == "true"].groupby("conversation_id", as_index=False).filter(lambda x: len(x) == 2)

    # Select first, last and middle conversation if possible   
    conversation_ids = conversations['conversation_id'].unique()
    if len(conversation_ids) == 0:
        indexes = []
    elif len(conversation_ids) == 1:
        indexes = [0]
    elif len(conversation_ids) == 2:
        indexes = [0, 1]
    else:
        indexes = [0, len(conversation_ids)//2, -1]
    selected_ids = [conversation_ids[i] for i in indexes]
    selected_conversations = conversations[conversations['conversation_id'].isin(selected_ids)]
    
    messages = selected_conversations["message"].tolist()
    questions_and_answers = list(zip(messages[0::2], messages[1::2]))

    return questions_and_answers


# Random question questionnaire

# Question measuring trust in answer provided by ChatGPT

Q1 = props.Translatable(
    {
        "en": "To what extent do you trust the answer provided by ChatGPT?",
        "nl": "Hoeveel vertrouwen heeft u in het antwoord van ChatGPT?"
    })
Q1_CHOICES = [
    props.Translatable(
        {
            "en": "1. I do not trust it at all", 
            "nl": "1. Helemaal geen vertrouwen"
        }),
    props.Translatable(
        {
            "en": "2", 
             "nl": "2"
        }),
    props.Translatable(
        {
            "en": "3", 
            "nl": "3"
        }),
    props.Translatable(
        {
            "en": "4",
             "nl": "4"
         }),
    props.Translatable(
        {
            "en": "5",
            "nl": "5"
         }),
    props.Translatable(
        {
            "en": "6",
             "nl": "6"
         }),
    props.Translatable({
        "en": "7. I trust it completely", 
        "nl": "7. Volledig vertrouwen"
    })
]

# Question measuring privacy

Q2 = props.Translatable(
    {
        "en": "The information in this conversation is:",
        "nl": "De informatie in dit gesprek is:"
    })
Q2_CHOICES = [
    props.Translatable(
        {
            "en": "1. Not at all personal about me", 
            "nl": "1. Helemaal niet persoonlijk over mij"
        }),
    props.Translatable(
        {
            "en": "2", 
             "nl": "2"
        }),
    props.Translatable(
        {
            "en": "3", 
            "nl": "3"
        }),
    props.Translatable(
        {
            "en": "4",
             "nl": "4"
         }),
    props.Translatable(
        {
            "en": "5",
            "nl": "5"
         }),
    props.Translatable(
        {
            "en": "6",
             "nl": "6"
         }),
    props.Translatable({
        "en": "7. Highly personal about me", 
        "nl": "7. Heel persoonlijk over mij"
    })
]

# Question measuring use type

Q3 = props.Translatable(
    {
        "en": "What is this conversation about?",
        "nl": "Waar gaat dit gesprek over?"
    })
Q3_CHOICES = [
    props.Translatable(
        {
            "en": "1. Help with work or school", 
            "nl": "1. Hulp bij werk of school"
        }),
    props.Translatable(
        {
            "en": "2. Writing texts or improving them", 
             "nl": "2. Teksten schrijven of beter maken"
        }),
    props.Translatable(
        {
            "en": "3. Entertainment or doing something fun", 
            "nl": "3. Amusement of iets leuks doen"
        }),
    props.Translatable(
        {
            "en": "4. Coming up with creative ideas or new things",
             "nl": "4. Creatieve ideeën of nieuwe dingen bedenken"
         }),
    props.Translatable(
        {
            "en": "5. Help to learn something new or understand something difficult better",
            "nl": "5. Hulp om iets nieuws te leren of iets moeilijks beter te snappen"
         }),
    props.Translatable(
        {
            "en": "6. Looking up information or answering questions",
             "nl": "6. Informatie zoeken of vragen beantwoorden"
         }),
    props.Translatable({
            "en": "7. News and current events", 
            "nl": "7. Nieuws en actualiteiten"
        }), 
    props.Translatable({
            "en": "8. Just talking or looking for company", 
             "nl": "8. Gewoon praten of gezelschap zoeken"
        }), 
    props.Translatable({
            "en": "9. Talking about personal questions or sensitive topics", 
            "nl": "9. Persoonlijke vragen of gevoelige onderwerpen bespreken"
        }), 
    props.Translatable({
            "en": "10. Help with daily things, like cooking, traveling, or other practical tasks", 
             "nl": "10. Hulp bij dagelijkse dingen, zoals koken, reizen of andere praktische zaken"
        }), 
    props.Translatable({
        "en": "11. Something else", 
        "nl": "11. Iets anders"
    })
]

#def render_questionnaire(question: str, answer: str):
#    questions = [
#        props.PropsUIQuestionMultipleChoice(question=Q1, id=1, choices=Q1_CHOICES),
#    ]
#
#    description = props.Translatable(
#        {
#            "en": "Below you can find the start of a conversation you had with ChatGPT. We would like to ask you a question about it.",
#            "nl": "Hieronder vind u het begin van een gesprek dat u heeft gehad met ChatGPT. We willen u daar een vraag over stellen."
#        })
#    header = props.PropsUIHeader(props.Translatable({"en": "Questionnaire", "nl": "Vragenlijst"}))
#    body = props.PropsUIPromptQuestionnaire(
#        questions=questions, 
#        description=description,
#        questionToChatgpt=question,
#        answerFromChatgpt=answer,
#    )
#    footer = props.PropsUIFooter()
#
#    page = props.PropsUIPageDonation("ASD", header, body, footer)
#    return CommandUIRender(page)


def generate_questionnaire(question: str, answer: str, index: int) -> d3i_props.PropsUIPromptQuestionnaire:
    """
    Administer a basic questionnaire in Port.
    This function generates a prompt which can be rendered with render_page().
    The questionnaire demonstrates all currently implemented question types.
    In the current implementation, all questions are optional.
    You can build in logic by:
    - Chaining questionnaires together
    - Using extracted data in your questionnaires
    Usage:
        prompt = generate_questionnaire()
        results = yield render_page(header_text, prompt)
        
    The results.value contains a JSON string with question answers that 
    can then be donated with donate().
    """
    
    questionnaire_description = props.Translatable({
        "en": "Thank you. We would like to understand how people talk with ChatGPT. Our system has selected up to three conversations that you had with ChatGPT in the past. Below you can view one of these conversations. Could you please help us by answering the questions below?",
        "nl": "Dank u. We willen graag weten hoe mensen met ChatGPT praten. Ons systeem heeft tot drie gesprekken gekozen die u eerder met ChatGPT had. Hieronder ziet u één van deze gesprekken. Kunt u ons alstublieft helpen door de vragen hieronder te beantwoorden?"
    })
    
    multiple_choice_trust = d3i_props.PropsUIQuestionMultipleChoice(
        id=f"{index}-trust",
        question=Q1,
        choices=Q1_CHOICES,
    )

    multiple_choice_privacy = d3i_props.PropsUIQuestionMultipleChoice(
        id=f"{index}-privacy",
        question=Q2,
        choices=Q2_CHOICES,
    )

    multiple_choice_usetype = d3i_props.PropsUIQuestionMultipleChoice(
        id=f"{index}-usetype",
        question=Q3,
        choices=Q3_CHOICES,
    )
    
    return d3i_props.PropsUIPromptQuestionnaire(
        description=questionnaire_description,
        questions=[
            multiple_choice_trust,
            multiple_choice_privacy,
            multiple_choice_usetype
        ],
        questionToChatgpt=question,
        answerFromChatgpt=answer,
    )



class ChatGPTFlow(FlowBuilder):
    def __init__(self, session_id: str):
        super().__init__(session_id, "ChatGPT")
        
    def validate_file(self, file):
        return validate.validate_zip(DDP_CATEGORIES, file)
        
    def extract_data(self, file_value, validation):
        return extraction(file_value, validation)


def process(session_id):
    flow = ChatGPTFlow(session_id)
    return flow.start_flow()
