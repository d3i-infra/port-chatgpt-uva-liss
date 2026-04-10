"""FlowBuilder — shared per-platform donation flow orchestration.

Subclass this to implement a platform-specific donation flow.
Override validate_file() and extract_data(). Call start_flow()
as a generator from script.py via `yield from`.
"""
from abc import abstractmethod
from collections.abc import Generator
import json
import logging
import pandas as pd
from  typing import Tuple

import port.api.props as props
import port.api.d3i_props as d3i_props
import port.helpers.port_helpers as ph
import port.helpers.validate as validate
import port.helpers.uploads as uploads


# STUDY SPECIFIC FUNCTIONALITY

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

logger = logging.getLogger(__name__)


class FlowBuilder:
    def __init__(self, session_id: str, platform_name: str):
        self.session_id = session_id
        self.platform_name = platform_name
        self._initialize_ui_text()

    def _initialize_ui_text(self):
        """Initialize UI text based on platform name."""
        self.UI_TEXT = {
            "submit_file_header": props.Translatable({
                "en": f"Select your {self.platform_name} file",
                "nl": f"Selecteer uw {self.platform_name} bestand",
            }),
            "review_data_header": props.Translatable({
                "en": f"Your {self.platform_name} data",
                "nl": f"Uw {self.platform_name} gegevens",
            }),
            "retry_header": props.Translatable({
                "en": "Try again",
                "nl": "Probeer opnieuw",
            }),
            "review_data_description": props.Translatable({
                "en": f"Below you will find a curated selection of {self.platform_name} data.",
                "nl": f"Hieronder vindt u een zorgvuldig samengestelde selectie van {self.platform_name} gegevens.",
            }),
        }

    def start_flow(self):
        """Main per-platform flow: file→materialize→safety→validate→retry→extract→consent→donate.

        This is a generator. script.py calls it via `yield from flow.start_flow()`.
        Control flow rules:
        - continue: retry upload only
        - break: successful extraction, proceed to consent
        - return: every terminal path

        Flow milestones are sent to the host via explicit CommandSystemLog yields
        (through emit_log). These must be PII-free. Local logger keeps full
        diagnostic detail in browser console only.
        """
        while True:
            # 1. Render file prompt → receive payload
            logger.info("Prompt for file for %s", self.platform_name)
            file_prompt = self.generate_file_prompt()
            file_result = yield ph.render_page(self.UI_TEXT["submit_file_header"], file_prompt)

            # Skip: user didn't select a file
            if file_result.__type__ not in ("PayloadFile", "PayloadString"):
                logger.info("Skipped at file selection for %s", self.platform_name)
                return

            # 2. Materialize upload to path
            path = uploads.materialize_file(file_result)
            file_size = getattr(file_result.value, "size", None) if file_result.__type__ == "PayloadFile" else None
            yield from ph.emit_log("info", f"[{self.platform_name}] File received: {file_size or 'unknown'} bytes, {file_result.__type__}")

            # 3. Safety check
            try:
                uploads.check_file_safety(path)
            except (uploads.FileTooLargeError, uploads.ChunkedExportError) as e:
                logger.error("Safety check failed for %s: %s", self.platform_name, e)
                yield from ph.emit_log("info", f"[{self.platform_name}] Safety check failed: {type(e).__name__}")
                _ = yield ph.render_safety_error_page(self.platform_name, e)
                return

            # 4. Validate
            validation = self.validate_file(path)
            status = validation.get_status_code_id()
            category = getattr(validation, "current_ddp_category", None)
            category_id = getattr(category, "id", "unknown") if category else "unknown"

            if status == 0:
                yield from ph.emit_log("info", f"[{self.platform_name}] Validation: valid ({category_id})")
            else:
                yield from ph.emit_log("info", f"[{self.platform_name}] Validation: invalid")

            # 5. If invalid → retry prompt
            if status != 0:
                logger.info("Invalid %s file; prompting retry", self.platform_name)
                retry_prompt = self.generate_retry_prompt()
                retry_result = yield ph.render_page(self.UI_TEXT["retry_header"], retry_prompt)
                if retry_result.__type__ == "PayloadTrue":
                    continue  # loop back to step 1
                return  # user declined retry

            # 6. Extract
            logger.info("Extracting data for %s", self.platform_name)
            raw_result = self.extract_data(path, validation)
            if isinstance(raw_result, Generator):
                result = yield from raw_result
            else:
                result = raw_result

            # 7. Log extraction summary (PII-free: counts only)
            total_rows = sum(len(t.data_frame) for t in result.tables)
            if result.errors:
                error_summary = ", ".join(f"{k}×{v}" for k, v in result.errors.items())
                yield from ph.emit_log("info", f"[{self.platform_name}] Extraction complete: {len(result.tables)} tables, {total_rows} rows; errors: {error_summary}")
            else:
                yield from ph.emit_log("info", f"[{self.platform_name}] Extraction complete: {len(result.tables)} tables, {total_rows} rows; errors: none")

            # 8. If no tables → no-data page
            if not result.tables:
                logger.info("No data extracted for %s", self.platform_name)
                _ = yield ph.render_no_data_page(self.platform_name)
                return

            break  # proceed to consent

        # 9. Render consent form
        yield from ph.emit_log("info", f"[{self.platform_name}] Consent form shown")
        review_data_prompt = self.generate_review_data_prompt(result.tables)
        consent_result = yield ph.render_page(self.UI_TEXT["review_data_header"], review_data_prompt)

        # 10. Donate with per-platform key
        if consent_result.__type__ == "PayloadJSON":
            reviewed_data = consent_result.value
            yield from ph.emit_log("info", f"[{self.platform_name}] Consent: accepted")
        elif consent_result.__type__ == "PayloadFalse":
            reviewed_data = json.dumps({"status": "data_submission declined"})
            yield from ph.emit_log("info", f"[{self.platform_name}] Consent: declined")
        else:
            return

        donate_key = f"{self.session_id}-{self.platform_name.lower()}"
        is_decline = consent_result.__type__ == "PayloadFalse"
        yield from ph.emit_log("info", f"[{self.platform_name}] Donation started: payload size={len(reviewed_data)} bytes")
        donate_result = yield ph.donate(donate_key, reviewed_data)

        # 11. Inspect donate result
        # For declines, don't show failure UI — the participant chose not to donate,
        # so a failure to record that decision is invisible infrastructure, not their problem.
        if not ph.handle_donate_result(donate_result):
            if is_decline:
                logger.warning("Decline status donation failed for %s (silent)", self.platform_name)
                yield from ph.emit_log("info", f"[{self.platform_name}] Donation result: decline record failed (silent)")
                return
            logger.error("Donation failed for %s", self.platform_name)
            yield from ph.emit_log("info", f"[{self.platform_name}] Donation result: failed")
            _ = yield ph.render_donate_failure_page(self.platform_name)
            return
        else:
            # render questionnaire
            # modified including three questions and answers rather than just a random one
            donated_data = json.loads(reviewed_data)[0]["chatgpt_conversations"]
            print(donated_data)
            if len(donated_data) > 0:
                questions_and_answers = select_three_qas(donated_data)
                for index, (question, answer) in enumerate(questions_and_answers, start=1):
                    if question and answer:
                        questionnaire_results = yield ph.render_page(
                            props.Translatable({"en": "", "nl": ""}), 
                            generate_questionnaire(question, answer, index)
                        )
                        
                        if questionnaire_results.__type__ == "PayloadJSON":
                            yield ph.donate(
                                f"{self.session_id}-questionnaire-{index}-donation", 
                                questionnaire_results.value
                            )

        yield from ph.emit_log("info", f"[{self.platform_name}] Donation result: success")

    # Methods to be overridden by platform-specific implementations
    def generate_file_prompt(self):
        """Generate platform-specific file prompt."""
        return ph.generate_file_prompt("application/zip")

    @abstractmethod
    def validate_file(self, file: str) -> validate.ValidateInput:
        """Validate the file according to platform-specific rules."""
        raise NotImplementedError("Must be implemented by subclass")

    @abstractmethod
    def extract_data(self, file: str, validation: validate.ValidateInput) -> d3i_props.ExtractionResult:
        """Extract data from file using platform-specific logic."""
        raise NotImplementedError("Must be implemented by subclass")

    def generate_retry_prompt(self):
        """Generate platform-specific retry prompt."""
        return ph.generate_retry_prompt(self.platform_name)

    def generate_review_data_prompt(self, table_list):
        """Generate platform-specific review data prompt."""
        return ph.generate_review_data_prompt(
            description=self.UI_TEXT["review_data_description"],
            table_list=table_list,
        )
