"""Один вызов малой модели для всех эпизодов: Ollama на машине или OpenRouter в сети.

Зачем один файл: вызов был скопирован в четырёх местах (в нескольких эпизодах), и настройки в копиях уже начали расходиться. Теперь настройка одна.

Путь выбирается переменной окружения, по умолчанию Ollama, как во всех прежних замерах:

    CAFE_BACKEND=ollama        модель на машине (по умолчанию)
    CAFE_BACKEND=openrouter    та же модель в сети
    CAFE_BACKEND=azure         модель в своём ресурсе Azure (адрес в CAFE_AZ_URL)

Почему провайдер закреплён. На OpenRouter одну и ту же модель отдают пять компаний
с разным квантованием: fp4, fp8, bf16 и «неизвестно». Это разные веса, значит разные
ответы. Локально у нас Q4_K_M, поэтому по умолчанию берём fp4 (ближе всего) и запрещаем
подмену провайдера: иначе замер молча поедет на другую точность, и сравнивать месяцы
между собой станет нельзя.

    CAFE_OR_MODEL=qwen/qwen3.5-9b     что звать в сети
    CAFE_OR_PROVIDER=Darkbloom        кто считает; пусто = любой (для замеров не надо)

Ключ в коде и в репозитории не лежит: берётся из OPENROUTER_API_KEY или из файла
~/.config/extella/openrouter.key (первая строка). В журнал пишется путь и провайдер,
но не ключ.
"""
import json
import os
import time
import urllib.error
import urllib.request

OLLAMA_URL = os.environ.get("CAFE_OLLAMA_URL", "http://localhost:11434/api/chat")
OR_URL = "https://openrouter.ai/api/v1/chat/completions"
KEY_FILE = os.path.expanduser("~/.config/extella/openrouter.key")
# свой ресурс Azure: адрес в CAFE_AZ_URL, ключ одной строкой в файле или в AZURE_API_KEY
AZ_URL = os.environ.get("CAFE_AZ_URL", "")
AZ_KEY_FILE = os.path.expanduser("~/.config/extella/azure.key")

SEED = 7
TEMPERATURE = 0
NUM_CTX = 4096
TRIES = 5          # сеть иногда отвечает отказом; на месяц игры это 30 вызовов
PAUSE = 6.0        # 429 приходит от провайдера на весь аккаунт, пауза нужна заметная


def backend():
    return os.environ.get("CAFE_BACKEND", "ollama")


def model():
    if backend() == "openrouter":
        return os.environ.get("CAFE_OR_MODEL", "qwen/qwen3.5-9b")
    if backend() == "azure":
        return os.environ.get("CAFE_AZ_MODEL", "DeepSeek-V4-Flash")
    return os.environ.get("CAFE_MODEL", "qwen3.5:9b")


def provider():
    """Один провайдер или несколько через запятую.

    Несколько имеет смысл только с одинаковым квантованием: DeepInfra,Parasail — оба
    bf16. Это нужно, когда один провайдер отвечает 429 на три потока: лимит частоты у
    него на весь аккаунт.

    Раньше здесь было написано «подмена между ними ответы не меняет». Это неверно и
    стояло без замера. Повтор G9 от 14.11 (девять месяцев, та же настройка, 270 вызовов):
    решения совпали полностью только в 2 месяцах из 9, различия шли в уровне цен (около
    2 %) и в заказе выпечки на единицы, смена и выборы событий совпадали всегда. На
    деньгах это 0,05 % выручки и ранговая корреляция 1,000 — то есть ответы меняются, а
    итог нет. Подробности в закрытом журнале замеров, «Итог G9».
    """
    if backend() != "openrouter":
        return None
    p = os.environ.get("CAFE_OR_PROVIDER", "Darkbloom")
    return p or None


def providers():
    p = provider()
    return [x.strip() for x in p.split(",") if x.strip()] if p else []


def tag():
    """Строка для журнала: по ней видно, на чём считали месяц."""
    if backend() == "openrouter":
        return "openrouter:%s@%s" % (model(), provider() or "любой")
    if backend() == "azure":
        return "azure:%s" % model()
    return "ollama:%s" % model()


def key():
    k = os.environ.get("OPENROUTER_API_KEY")
    if k:
        return k.strip()
    if os.path.exists(KEY_FILE):
        with open(KEY_FILE, encoding="utf-8") as f:
            return f.readline().strip()
    raise RuntimeError(
        "Нет ключа OpenRouter. Положи его в %s или в OPENROUTER_API_KEY." % KEY_FILE)


def azure_key():
    k = os.environ.get("AZURE_API_KEY")
    if k:
        return k.strip()
    if os.path.exists(AZ_KEY_FILE):
        with open(AZ_KEY_FILE, encoding="utf-8") as f:
            return f.readline().strip()
    raise RuntimeError("Нет ключа Azure. Положи его одной строкой в %s или в AZURE_API_KEY." % AZ_KEY_FILE)


def _azure(messages, num_predict, timeout):
    """Ресурс extella-models, путь /openai/v1: тот же вид запроса, что у OpenAI."""
    body = {"model": model(), "messages": messages, "stream": False,
            "temperature": TEMPERATURE, "max_tokens": num_predict,
            "response_format": {"type": "json_object"}}
    head = {"Content-Type": "application/json", "Authorization": "Bearer %s" % azure_key(), "api-key": azure_key()}
    out = _post(AZ_URL, body, head, timeout)
    if "choices" not in out:
        raise RuntimeError("Azure не вернул ответ: %s" % json.dumps(out, ensure_ascii=False)[:300])
    m = out["choices"][0].get("message") or {}
    content = m.get("content")
    if not content:
        raise RuntimeError("Пустой ответ Azure; finish=%s" % out["choices"][0].get("finish_reason"))
    # часть моделей оборачивает JSON в ```json ... ```, хотя просили чистый JSON: снимаем обёртку
    c = content.strip()
    if c.startswith("```"):
        c = c.split("\n", 1)[1] if "\n" in c else c[3:]
        if c.rstrip().endswith("```"):
            c = c.rstrip()[:-3]
        content = c.strip()
    u = out.get("usage") or {}
    return (content, u.get("prompt_tokens"), u.get("completion_tokens"))


def _post(url, body, headers, timeout):
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def _ollama(messages, num_predict, timeout):
    body = {"model": model(), "messages": messages, "stream": False, "think": False, "format": "json",
            "options": {"temperature": TEMPERATURE, "seed": SEED, "num_ctx": NUM_CTX, "num_predict": num_predict}}
    out = _post(OLLAMA_URL, body, {"Content-Type": "application/json"}, timeout)
    return (out["message"]["content"], out.get("prompt_eval_count"), out.get("eval_count"))


def _openrouter(messages, num_predict, timeout):
    # reasoning отключаем намеренно: у qwen3.5 размышление включено по умолчанию, и тогда
    # ответ уходит в поле reasoning, а content приходит пустым. Локально мы ставим
    # think: false, значит и здесь надо так же, иначе сравнивать нечего.
    # Исключение: у части моделей (Claude Opus 5.5) размышление выключить нельзя, сеть отвечает 400.
    # Для них CAFE_OR_REASONING=low|medium|high, и max_tokens тогда должен покрывать и размышление.
    body = {"model": model(), "messages": messages, "stream": False,
            "temperature": TEMPERATURE, "seed": SEED, "max_tokens": num_predict,
            "reasoning": ({"effort": os.environ["CAFE_OR_REASONING"]} if os.environ.get("CAFE_OR_REASONING") else {"enabled": False}),
            "response_format": {"type": "json_object"}}
    ps = providers()
    if ps:
        # подмена разрешена только внутри названного списка: платформа не уведёт вызов
        # на провайдера с другим квантованием, а между равными переключится сама
        body["provider"] = {"order": ps, "allow_fallbacks": len(ps) > 1}
    head = {"Content-Type": "application/json", "Authorization": "Bearer %s" % key()}
    out = _post(OR_URL, body, head, timeout)
    if "choices" not in out:
        raise RuntimeError("OpenRouter не вернул ответ: %s" % json.dumps(out, ensure_ascii=False)[:300])
    m = out["choices"][0].get("message") or {}
    content = m.get("content")
    if not content:
        # пусто бывает, когда провайдер всё-таки размышлял: тогда текст лежит в reasoning
        raise RuntimeError("Пустой ответ от %s; finish=%s, reasoning=%s" % (
            out.get("provider"), out["choices"][0].get("finish_reason"),
            (m.get("reasoning") or "")[:200]))
    # часть моделей оборачивает JSON в ```json ... ```, хотя просили чистый JSON: снимаем обёртку
    c = content.strip()
    if c.startswith("```"):
        c = c.split("\n", 1)[1] if "\n" in c else c[3:]
        if c.rstrip().endswith("```"):
            c = c.rstrip()[:-3]
        content = c.strip()
    u = out.get("usage") or {}
    return (content, u.get("prompt_tokens"), u.get("completion_tokens"))


def ask(messages, num_predict=350, timeout=1500):
    """Один вызов модели. Возвращает словарь; поля content и секунды есть всегда."""
    fn = {"openrouter": _openrouter, "azure": _azure}.get(backend(), _ollama)
    last = None
    t0 = time.time()
    for i in range(TRIES):
        try:
            content, pin, pout = fn(messages, num_predict, timeout)
            return {"content": content, "seconds": round(time.time() - t0, 2),
                    "prompt_tokens": pin, "out_tokens": pout,
                    "backend": backend(), "model": model(), "provider": provider(),
                    "tries": i + 1}
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, RuntimeError) as e:
            last = e
            if isinstance(e, urllib.error.HTTPError) and e.code in (401, 402, 403):
                raise RuntimeError("OpenRouter отказал (%d): ключ или оплата." % e.code)
            if i + 1 < TRIES:
                # 429 значит «слишком часто»: ждём дольше обычного отказа сети
                hard = isinstance(e, urllib.error.HTTPError) and e.code == 429
                time.sleep(PAUSE * (i + 1) * (3 if hard else 1))
    raise RuntimeError("Модель не ответила %d раза: %s" % (TRIES, last))


if __name__ == "__main__":
    r = ask([{"role": "user", "content": 'Ответь ровно {"ok": 1} и ничего больше.'}], num_predict=20)
    print(tag())
    print("ответ:", r["content"].strip()[:120])
    print("секунд %.2f, вход %s, выход %s, попыток %d" % (r["seconds"], r["prompt_tokens"], r["out_tokens"], r["tries"]))
