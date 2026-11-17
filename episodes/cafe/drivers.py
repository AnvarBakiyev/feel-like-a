"""Simple players without AI. Each is f(obs, game) -> decision for the evening.

careful: orders by the forecast with a margin, shifts by the forecast, hires when short, answers cards by expected value.
plenty, thrifty, bare: the same calculation with one thing changed (more stock and staff; fewer people; order exactly the forecast).
naive: orders the same every day and keeps the starting shifts.
The rules live in policies.py; the page shows careful, plenty, thrifty and bare as rivals.
"""
import policies


def careful(obs, game=None):
    return policies.careful(obs)


def plenty(obs, game=None):
    return policies.plenty(obs)


def thrifty(obs, game=None):
    return policies.thrifty(obs)


def bare(obs, game=None):
    return policies.bare(obs)


def naive(obs, game=None):
    return policies.naive(obs)
