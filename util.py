#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# SPDX-FileCopyrightText: 2025 zzzz0317
#
# SPDX-License-Identifier: AGPL-3.0-only

import hashlib
import datetime
import urllib.request
import urllib.error


def calculate_file_hash(file_path):
    sha512_hash = hashlib.sha512()
    with open(file_path, "rb") as file:
        for chunk in iter(lambda: file.read(4096), b""):
            sha512_hash.update(chunk)
    return sha512_hash.hexdigest()


def get_time_str(dt=None, time_format="%Y-%m-%d %H:%M:%S"):
    if dt is None:
        dt = datetime.datetime.now()
    return dt.strftime(time_format)


def get_remote_content(url, encoding="utf-8"):
    try:
        response = urllib.request.urlopen(url)
        status_code = response.getcode()
        if encoding is None:
            content = response.read()
        else:
            content = response.read().decode(encoding)
        return status_code, content
    except urllib.error.HTTPError as e:
        return e.code, None
    except:
        return -1, None

def sort_dict_keys(obj):
    if isinstance(obj, dict):
        return {k: sort_dict_keys(v) for k, v in sorted(obj.items())}
    elif isinstance(obj, list):
        return [sort_dict_keys(item) for item in obj]
    else:
        return obj
