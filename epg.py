import os
import sys
import json
import datetime
import pytz
import xml.etree.ElementTree as ET

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
config_sniff_save_path = config.get("sniff_save_path", "playlist_raw.json")

datetime_now = datetime.datetime.now()

print("config_epg_server_url:", config_epg_server_url)
print("config_epg_save_path:", config_epg_save_path)
print("config_sniff_save_path:", config_sniff_save_path)
print("datetime_now:", datetime_now)

if not os.path.exists(config_sniff_save_path):
    print("raw playlist file not exist!")
    sys.exit(1)

with open(config_sniff_save_path, "r", encoding="utf-8") as f_sniff_save:
    raw_channel_list = json.load(f_sniff_save)

channel_codes = []
for c in raw_channel_list:
    channel_codes.append(c.get("channelID"))

channel_codes = list(set(channel_codes))
print("channel_codes count:", len(channel_codes))

channel_list = {}
programme_list = []

for channel_code in channel_codes:
    for i in range(0, 8):
        datestr = datetime_now + datetime.timedelta(days=i)
        datestr = get_time_str(datestr, "%Y%m%d")
        url = f"{config_epg_server_url}/schedules/{channel_code}_{datestr}.json"
        status_code, day_epg_data = get_remote_content(url)
        if status_code == 404:
            print("send_schedules_request return 404:", url)
            break
        elif status_code != 200:
            print(f"send_schedules_request return {status_code}:", url)
            continue
        print(f"send_schedules_request ok:", url)
        day_epg_data = json.loads(day_epg_data)
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
            programme_list.append({
                "channel": channel_num,
                "start": get_time_str(start_time, target_time_format) + " +0800",
                "stop": get_time_str(end_time, target_time_format) + " +0800",
                "title": schedule.get("title", "无节目名称")
            })

print("channel_count:", len(channel_list.keys()))
# print(json.dumps(channel_list, ensure_ascii=False, indent=2))
print("programme_count:", len(programme_list))
# print(json.dumps(programme_list, ensure_ascii=False, indent=2))

root = ET.Element(
    "tv",
    attrib={
        "generator-info-name": "beijing-unicom-iptv-playlist-sniffer",
        "generator-info-url": "https://github.com/zzzz0317/beijing-unicom-iptv-playlist-sniffer"
    }
)

for k in channel_list:
    channel = channel_list[k]
    elem_channel = ET.SubElement(root, "channel", attrib={"id": channel["channel_num"]})
    display_name = ET.SubElement(elem_channel, "display-name", attrib={"lang": "zh"})
    display_name.text = channel["channel_name"]

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

tree = ET.ElementTree(root)
tree.write(
    config_epg_save_path,
    encoding="UTF-8",
    xml_declaration=True
)
