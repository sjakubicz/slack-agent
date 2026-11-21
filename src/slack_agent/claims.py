import re
from typing import Any

from langchain_core.messages import AIMessage, AnyMessage, HumanMessage

from slack_agent.config import ChecksConfig
from slack_agent.dataset import Reviews
from slack_agent.utils import message_text


def mentions(text: str, word: str) -> bool:
    return bool(re.search(rf'\b{re.escape(word)}\b', text, re.IGNORECASE))


def normalized(text: str) -> str:
    return ' '.join(text.lower().split())


def states_statistics(text: str) -> bool:
    return bool(
        re.search(r'\d+%', text)
        and re.search(r'\b(reviews?|positive|negative)\b', text, re.IGNORECASE)
    )


def analyzed_keywords(messages: list[AnyMessage]) -> list[str]:
    return [
        call['args']['keyword']
        for message in messages
        if isinstance(message, AIMessage)
        for call in message.tool_calls
        if call['name'] == 'analyze_reviews'
    ]


def last_post(messages: list[AnyMessage]) -> dict[str, Any] | None:
    ai = next(
        (
            m
            for m in reversed(messages)
            if isinstance(m, AIMessage) and m.tool_calls
        ),
        None,
    )
    calls = ai.tool_calls if ai else []
    return next(
        (c['args'] for c in calls if c['name'] == 'post_to_channel'), None
    )


def user_request(messages: list[AnyMessage]) -> str:
    return next(
        (message_text(m) for m in messages if isinstance(m, HumanMessage)), ''
    )


def find_problem(
    checks: ChecksConfig,
    reviews: Reviews,
    text: str,
    keyword: str,
    request: str,
) -> str | None:
    count, positive = reviews.stats(keyword)
    negative = f'{100 - int(positive.rstrip("%"))}%'
    percents = re.findall(r'\d+%', text)
    numbers = re.findall(r'\d+', re.sub(r'\d+%', '', text))
    wrong = [p for p in percents if p not in (positive, negative)]
    hint = checks.hint.format(request=request)
    problems = [
        (
            not mentions(request, keyword),
            checks.keyword_not_in_request.format(keyword=keyword, hint=hint),
        ),
        (
            count == 0,
            checks.no_matches.format(keyword=keyword, hint=hint),
        ),
        (
            not mentions(text, keyword),
            checks.keyword_not_mentioned.format(keyword=keyword),
        ),
        (
            positive not in percents,
            checks.missing_positive.format(positive=positive),
        ),
        (
            bool(wrong),
            checks.wrong_percent.format(
                wrong=', '.join(wrong), positive=positive, negative=negative
            ),
        ),
        (
            str(count) not in numbers,
            checks.missing_count.format(count=count),
        ),
    ]
    return next((problem for failed, problem in problems if failed), None)


def check_claims(
    checks: ChecksConfig,
    reviews: Reviews,
    messages: list[AnyMessage],
    text: str,
    request: str,
) -> str | None:
    if normalized(text) in normalized(request):
        return None
    keyword = next(
        (k for k in reversed(analyzed_keywords(messages)) if mentions(text, k)),
        None,
    )
    if keyword is not None:
        return find_problem(checks, reviews, text, keyword, request)
    if states_statistics(text):
        return checks.unsourced_statistics.format(request=request)
    return None
