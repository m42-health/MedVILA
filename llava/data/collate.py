from dataclasses import dataclass
from typing import Any, Dict, Sequence

import torch
from transformers import PreTrainedTokenizer

from llava.constants import IGNORE_INDEX
from llava.utils.logging import logger

__all__ = ["DataCollator"]


@dataclass
class DataCollator:
    tokenizer: PreTrainedTokenizer

    def __init__(self, tokenizer: PreTrainedTokenizer):
        super().__init__()
        self.tokenizer = tokenizer

    def __call__(self, instances: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
        # Gather everything from the batch
        # breakpoint()
        input_ids, labels, media = [], [], {name: [] for name in self.tokenizer.media_tokens}
        index_ids = []
        for instance in instances:
            if isinstance(instance["input_ids"], torch.Tensor):
                index_ids.append(instance["index"])
                input_ids.append(instance["input_ids"])
                labels.append(instance["labels"])
                for name in media:
                    objs = instance.get(name)
                    objs = objs if objs is not None else []
                    media[name].append([obj for obj in objs])
            else:
                index_ids.append(instance["index"])
                input_ids.extend(instance["input_ids"])
                labels.extend(instance["labels"])
                for name in media:
                    objs = instance.get(name)
                    objs = objs if objs is not None else []
                    media[name].extend(objs)

        batch_size = len(input_ids)

        # Batchify the inputs
        input_ids = torch.nn.utils.rnn.pad_sequence(
            input_ids,
            batch_first=True,
            padding_value=self.tokenizer.pad_token_id,
        )
        labels = torch.nn.utils.rnn.pad_sequence(
            labels,
            batch_first=True,
            padding_value=IGNORE_INDEX,
        )
        input_ids = input_ids[:, : self.tokenizer.model_max_length]
        labels = labels[:, : self.tokenizer.model_max_length]
        attention_mask = input_ids.ne(self.tokenizer.pad_token_id)

        # Truncate media objects if necessary
        for name in media:
            objects = []
            for k in range(batch_size):
                objects.extend(media[name][k])
            media[name] = objects

        block_sizes = []
        for instance in instances:
            block_sizes.extend(instance.get("block_sizes", [None]))

        return {
            "input_ids": input_ids,
            "media": media,
            "media_config": {"image": {"block_sizes": block_sizes}, "video": {}},
            "labels": labels,
            "attention_mask": attention_mask,
            "indexes": index_ids,
        }
