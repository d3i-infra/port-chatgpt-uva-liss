"""
ChatGPT

This module provides an example flow of a ChatGPT data donation study

Assumptions:
It handles DDPs in the english language with filetype JSON.
"""
import logging
from collections import Counter

import pandas as pd
import re

import port.api.props as props
import port.api.d3i_props as d3i_props
from port.api.d3i_props import ExtractionResult
import port.helpers.extraction_helpers as eh
import port.helpers.validate as validate
from port.helpers.extraction_helpers import ZipArchiveReader
from port.helpers.flow_builder import FlowBuilder

import port.helpers.redact as redact

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


def conversations_to_df(reader: ZipArchiveReader, errors: Counter) -> pd.DataFrame:
    datapoints = []

    # 1. Collect all matching files BEFORE calling reader.json
    conversation_files = [
        m for m in reader.archive_members
        if re.search(r"(?:^|/)conversations.*\.json$", m)
    ]

    try:
        for member in conversation_files:
            result = reader.json(member)
            if not result.found:
                continue

            conversations = result.data

            for conversation in conversations:
                title = conversation.get("title", "")
                conversation_id = conversation.get("conversation_id", "")
                first_question = None
                first_answer = None

                for _, turn in conversation.get("mapping", {}).items():
                    denested_d = eh.dict_denester(turn)

                    is_hidden = eh.find_item(denested_d, "is_visually_hidden_from_conversation")
                    content_type = eh.find_item(denested_d, "content_type")
                    role = eh.find_item(denested_d, "role")

                    if (content_type != "text") or (is_hidden == "True") or (role not in ["user", "assistant"]):
                        continue

                    message = "".join(eh.find_items(denested_d, "part"))

                    # Skip empty assistant responses
                    if (role == "assistant") and (not message):
                        continue

                    model = eh.find_item(denested_d, "-model_slug")
                    time = eh.epoch_to_iso(
                        eh.find_item(denested_d, "create_time"),
                        errors=errors
                    )

                    # Identify first Q/A
                    id_ = eh.find_item(denested_d, "id")
                    if (role == "user") and (not first_question):
                        first_question = id_
                    elif (role == "assistant") and (not first_answer):
                        first_answer = id_

                    datapoints.append({
                        "conversation title": title,
                        "role": role,
                        "message": redact.redact(message),
                        "model": model,
                        "time": time,
                        "conversation_id": conversation_id,
                        "is_first": (id_ == first_question) or (id_ == first_answer),
                    })

        return pd.DataFrame(datapoints)

    except Exception as e:
        logger.error("Data extraction error: %s", e)
        errors[type(e).__name__] += 1
        return pd.DataFrame()


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
