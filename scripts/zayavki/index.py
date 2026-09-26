# -*- coding: utf-8 -*-
"""
Приёмник заявок с сайта Анны Видуецкой.
Разворачивается как функция в Yandex Cloud Functions (Россия, 152-ФЗ).

Что делает:
  1. принимает POST с данными формы;
  2. сразу сохраняет заявку отдельным файлом — чтобы она не потерялась ни при каких условиях;
  3. дописывает строку в таблицу /Заявки/Заявки.csv на Яндекс Диске,
     её можно открыть в Яндекс Документах как обычную таблицу.

Переменные окружения функции:
  YANDEX_DISK_TOKEN — OAuth-токен Яндекс Диска (единственный секрет, в коде его нет)
  ALLOWED_ORIGIN    — адрес сайта, которому разрешено слать заявки
"""
import json
import os
import re
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

API = "https://cloud-api.yandex.net/v1/disk/resources"
TABLE = "/Заявки/Заявки.csv"
RAW_DIR = "/Заявки/сырые"
MSK = timezone(timedelta(hours=3))

COLUMNS = ["Дата", "Форма", "Имя", "Телефон", "Почта", "Контакт", "Комментарий", "Новости"]
FIELD_MAP = {"name": "Имя", "phone": "Телефон", "email": "Почта",
             "contact": "Контакт", "event": "Комментарий", "note": "Комментарий"}


def _req(url, method="GET", data=None, headers=None):
    r = urllib.request.Request(url, data=data, method=method, headers=headers or {})
    with urllib.request.urlopen(r, timeout=20) as resp:
        return resp.status, resp.read()


def _auth(token):
    return {"Authorization": "OAuth " + token}


def _ensure_dirs(token):
    for path in ("/Заявки", RAW_DIR):
        try:
            _req(API + "?path=" + urllib.parse.quote(path), "PUT", headers=_auth(token))
        except urllib.error.HTTPError as e:
            if e.code != 409:          # 409 — папка уже есть, это нормально
                raise


def _upload(token, path, body: bytes):
    url = API + "/upload?overwrite=true&path=" + urllib.parse.quote(path)
    _, raw = _req(url, headers=_auth(token))
    href = json.loads(raw)["href"]
    _req(href, "PUT", data=body)


def _download(token, path):
    """Возвращает содержимое файла или None, если его ещё нет."""
    url = API + "/download?path=" + urllib.parse.quote(path)
    try:
        _, raw = _req(url, headers=_auth(token))
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise
    href = json.loads(raw)["href"]
    _, body = _req(href)
    return body


def _csv_cell(v):
    v = re.sub(r"[\r\n]+", " ", str(v or "")).strip()
    if v[:1] in ("=", "+", "-", "@"):      # чтобы таблица не приняла текст за формулу
        v = "'" + v
    return '"' + v.replace('"', '""') + '"'


def _row(data):
    vals = {c: "" for c in COLUMNS}
    vals["Дата"] = datetime.now(MSK).strftime("%d.%m.%Y %H:%M")
    vals["Форма"] = data.get("form", "")
    vals["Новости"] = data.get("news", "")
    for key, col in FIELD_MAP.items():
        if data.get(key):
            vals[col] = (vals[col] + " / " if vals[col] else "") + data[key]
    return ";".join(_csv_cell(vals[c]) for c in COLUMNS)


def handler(event, context):
    origin = os.environ.get("ALLOWED_ORIGIN", "*")
    cors = {
        "Access-Control-Allow-Origin": origin,
        "Access-Control-Allow-Methods": "POST, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type",
    }
    if event.get("httpMethod") == "OPTIONS":
        return {"statusCode": 204, "headers": cors, "body": ""}
    if event.get("httpMethod") != "POST":
        return {"statusCode": 405, "headers": cors, "body": "only POST"}

    token = os.environ.get("YANDEX_DISK_TOKEN")
    if not token:
        return {"statusCode": 500, "headers": cors, "body": "no token"}

    try:
        data = json.loads(event.get("body") or "{}")
    except ValueError:
        return {"statusCode": 400, "headers": cors, "body": "bad json"}

    # отсекаем заведомый мусор
    data = {k: str(v)[:500] for k, v in data.items() if isinstance(k, str)}
    if not (data.get("name") or data.get("phone") or data.get("email") or data.get("contact")):
        return {"statusCode": 400, "headers": cors, "body": "empty"}

    stamp = datetime.now(MSK).strftime("%Y-%m-%d_%H-%M-%S")
    try:
        _ensure_dirs(token)
        # 1) страховка: заявка целиком, отдельным файлом
        _upload(token, f"{RAW_DIR}/{stamp}.json",
                json.dumps(data, ensure_ascii=False, indent=1).encode("utf-8"))
        # 2) строка в таблицу
        old = _download(token, TABLE)
        if old is None:
            head = "﻿" + ";".join(_csv_cell(c) for c in COLUMNS) + "\r\n"
            body = (head + _row(data) + "\r\n").encode("utf-8")
        else:
            body = old.rstrip(b"\r\n") + b"\r\n" + _row(data).encode("utf-8") + b"\r\n"
        _upload(token, TABLE, body)
    except Exception as e:                       # заявка уже сохранена в сырых
        return {"statusCode": 502, "headers": cors, "body": "disk error: %s" % e}

    return {"statusCode": 200, "headers": dict(cors, **{"Content-Type": "application/json"}),
            "body": json.dumps({"ok": True}, ensure_ascii=False)}
