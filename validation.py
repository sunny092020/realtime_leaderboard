from typing import Dict, Tuple
from const import VALID_QUIZZES, VALID_USER_IDS

def validate_user_and_quiz(user_id: str, quiz_id: str) -> Tuple[bool, str]:
    if user_id not in VALID_USER_IDS:
        return False, "Invalid user ID"
    if quiz_id not in VALID_QUIZZES:
        return False, "Invalid quiz ID"
    return True, ""

def validate_quiz_id(quiz_id: str) -> Tuple[bool, str]:
    if quiz_id not in VALID_QUIZZES:
        return False, "Invalid quiz ID"
    return True, "" 