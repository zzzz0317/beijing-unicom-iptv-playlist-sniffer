#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# SPDX-FileCopyrightText: 2025 zzzz0317
#
# SPDX-License-Identifier: AGPL-3.0-only

import os
import sys
import json
import datetime
import pytz
import xml.etree.ElementTree as ET
import gzip

default_timezone = pytz.timezone("Asia/Shanghai")
pytz.timezone.default = default_timezone

from util import get_time_str, get_remote_content

DIR_SCRIPT = os.path.dirname(os.path.realpath(sys.argv[0]))
DIR_RUNNING = os.getcwd()

CONFIG_PATH = os.path.join(DIR_SCRIPT, "config.json")
if os.path.exists(CONFIG_PATH):
    with open(CONFIG_PATH, "r", encoding="utf-8") as f_config_json:
        config = json.load(f_config_json)
else:
    config = {}

config_epg_server_url = config.get("epg_server_url", "http://210.13.21.3")
config_epg_save_path = config.get("epg_save_path", "epg.xml")
config_epg_offset_start = config.get("epg_offset_start", -1)
config_epg_offset_end = config.get("epg_offset_end", 8)
config_epg_cache = config.get("epg_cache", False)
config_epg_cache_path = config.get("epg_cache_path", "epg_cache")
config_epg_cache_offset = config.get("epg_cache_offset", -2)
config_epg_cache_external = config.get("epg_cache_external", False)
config_epg_cache_external_path = config.get("epg_cache_external_path", "epg_cache_external")
config_epg_cache_external_offset = config.get("epg_cache_external_offset", 0)
config_epg_internal = config.get("epg_internal", [])
config_epg_external = config.get("epg_external", [])
config_playlist_raw_path = config.get("playlist_raw_path", config.get("sniff_save_path", "playlist_raw.json"))

datetime_now = datetime.datetime.now()

print("config_epg_server_url:", config_epg_server_url)
print("config_epg_save_path:", config_epg_save_path)
print("config_epg_offset_start:", config_epg_offset_start)
print("config_epg_offset_end:", config_epg_offset_end)
print("config_epg_cache:", config_epg_cache)
print("config_epg_cache_path:", config_epg_cache_path)
print("config_epg_cache_offset:", config_epg_cache_offset)
print("config_epg_cache_external:", config_epg_cache_external)
print("config_epg_cache_external_path:", config_epg_cache_external_path)
print("config_epg_cache_external_offset:", config_epg_cache_external_offset)
print("config_epg_internal:", config_epg_internal)
print("config_epg_external:", config_epg_external)
print("config_playlist_raw_path:", config_playlist_raw_path)
print("datetime_now:", datetime_now)

if not os.path.exists(config_playlist_raw_path):
    print("raw playlist file not exist!")
    sys.exit(1)

with open(config_playlist_raw_path, "r", encoding="utf-8") as f_sniff_save:
    raw_channel_list = json.load(f_sniff_save)

channel_codes = []
for c in raw_channel_list:
    channel_codes.append(c.get("channelID"))

channel_codes = list(set(channel_codes))
print("channel_codes count:", len(channel_codes))

channel_list = {}
channel_with_epg_list = []
programme_list = []

for channel_code in channel_codes:
    for i in range(config_epg_offset_start, config_epg_offset_end):
        datestr = datetime_now + datetime.timedelta(days=i)
        datestr = get_time_str(datestr, "%Y%m%d")
        filename = f"{channel_code}_{datestr}.json"
        day_epg_data = None
        if config_epg_cache and i <= config_epg_cache_offset:
            cache_filename = os.path.join(config_epg_cache_path, filename)
            if os.path.exists(cache_filename):
                with open(cache_filename, "r", encoding="utf-8") as f_cache:
                    try:
                        day_epg_data = json.load(f_cache)
                        print("epg cache hit:", cache_filename)
                    except Exception as e:
                        print("epg cache load error:", cache_filename, e)
                        day_epg_data = None
        if day_epg_data is None:
            url = f"{config_epg_server_url}/schedules/{filename}"
            status_code, day_epg_data = get_remote_content(url)
            if status_code == 404:
                # print("send_schedules_request return 404:", url)
                cache_filename = os.path.join(config_epg_cache_path, filename)
                if os.path.exists(cache_filename):
                    with open(cache_filename, "r", encoding="utf-8") as f_cache:
                        try:
                            day_epg_data = f_cache.read().encode("utf-8")
                            print("send_schedules_request return 404, but epg cache hit:", cache_filename)
                        except Exception as e:
                            print("send_schedules_request return 404, and epg cache load error:", cache_filename, e)
                            continue
                else:
                    print("send_schedules_request return 404, and no epg cache:", url)
                    if i <= 2:
                        continue
                    break
            elif status_code != 200:
                print(f"send_schedules_request return {status_code}:", url)
                continue
            print(f"send_schedules_request ok:", url)
            day_epg_data = json.loads(day_epg_data)
            if config_epg_cache:
                if not os.path.exists(config_epg_cache_path):
                    os.makedirs(config_epg_cache_path)
                cache_filename = os.path.join(config_epg_cache_path, filename)
                with open(cache_filename, "w", encoding="utf-8") as f_cache:
                    f_cache.write(json.dumps(day_epg_data, ensure_ascii=False, indent=2))
                    print("epg cache save:", cache_filename)
        channel_info = day_epg_data.get("channel", {})
        channel_num = channel_info.get("channelnum", "9999")
        if channel_code not in channel_list.keys():
            channel_name = channel_info.get("title", f"未定义频道-{channel_code}")
            channel_list[channel_code] = {"channel_num": channel_num, "channel_name": channel_name}
        schedules = day_epg_data.get("schedules")
        for schedule in schedules:
            source_time_format = "%Y-%m-%d %H:%M:%S"
            target_time_format = "%Y%m%d%H%M%S"
            start_time = datetime.datetime.strptime(
                schedule.get(
                    "starttime", schedule.get("showStarttime", "1970-01-01 08:00:00")
                ), source_time_format)
            end_time = datetime.datetime.strptime(schedule.get("endtime", start_time), source_time_format)
            if channel_num not in channel_with_epg_list:
                channel_with_epg_list.append(channel_num)
            programme_list.append({
                "channel": channel_num,
                "start": get_time_str(start_time, target_time_format) + " +0800",
                "stop": get_time_str(end_time, target_time_format) + " +0800",
                "title": schedule.get("title", "无节目名称")
            })

print("channel_count:", len(channel_list.keys()))
# print(json.dumps(channel_list, ensure_ascii=False, indent=2))
print("channel_with_epg_list:", len(channel_with_epg_list))
# print(json.dumps(channel_with_epg_list, ensure_ascii=False, indent=2))
print("programme_count:", len(programme_list))
# print(json.dumps(programme_list, ensure_ascii=False, indent=2))

print("Processing internal EPG mapping...")
from_id_dict = {}
new_programmes = []

for channel in config_epg_internal:
    tvg_from_id = channel["tvg_from_id"]
    tvg_to_id = channel["tvg_to_id"]
    from_raw_channel = next((ch for ch in raw_channel_list if ch.get("userChannelID") == tvg_from_id), None)
    to_raw_channel = next((ch for ch in raw_channel_list if ch.get("userChannelID") == tvg_to_id), None)
    if from_raw_channel is None:
        print(f"from channel {tvg_from_id} ({channel['tvg_from']}) not found, skip")
        continue
    if from_raw_channel.get("channelName") != channel["tvg_from"]:
        print(f"from channel {tvg_from_id}'s channelName not match {channel['tvg_from']}, skip")
        continue
    if to_raw_channel is None:
        print(f"to channel {tvg_to_id} ({channel['tvg_to']}) not found, skip")
        continue
    if to_raw_channel.get("channelName") != channel["tvg_to"]:
        print(f"to channel {tvg_to_id}'s channelName not match {channel['tvg_to']}, skip")
        continue
    if tvg_from_id not in from_id_dict:
        from_id_dict[tvg_from_id] = []
    from_id_dict[tvg_from_id].append(tvg_to_id)
    print(f"add internal epg mapping: from channel {tvg_from_id} ({channel['tvg_from']}) to channel {tvg_to_id} ({channel['tvg_to']})")
    # 清理目标频道已有的 EPG 数据
    if tvg_to_id in channel_with_epg_list:
        programme_list = [p for p in programme_list if p["channel"] != str(tvg_to_id)]
        print(f"channel {tvg_to_id} ({channel['tvg_to']}) in channel_with_epg_list, clear its programme in programme_list for rewrite")
    # 添加频道到频道列表
    if not any(ch.get("channel_num") == str(tvg_to_id) for ch in channel_list.values()):
        channel_list[tvg_to_id] = {"channel_num": str(tvg_to_id), "channel_name": channel["tvg_to"]}
        print(f"channel {tvg_to_id} ({channel['tvg_to']}) not in channel_list, add it for internal epg")
    # 如果 tvg_to_id 不在 channel_with_epg_list 中，则添加到 channel_with_epg_list 中，表示它已经有 EPG 数据了（虽然还没有，但后面会添加）
    if tvg_to_id not in channel_with_epg_list:
        channel_with_epg_list.append(tvg_to_id)

for programme in programme_list:
    channel = int(programme.get('channel'))
    if channel not in from_id_dict:
        continue
    title = programme.get('title')
    time_start = programme.get('start')
    time_stop = programme.get('stop')
    for programme_tvg_to_id in from_id_dict[channel]:
        # print(f"map channel {channel} to {programme_tvg_to_id} for programme {title} ({time_start} - {time_stop})")
        new_programmes.append({
            "channel": str(programme_tvg_to_id),
            "start": time_start,
            "stop": time_stop,
            "title": title
        })

# 将新节目添加到 programme_list
programme_list.extend(new_programmes)
print(f"copied {len(new_programmes)} new programme entries")
print("channel_count after internal epg:", len(channel_list.keys()))
# print(json.dumps(channel_list, ensure_ascii=False, indent=2))
print("programme_count after internal epg:", len(programme_list))
# print(json.dumps(programme_list, ensure_ascii=False, indent=2))

print("Processing external EPG mapping...")

for epg in config_epg_external:
    url = epg["url"]
    epg_name = epg["name"]
    print(f"Get {epg_name} EPG data from {url}")
    status_code, ext_epg_data = get_remote_content(url, encoding=None)
    if status_code != 200:
        print(f"Get EPG data from {url} failed ({status_code})")
        continue
    if url.endswith(".gz"):
        print("EPG is gzip compressed")
        ext_epg_data = gzip.decompress(ext_epg_data)
    ext_epg_data = ext_epg_data.decode("utf-8")
    ext_epg_data = ET.fromstring(ext_epg_data)
    ext_epg_cache_data = {}
    ext_id_dict = {}
    for channel in epg["channel"]:
        tvg_id_ext = channel["tvg_id_ext"]
        tvg_id_iptv = channel["tvg_id_iptv"]
        raw_channel = next((channel for channel in raw_channel_list if channel.get("userChannelID") == tvg_id_iptv), None)
        if raw_channel == None:
            print(f"channel {tvg_id_iptv} ({channel['tvg_name']}) not found, skip")
            continue
        if raw_channel.get("channelName") != channel["tvg_name"]:
            print(f"channel {tvg_id_iptv} ({channel['tvg_name']})'s channelName not match {channel['tvg_name']}, skip")
            continue
        ext_programmes = ext_epg_data.findall('programme')
        ext_has_epg = any(p.get('channel') == str(tvg_id_ext) for p in ext_programmes)
        if ext_has_epg:
            if channel["tvg_id_ext"] not in ext_id_dict:
                ext_id_dict[channel["tvg_id_ext"]] = []
            ext_id_dict[channel["tvg_id_ext"]].append(tvg_id_iptv)
            print(f"add external epg mapping: from external {tvg_id_ext} to channel {tvg_id_iptv} ({channel['tvg_name']})")
            if tvg_id_iptv in channel_with_epg_list:
                # 清除 programme_list 中 tvg_id_iptv 已有的 EPG 数据
                programme_list = [p for p in programme_list if p["channel"] != str(tvg_id_iptv)]
                print(f"channel {tvg_id_iptv} ({channel['tvg_name']}) in channel_with_epg_list, clear its programme in programme_list for rewrite")
            if [idkey for idkey, channel in channel_list.items() if channel.get("channel_num") == str(tvg_id_iptv)] == []:
                channel_list[tvg_id_iptv] = {"channel_num": str(tvg_id_iptv), "channel_name": channel["tvg_name"]}
                print(f"channel {tvg_id_iptv} ({channel['tvg_name']}) not in channel_list, add it for external epg")
            # 如果 tvg_id_iptv 不在 channel_with_epg_list 中，则添加到 channel_with_epg_list 中，表示它已经有 EPG 数据了（虽然还没有，但后面会添加）
            if tvg_id_iptv not in channel_with_epg_list:
                channel_with_epg_list.append(tvg_id_iptv)

    ext_id_list = list(ext_id_dict.keys())
    # print(f"ext_id_dict: {ext_id_dict}")

    for epg_tvg_id_ext in ext_id_dict:
        for epg_tvg_id_iptv in ext_id_dict[epg_tvg_id_ext]:
            channel_code = epg_tvg_id_iptv
            for i in range(config_epg_offset_start, epg.get("cache_offset", config_epg_cache_external_offset)):
                datestr = datetime_now + datetime.timedelta(days=i)
                datestr = get_time_str(datestr, "%Y%m%d")
                filename = f"{channel_code}_{datestr}_{epg_name}.json"
                if config_epg_cache_external:
                    cache_filename = os.path.join(config_epg_cache_external_path, filename)
                    if os.path.exists(cache_filename):
                        with open(cache_filename, "r", encoding="utf-8") as f_cache:
                            try:
                                day_epg_data = json.load(f_cache)
                                print("epg cache external hit:", cache_filename)
                                for programme in day_epg_data:
                                    programme_list.append({
                                        "channel": programme["channel"],
                                        "start": programme["start"],
                                        "stop": programme["stop"],
                                        "title": programme["title"]
                                    })
                            except Exception as e:
                                print("epg cache external load error:", cache_filename, e)

    for programme in ext_epg_data.findall('programme'):
        channel = int(programme.get('channel'))
        if channel not in ext_id_list:
            # print(f"channel {channel} not in ext_id_list")
            continue
        titles = programme.findall('title')
        time_start = programme.get('start')
        time_stop = programme.get('stop')
        zh_title = next((title.text for title in titles if title.get('lang') == 'zh'), None)
        if zh_title is None and titles:
            zh_title = titles[0].text
        if zh_title is not None and time_start is not None and time_stop is not None:
            for tvg_id_iptv in ext_id_dict[channel]:
                # print(f"map channel {channel} to {ext_id_dict[channel]} for programme {zh_title} ({time_start} - {time_stop})")
                programme_list.append({
                    "channel": str(tvg_id_iptv),
                    "start": time_start,
                    "stop": time_stop,
                    "title": zh_title
                })
                date = time_start[0:8]
                ext_epg_cache_data[tvg_id_iptv] = ext_epg_cache_data.get(tvg_id_iptv, {})
                ext_epg_cache_data[tvg_id_iptv][date] = ext_epg_cache_data[tvg_id_iptv].get(date, [])
                ext_epg_cache_data[tvg_id_iptv][date].append({
                    "channel": str(tvg_id_iptv),
                    "start": time_start,
                    "stop": time_stop,
                    "title": zh_title
                })

    for ext_epg_cache_data_channel in ext_epg_cache_data:
        for ext_epg_cache_data_date in ext_epg_cache_data[ext_epg_cache_data_channel]:
            filename = f"{ext_epg_cache_data_channel}_{ext_epg_cache_data_date}_{epg_name}.json"
            if config_epg_cache_external:
                if not os.path.exists(config_epg_cache_external_path):
                    os.makedirs(config_epg_cache_external_path)
                cache_filename = os.path.join(config_epg_cache_external_path, filename)
                with open(cache_filename, "w", encoding="utf-8") as f_cache:
                    f_cache.write(json.dumps(ext_epg_cache_data[ext_epg_cache_data_channel][ext_epg_cache_data_date], ensure_ascii=False, indent=2))
                    print("epg cache external save:", cache_filename)

print("channel_count after external epg:", len(channel_list.keys()))
# print(json.dumps(channel_list, ensure_ascii=False, indent=2))
print("programme_count after external epg:", len(programme_list))
# print(json.dumps(programme_list, ensure_ascii=False, indent=2))

root = ET.Element(
    "tv",
    attrib={
        "generator-info-name": "beijing-unicom-iptv-playlist-sniffer",
        "generator-info-url": "https://github.com/zzzz0317/beijing-unicom-iptv-playlist-sniffer"
    }
)

channel_list = dict(sorted(channel_list.items(), key=lambda x: int(x[1]["channel_num"])))
programme_list = sorted(programme_list, key=lambda x: (int(x["channel"]), x["start"]))

print("Generating EPG channel list")
for k in channel_list:
    channel = channel_list[k]
    elem_channel = ET.SubElement(root, "channel", attrib={"id": channel["channel_num"]})
    display_name = ET.SubElement(elem_channel, "display-name", attrib={"lang": "zh"})
    display_name.text = channel["channel_name"]

print("Generating EPG programme list")
for programme in programme_list:
    elem_programme = ET.SubElement(
        root,
        "programme",
        attrib={
            "start": programme["start"],
            "stop": programme["stop"],
            "channel": programme["channel"]
        }
    )
    title = ET.SubElement(elem_programme, "title", attrib={"lang": "zh"})
    title.text = programme["title"]
    desc1 = ET.SubElement(elem_programme, "desc", attrib={"lang": "zh"})

print("Writting EPG file to:", config_epg_save_path)
tree = ET.ElementTree(root)
tree.write(
    config_epg_save_path,
    encoding="UTF-8",
    xml_declaration=True
)
