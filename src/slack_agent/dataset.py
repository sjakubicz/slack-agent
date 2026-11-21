import re
from functools import cached_property
from typing import cast

from datasets import Dataset, load_dataset

from slack_agent.config import DatasetConfig


class Reviews:
    def __init__(self, config: DatasetConfig):
        self.config = config

    @cached_property
    def rows(self) -> list[dict]:
        dataset = cast(
            Dataset,
            load_dataset(self.config.name, split=self.config.split),
        )
        return dataset.to_list()

    def find(self, keyword: str) -> list[dict]:
        pattern = re.compile(rf'\b{re.escape(keyword)}\b', re.IGNORECASE)
        return [
            r for r in self.rows if pattern.search(r[self.config.text_field])
        ]

    def stats(self, keyword: str) -> tuple[int, str]:
        hits = self.find(keyword)
        if not hits:
            return 0, '0%'
        positive = sum(r[self.config.label_field] for r in hits) / len(hits)
        return len(hits), f'{positive:.0%}'
