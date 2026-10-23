"""Draw one equally weighted, currently available card."""

import random


def card_pool(results, tag=None):
    """None means all tags; empty string means explicitly untagged."""
    return [
        result["preset"] for result in results
        if result["status"] == "available"
        and (tag is None or result["preset"]["tag"] == tag)
    ]


def draw_card(results, tag=None):
    pool = card_pool(results, tag)
    if not pool:
        raise ValueError("当前范围内没有可抽的卡，请调整标签、切换门店或重试检查。")
    # Each invocation is independent: no weights, consumption or daily lock.
    return random.choice(pool)
