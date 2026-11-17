"""One call of a language model: Ollama on your machine or OpenRouter. Used by extella/player.py and bench/noext.py.

CAFE_BACKEND=ollama (default) or openrouter. CAFE_MODEL (Ollama, default qwen3.5:9b), CAFE_OR_MODEL (OpenRouter,
default qwen/qwen3.5-9b), CAFE_OR_PROVIDER (comma list of OpenRouter providers; the published runs used
DeepInfra,Parasail,PrimeIntellect, all bf16), CAFE_OR_REASONING (low/medium/high for models that cannot switch
reasoning off). The key comes from OPENROUTER_API_KEY. Temperature 0, seed 7, JSON answers.
"""
import json, os, time, urllib.error, urllib.request

OLLAMA_URL = os.environ.get("CAFE_OLLAMA_URL", "http://localhost:11434/api/chat")
OR_URL = "https://openrouter.ai/api/v1/chat/completions"
SEED = 7
TEMPERATURE = 0
NUM_CTX = 4096
TRIES = 5
PAUSE = 6.0


def backend():
    return os.environ.get("CAFE_BACKEND", "ollama")


def model():
    if backend() == "openrouter":
        return os.environ.get("CAFE_OR_MODEL", "qwen/qwen3.5-9b")
    return os.environ.get("CAFE_MODEL", "qwen3.5:9b")


def providers():
    p = os.environ.get("CAFE_OR_PROVIDER", "") if backend() == "openrouter" else ""
    return [x.strip() for x in p.split(",") if x.strip()]


def tag():
    """Written into every run: what the month was computed on."""
    if backend() == "openrouter":
        return "openrouter:%s@%s" % (model(), ",".join(providers()) or "any")
    return "ollama:%s" % model()


def _post(url, body, headers, timeout):
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def _strip_fence(c):
    c = c.strip()
    if c.startswith("```"):
        c = c.split("\n", 1)[1] if "\n" in c else c[3:]
        if c.rstrip().endswith("```"):
            c = c.rstrip()[:-3]
    return c.strip()


def _ollama(messages, num_predict, timeout):
    body = {"model": model(), "messages": messages, "stream": False, "think": False, "format": "json",
            "options": {"temperature": TEMPERATURE, "seed": SEED, "num_ctx": NUM_CTX, "num_predict": num_predict}}
    out = _post(OLLAMA_URL, body, {"Content-Type": "application/json"}, timeout)
    return out["message"]["content"], out.get("prompt_eval_count"), out.get("eval_count")


def _openrouter(messages, num_predict, timeout):
    body = {"model": model(), "messages": messages, "stream": False, "temperature": TEMPERATURE, "seed": SEED, "max_tokens": num_predict,
            "reasoning": ({"effort": os.environ["CAFE_OR_REASONING"]} if os.environ.get("CAFE_OR_REASONING") else {"enabled": False}),
            "response_format": {"type": "json_object"}}
    ps = providers()
    if ps:
        body["provider"] = {"order": ps, "allow_fallbacks": len(ps) > 1}
    out = _post(OR_URL, body, {"Content-Type": "application/json", "Authorization": "Bearer %s" % os.environ["OPENROUTER_API_KEY"].strip()}, timeout)
    if "choices" not in out:
        raise RuntimeError("no answer: %s" % json.dumps(out, ensure_ascii=False)[:300])
    content = (out["choices"][0].get("message") or {}).get("content")
    if not content:
        raise RuntimeError("empty answer, finish=%s" % out["choices"][0].get("finish_reason"))
    u = out.get("usage") or {}
    return _strip_fence(content), u.get("prompt_tokens"), u.get("completion_tokens")


def ask(messages, num_predict=350, timeout=1500):
    fn = _openrouter if backend() == "openrouter" else _ollama
    last = None
    t0 = time.time()
    for i in range(TRIES):
        try:
            content, pin, pout = fn(messages, num_predict, timeout)
            return {"content": content, "seconds": round(time.time() - t0, 2), "prompt_tokens": pin, "out_tokens": pout,
                    "backend": backend(), "model": model(), "tries": i + 1}
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, RuntimeError) as e:
            last = e
            if isinstance(e, urllib.error.HTTPError) and e.code in (401, 402, 403):
                raise RuntimeError("refused (%d): key or billing" % e.code)
            if i + 1 < TRIES:
                hard = isinstance(e, urllib.error.HTTPError) and e.code == 429
                time.sleep(PAUSE * (i + 1) * (3 if hard else 1))
    raise RuntimeError("model did not answer %d times: %s" % (TRIES, last))
