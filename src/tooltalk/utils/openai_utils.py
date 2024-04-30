"""
Copyright (c) Microsoft Corporation.
Licensed under the MIT license.
"""
import logging
import time
from functools import wraps
import os

import openai

logger = logging.getLogger(__name__)


def retry_on_limit(func, retries=5, wait=60):
    @wraps(func)
    def wrapper(*args, **kwargs):
        for i in range(retries):
            try:
                return func(*args, **kwargs)
            except openai.RateLimitError as error:
                logger.info(str(error))
                time.sleep(wait)
        raise openai.RateLimitError
    return wrapper


client = openai.OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
openai_chat_completion = retry_on_limit(client.chat.completions.create)
openai_completion = retry_on_limit(client.completions.create)
