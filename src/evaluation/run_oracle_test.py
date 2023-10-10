import argparse
import copy
import os
import sys
import json
import logging

from tqdm import tqdm

from paper.evaluation.tool_executor import ToolExecutor, BaseAPIPredictor
from paper.utils.file_utils import get_names_and_paths

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)
os.environ["API_TALK_DEBUG"] = "1"


class OraclePredictor(BaseAPIPredictor):
    """
    Stores entire conversation, then determines conversation state from conversation_history.
    It then passes in the next, correct API call based off of ground truth.

    aka it produces oracle predictions for testing purposes.
    """

    def __init__(self, conversation: dict, disable_session_token: bool = False):
        self.conversation = conversation
        self.disable_session_token = disable_session_token

    def predict(self, metadata: dict, conversation_history: dict) -> dict:
        assert metadata == self.conversation["metadata"]
        turn_index = 0
        api_index = 0
        for turn in conversation_history:
            # ignore api calls
            if turn["role"] == "assistant" or turn["role"] == "user":
                api_index = 0
                turn_index += 1
            elif turn["role"] == "api":
                api_index += 1
            else:
                raise ValueError(f"Unknown role {turn['role']}")

        if len(self.conversation["conversation"]) <= turn_index:
            raise ValueError("Conversation history is longer than ground truth conversation")

        turn = self.conversation["conversation"][turn_index]

        if "apis" in turn:
            if len(turn["apis"]) < api_index:
                raise ValueError("Current api history is longer than ground truth api history")
            elif len(turn["apis"]) == api_index:
                return {
                    "role": "assistant",
                    "text": turn["text"]
                }
            else:
                parameters = copy.deepcopy(turn["apis"][api_index]["request"]["parameters"])
                if "session_token" in parameters and self.disable_session_token:
                    del parameters["session_token"]
                return {
                    "role": "api",
                    "request": {
                        "api_name": turn["apis"][api_index]["request"]["api_name"],
                        "parameters": parameters
                    }
                }
        else:
            return {
                "role": "assistant",
                "text": turn["text"]
            }


def get_arg_parser():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset_name", type=str)
    parser.add_argument("--disable_session_token", action="store_true")

    return parser


def main():
    """
    go through every conversation in dataset and simulate each turn
    then execute ground truth verifying that it matches 100%
    """
    parser = get_arg_parser()
    args = parser.parse_args()
    this_dir = os.path.dirname(os.path.abspath(__file__))
    data_dir = os.path.abspath(os.path.join(this_dir, "..", "data"))
    test_dataset_path = os.path.join(data_dir, args.dataset_name)
    test_database_path = os.path.join(data_dir, "databases")

    tool_executor = ToolExecutor(
        init_database_dir=test_database_path,
        disable_session_token=args.disable_session_token
    )
    for file_name, file_path in tqdm(get_names_and_paths(test_dataset_path)):
        logger.info(f"Running conversation: {file_name}")
        with open(file_path, 'r', encoding='utf-8') as reader:
            conversation = json.load(reader)

        predictor_func = OraclePredictor(conversation, disable_session_token=args.disable_session_token)
        conversation_with_predictions = tool_executor.run_conversation(conversation, predictor_func)
        conversation_with_metrics = tool_executor.evaluate_predictions(conversation_with_predictions)
        metrics = conversation_with_metrics["metrics"]
        assert metrics["precision"] == 1.0
        assert metrics["recall"] == 1.0
        assert metrics["success"]
        logger.info(f"Conversation: {file_name} passed!")


if __name__ == '__main__':
    main()
