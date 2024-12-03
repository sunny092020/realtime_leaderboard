from typing import Optional

from dynamodb_operations import DynamoDBOperations


def calculate_score(
    answer: str, quiz_id: str, user_id: str, dynamodb_ops: DynamoDBOperations
) -> int:
    # Get the user's past score from DynamoDB
    past_score = dynamodb_ops.get_user_score(user_id, quiz_id)

    # Calculate new score (implement your scoring logic here)
    new_score = len(answer)

    # Accumulate past score with new score
    total_score = past_score + new_score
    return total_score
