# app/services/level.py
from app.models.user import User

# 定義每一段的「每升一級需要多少 EXP」
LEVEL_CONFIG = [
    (1, 10, 100),
    (11, 20, 200),
    (21, 30, 300),
    (31, 40, 500),
    (41, 50, 1000),
]

MAX_LEVEL = 50

def calc_level_from_exp(total_exp: int) -> int:
    level = 1
    remain = max(total_exp, 0)

    for start, end, need in LEVEL_CONFIG:
        for lv in range(start, end + 1):
            if remain >= need and level < MAX_LEVEL:
                remain -= need
                level += 1
            else:
                return level
    return level

def apply_exp_and_update(user: User, delta_exp: int) -> None:
    """
    給 user 加上 delta_exp，並依照總 EXP 重算 level
    """
    user.exp = max(0, (user.exp or 0) + delta_exp)
    user.level = calc_level_from_exp(user.exp)
