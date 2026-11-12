"""A simple operator without AI: pump what the forecast says, more at night when power is cheap."""


def simple(obs, g):
    f = obs["forecast_next_3h"][0] if obs["forecast_next_3h"] else 0
    want = f + (60 if obs["hour"] % 24 < 6 and obs["level"] < 300 else 0) - (obs["level"] - 200) * 0.2
    return {"pump": max(0.0, min(100.0, round(want, 1)))}
