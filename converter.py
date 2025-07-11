import os
import sys
import json
import time
import argparse

from util import calculate_file_hash

DIR_SCRIPT = os.path.dirname(os.path.realpath(sys.argv[0]))
DIR_RUNNING = os.getcwd()

parser = argparse.ArgumentParser()
parser.add_argument('--no-exit', action='store_true', help='Override no exit')
args = parser.parse_args()

CONFIG_PATH = os.path.join(DIR_SCRIPT, "config.json")
if os.path.exists(CONFIG_PATH):
    with open(CONFIG_PATH, "r", encoding="utf-8") as f_config_json:
        config = json.load(f_config_json)
else:
    config = {}


config_playlist_watcher_no_exit = config.get("playlist_watcher_no_exit", False)
if args.no_exit:
    config_playlist_watcher_no_exit = True
config_playlist_watcher_interval = config.get("playlist_watcher_interval", 5)
config_playlist_epg_url = config.get("playlist_epg_url", "")
config_playlist_tvg_img_url = config.get("playlist_tvg_img_url", "")
config_playlist_ignore_channel_list = config.get("playlist_ignore_channel_list", [])
config_playlist_additional = config.get("playlist_additional", {})
config_playlist_udpxy_url = config.get("playlist_udpxy_url", "http://127.0.0.1:8080/rtp/")
config_playlist_save_path = config.get("playlist_save_path", "playlist.m3u")
config_playlist_mc_save_path = config.get("playlist_mc_save_path", "playlist_mc.m3u")
config_playlist_ignored_save_path = config.get("playlist_ignored_save_path", "playlist_ignored.m3u")
config_playlist_ignored_mc_save_path = config.get("playlist_ignored_mc_save_path", "playlist_ignored_mc.m3u")
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
            channel_name = channel["channelName"].strip()
            zz_playlist.append({"channel_id": channel_id, "igmp_ip_port": igmp_ip_port, "channel_name": channel_name})
        for channel_name, channel_data in config_playlist_additional.items():
            zz_playlist.append({"channel_id": channel_data["channel_id"], "igmp_ip_port": channel_data["igmp_ip_port"], "channel_name": channel_name})
        need_update_playlist = False
        # print(zz_playlist)
        m3u_header = "#EXTM3U name=\"bj-unicom-iptv\"" if epg_disable else f"#EXTM3U name=\"bj-unicom-iptv\" x-tvg-url=\"{config_playlist_epg_url}\""
        line_unicast = [m3u_header]
        line_multicast = [m3u_header]
        line_unicast_ignored = [m3u_header]
        line_multicast_ignored = [m3u_header]
        for channel in zz_playlist:
            flag_ignore_channel = False
            if channel["channel_name"] in config_playlist_ignore_channel_list:
                print("Ignore channel:", channel["channel_name"])
                flag_ignore_channel = True
                #continue
            tvg_mapper_channel = tvg_mapper.get(channel["channel_name"], {})
            info_line = f'#EXTINF:-1 channel-number="{channel["channel_id"]}"'
            tvg_id = channel["channel_id"]
            if not epg_disable:
                tmp_epg_data = tvg_mapper_channel.copy()
                if not "tvg-id" in tvg_mapper_channel.keys():
                    tmp_epg_data["tvg-id"] = channel["channel_id"]
                if not "tvg-name" in tvg_mapper_channel.keys():
                    tmp_epg_data["tvg-name"] = channel["channel_name"]
                if "tvg-logo" in tvg_mapper_channel.keys():
                    tmp_epg_data["tvg-logo"] = config_playlist_tvg_img_url + tmp_epg_data["tvg-logo"]
                info_line = info_line + f' tvg-id="{tmp_epg_data.pop("tvg-id")}" tvg-name="{tmp_epg_data.pop("tvg-name")}"'
                for k in tmp_epg_data.keys():
                    info_line = info_line + f' {k}="{tmp_epg_data[k]}"'
            info_line = info_line + "," + channel["channel_name"]
            uc_url_line = config_playlist_udpxy_url + channel["igmp_ip_port"]
            mc_url_line = "rtp://" + channel["igmp_ip_port"]
            if flag_ignore_channel:
                line_unicast_ignored.append(info_line)
                line_unicast_ignored.append(uc_url_line)
                line_multicast_ignored.append(info_line)
                line_multicast_ignored.append(mc_url_line)
            line_unicast.append(info_line)
            line_unicast.append(uc_url_line)
            line_multicast.append(info_line)
            line_multicast.append(mc_url_line)
        result_unicast = "\n".join(line_unicast)
        result_multicast = "\n".join(line_multicast)
        result_unicast_ignored = "\n".join(line_unicast_ignored)
        result_multicast_ignored = "\n".join(line_multicast_ignored)
        print("Writting unicast playlist to", config_playlist_save_path)
        with open(config_playlist_save_path, "w", encoding="utf-8") as f_unicast_m3u:
            f_unicast_m3u.write(result_unicast)
        print("Writting multicast playlist to", config_playlist_mc_save_path)
        with open(config_playlist_mc_save_path, "w", encoding="utf-8") as f_multicast_m3u:
            f_multicast_m3u.write(result_multicast)
        print("Writting ignored unicast playlist to", config_playlist_ignored_save_path)
        with open(config_playlist_ignored_save_path, "w", encoding="utf-8") as f_ignored_unicast_m3u:
            f_ignored_unicast_m3u.write(result_unicast_ignored)
        print("Writting ignored multicast playlist to", config_playlist_ignored_mc_save_path)
        with open(config_playlist_ignored_mc_save_path, "w", encoding="utf-8") as f_ignored_multicast_m3u:
            f_ignored_multicast_m3u.write(result_multicast_ignored)
    if not config_playlist_watcher_no_exit:
            sys.exit(0)

    time.sleep(config_playlist_watcher_interval)