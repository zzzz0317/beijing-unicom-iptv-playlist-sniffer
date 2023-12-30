import os
import sys
import json
import time
import urllib.request
import traceback

from util import calculate_file_hash

DIR_SCRIPT = os.path.dirname(os.path.realpath(sys.argv[0]))
DIR_RUNNING = os.getcwd()

CONFIG_PATH = os.path.join(DIR_SCRIPT, "config.json")
if os.path.exists(CONFIG_PATH):
    with open(CONFIG_PATH, "r", encoding="utf-8") as f_config_json:
        config = json.load(f_config_json)
else:
    config = {}


config_playlist_watcher_no_exit = config.get("playlist_watcher_no_exit", False)
config_playlist_watcher_interval = config.get("playlist_watcher_interval", 5)
config_playlist_epg_url = config.get("playlist_epg_url", "")
config_playlist_tvg_img_url = config.get("playlist_tvg_img_url", "")
config_playlist_udpxy_url = config.get("playlist_udpxy_url", "http://127.0.0.1:8080/rtp/")
config_playlist_save_path = config.get("playlist_save_path", "playlist.m3u")
config_playlist_mc_save_path = config.get("playlist_mc_save_path", "playlist_mc.m3u")
config_sniff_save_path = config.get("sniff_save_path", "playlist_raw.json")


epg_disable = False
if config_playlist_epg_url == "":
    epg_disable = True

tvg_mapper = {}
if not epg_disable:
    tvg_mapper_path = os.path.join(DIR_SCRIPT, "tvg_mapper.json")
    if os.path.exists(tvg_mapper_path):
        with open(tvg_mapper_path, "r", encoding="utf-8") as f_tvg_mapper:
            tvg_mapper = json.load(f_tvg_mapper)

print("config_playlist_watcher_no_exit:", config_playlist_watcher_no_exit)
print("config_playlist_watcher_interval:", config_playlist_watcher_interval)
print("config_playlist_epg_url:", config_playlist_epg_url, "epg_disable:", epg_disable)
print("config_playlist_udpxy_url:", config_playlist_udpxy_url)
print("config_playlist_save_path:", config_playlist_save_path)
print("config_playlist_mc_save_path:", config_playlist_mc_save_path)
print("config_sniff_save_path:", config_sniff_save_path)

need_update_playlist = True
raw_playlist_hash_path = os.path.join(DIR_SCRIPT, "last_raw_playlist_hash.txt")
if os.path.exists(raw_playlist_hash_path):
    with open(raw_playlist_hash_path, "r") as f_raw_playlist_hash:
        last_raw_playlist_hash = f_raw_playlist_hash.read()
elif os.path.exists(config_sniff_save_path):
    last_raw_playlist_hash = calculate_file_hash(config_sniff_save_path)
else:
    last_raw_playlist_hash = "-"

while True:
    if not os.path.exists(config_sniff_save_path):
        print("RAW playlist not found in", config_sniff_save_path)
        if not config_playlist_watcher_no_exit:
            sys.exit(1)
        continue
    if not need_update_playlist:
        raw_playlist_hash = calculate_file_hash(config_sniff_save_path)
        if raw_playlist_hash != last_raw_playlist_hash:
            need_update_playlist = True
            last_raw_playlist_hash = raw_playlist_hash
            with open(raw_playlist_hash_path, "w") as f_raw_playlist_hash:
                f_raw_playlist_hash.write(last_raw_playlist_hash)
    if need_update_playlist:
        print("need_update_playlist is True, time to update playlist!")
        with open(config_sniff_save_path, "r", encoding="utf-8") as f_sniff_save:
            channel_list = json.load(f_sniff_save)
        channel_list = sorted(channel_list, key = lambda i: i['userChannelID'])
        # print(channel_list)
        zz_playlist = []
        for channel in channel_list:
            channel_id = channel["userChannelID"]
            channel_url = channel["channelURL"]
            if channel_url.startswith("igmp://"):
                igmp_ip_port = channel_url[7:]
            else:
                print(f"Channel {channel_id} URL is not start from igmp://, ignored")
                continue
            channel_name = channel["channelName"]
            zz_playlist.append({"channel_id": channel_id, "igmp_ip_port": igmp_ip_port, "channel_name": channel_name})
        need_update_playlist = False
        # print(zz_playlist)
        m3u_header = "#EXTM3U name=\"bj-unicom-iptv\"" if epg_disable else "#EXTM3U name=\"bj-unicom-iptv\" x-tvg-url=\"{config_playlist_epg_url}\""
        line_unicast = [m3u_header]
        line_multicast = [m3u_header]
        for channel in zz_playlist:
            tvg_mapper_channel = tvg_mapper.get(channel["channel_name"], {})
            info_line = f'#EXTINF:-1 channel-number="{channel["channel_id"]}"'
            if not epg_disable:
                tvg_img_url = tvg_mapper_channel.get("tvg_logo", "")
                if config_playlist_tvg_img_url != "" and tvg_img_url != "":
                    tvg_img_url = config_playlist_tvg_img_url + tvg_img_url
                else:
                    tvg_img_url = ""
                info_line = info_line + f' tvg-id="{tvg_mapper_channel.get("tvg_id", "")}" tvg-name="{tvg_mapper_channel.get("tvg_name", "")}" tvg-logo="{tvg_img_url}" group-title="{tvg_mapper_channel.get("group_title", "")}"'
            info_line = info_line + "," + channel["channel_name"]
            uc_url_line = config_playlist_udpxy_url + channel["igmp_ip_port"]
            mc_url_line = "rtp://" + channel["igmp_ip_port"]
            line_unicast.append(info_line)
            line_unicast.append(uc_url_line)
            line_multicast.append(info_line)
            line_multicast.append(mc_url_line)
        result_unicast = "\n".join(line_unicast)
        result_multicast = "\n".join(line_multicast)
        print("Writting unicast playlist to", config_playlist_save_path)
        with open(config_playlist_save_path, "w", encoding="utf-8") as f_unicast_m3u:
            f_unicast_m3u.write(result_unicast)
        print("Writting multicast playlist to", config_playlist_mc_save_path)
        with open(config_playlist_mc_save_path, "w", encoding="utf-8") as f_multicast_m3u:
            f_multicast_m3u.write(result_multicast)

    time.sleep(config_playlist_watcher_interval)