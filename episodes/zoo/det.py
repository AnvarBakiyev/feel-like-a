"""Общие основы эпизодов: генератор mulberry32 с подпотоками по FNV-1a, своё округление, календарь.
Всё переносится на JS один к одному. Взято из симулятора кофейни без изменений."""
import math


def rnd(x):
    return int(math.floor(x + 0.5))


def cents(x):
    return math.floor(x * 100 + 0.5) / 100


def fnv(s):
    h = 2166136261
    for ch in s.encode("utf-8"):
        h ^= ch
        h = (h * 16777619) & 0xFFFFFFFF
    return h


def imul(a, b):
    return (a * b) & 0xFFFFFFFF


class Rng:
    def __init__(self, seed_int):
        self.a = seed_int & 0xFFFFFFFF

    def u(self):
        self.a = (self.a + 0x6D2B79F5) & 0xFFFFFFFF
        t = self.a
        t = imul(t ^ (t >> 15), t | 1)
        t = t ^ ((t + imul(t ^ (t >> 7), t | 61)) & 0xFFFFFFFF)
        return ((t ^ (t >> 14)) & 0xFFFFFFFF) / 4294967296.0

    def int(self, lo, hi):  # включительно
        return lo + int(math.floor(self.u() * (hi - lo + 1)))

    def pick_w(self, weights):
        x = self.u() * sum(weights); acc = 0.0
        for i, w in enumerate(weights):
            acc += w
            if x < acc:
                return i
        return len(weights) - 1


def clamp(x, lo, hi):
    return lo if x < lo else hi if x > hi else x


def split_lr(n, shares):
    """Делит n на целые части по долям, наибольшие остатки, порядок стабилен."""
    tot = sum(shares)
    raw = [n * s / tot for s in shares]
    base = [int(math.floor(r)) for r in raw]
    rest = n - sum(base)
    order = sorted(range(len(shares)), key=lambda i: (-(raw[i] - base[i]), i))
    for i in order[:rest]:
        base[i] += 1
    return base


def days_in_month(y, m):
    return [31, 29 if (y % 4 == 0 and (y % 100 != 0 or y % 400 == 0)) else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][m - 1]


def weekday(y, m, d):  # пн=0, Сакамото
    t = [0, 3, 2, 5, 0, 3, 5, 1, 4, 6, 2, 4]
    yy = y - 1 if m < 3 else y
    w = (yy + yy // 4 - yy // 100 + yy // 400 + t[m - 1] + d) % 7  # вс=0
    return (w + 6) % 7
