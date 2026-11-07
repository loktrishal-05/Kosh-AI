from decimal import Decimal, ROUND_HALF_UP

D = Decimal
TWO = D("0.01")


def d(x) -> Decimal:
    # str() first so floats like 0.1 do not leak binary noise into Decimal
    return x if isinstance(x, Decimal) else D(str(x))


def r2(x) -> Decimal:
    return d(x).quantize(TWO, rounding=ROUND_HALF_UP)


def r0(x) -> Decimal:
    return d(x).quantize(D("1"), rounding=ROUND_HALF_UP)
