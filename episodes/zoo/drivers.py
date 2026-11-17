"""Simple players without AI (the logic lives in policies.py).

full: the careful program, the "Python program" rival on the page: care minimum, feed stock up to the next
      delivery plus a buffer, two public feedings, vet twice, base ticket price.
naive: staffs the minimum, thaws the exact ration, same order every time, default answers to event cards.
"""
import policies


def full(obs, game):
    return policies.careful(obs)


def naive(obs, game):
    return policies.naive(obs)
