\
\
\
\
\
   

from __future__ import annotations

import random
from collections.abc import Sequence


MIN_DIGITS = 3
MAX_DIGITS = 8


def normalize_digit_count(value: object, default: int = 4) -> int:
                                                                        

                                                                           
    try:
        count = int(value)
    except (TypeError, ValueError):
        return default
    return count if MIN_DIGITS <= count <= MAX_DIGITS else default


def create_to_solve_task(count: int | str) -> list[int]:
                                                        

                                                                    
    digit_count = normalize_digit_count(count)
    return random.sample(range(10), digit_count)


def validate_guess(guess: str, count: int) -> tuple[bool, str]:
                                                                           

                                                                             
    if len(guess) != count:
        return False, f"{count}桁の数字を入力してください。"
    if not guess.isascii() or not guess.isdigit():
        return False, "半角数字だけを入力してください。"
    if len(set(guess)) != count:
        return False, "同じ数字は1回しか使えません。"
    return True, ""


def evaluate_guess(secret: Sequence[int], guess: Sequence[int] | str) -> tuple[int, int]:
                                                                

                                                                             
    guess_digits = [int(value) for value in guess]
    secret_digits = [int(value) for value in secret]
    hits = sum(left == right for left, right in zip(secret_digits, guess_digits))
    blows = sum(value in secret_digits for value in guess_digits) - hits
    return hits, blows


def calculate_score(digit_count: int, attempts: int, elapsed_seconds: float) -> int:
                                                                     

                                                                           
    attempts = max(1, attempts)
    elapsed_seconds = max(0.0, elapsed_seconds)
    base = digit_count * 10_000
    attempt_penalty = (attempts - 1) * 700
    time_penalty = int(elapsed_seconds * 12)
    return max(100, base - attempt_penalty - time_penalty)
    
