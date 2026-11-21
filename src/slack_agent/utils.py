import logging
import os
import re

import ollama
from langchain_core.messages import BaseMessage

logger = logging.getLogger(__name__)


def first_env(names: list[str]) -> str | None:
    return next((os.environ[n] for n in names if os.environ.get(n)), None)


def message_text(message: BaseMessage) -> str:
    content = message.content
    if isinstance(content, str):
        return content
    return ''.join(
        block.get('text', '') if isinstance(block, dict) else block
        for block in content
    )


def to_slack_markdown(text: str) -> str:
    return re.sub(r'\*\*(.+?)\*\*', r'*\1*', text)


def ensure_model(model: str) -> None:
    try:
        ollama.show(model)
    except ollama.ResponseError as e:
        if e.status_code != 404:
            raise
        logger.info('Model %s not found locally, pulling it', model)
        status = ''
        for update in ollama.pull(model, stream=True):
            if update.status != status:
                status = update.status or ''
                logger.info('Pulling %s: %s', model, status)
        logger.info('Model %s is ready', model)
