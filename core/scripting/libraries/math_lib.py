"""math 内置库。"""

import math
import random


def build_math_lib(interp=None):
    return {
        "pi": math.pi,
        "e": math.e,

        "sin": math.sin,
        "cos": math.cos,
        "tan": math.tan,

        "arcsin": math.asin,
        "arccos": math.acos,
        "arctan": math.atan,

        "asin": math.asin,
        "acos": math.acos,
        "atan": math.atan,

        "sinh": math.sinh,
        "cosh": math.cosh,
        "tanh": math.tanh,

        "sqrt": math.sqrt,
        "abs": abs,

        "ln": math.log,
        "log": math.log10,
        "exp": math.exp,

        "cot": lambda x: 1.0 / math.tan(x),
        "sec": lambda x: 1.0 / math.cos(x),
        "csc": lambda x: 1.0 / math.sin(x),

        "min": min,
        "max": max,

        "floor": math.floor,
        "ceil": math.ceil,
        "round": lambda x: float(round(x)),

        "random": random.random,
        
"floor": math.floor,
"ceil": math.ceil,
"round": lambda x: float(round(x)),
"sign": lambda x: (x > 0) - (x < 0),
"min": min,
"max": max,
"sec": lambda x: 1.0 / math.cos(x),
"csc": lambda x: 1.0 / math.sin(x),
"cot": lambda x: 1.0 / math.tan(x),
    }