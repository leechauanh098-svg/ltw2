MAX_LEVEL_GAP = 1


def is_compatible(me: dict, other: dict) -> bool:
    """Ghép được khi cùng lộ trình, lệch trình độ tối đa 1 bậc và người kia đang sẵn sàng."""
    return (
        me["roadmap_id"] == other["roadmap_id"]
        and abs(me["level"] - other["level"]) <= MAX_LEVEL_GAP
        and bool(other["available"])
    )
