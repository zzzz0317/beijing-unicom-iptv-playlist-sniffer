import os
import sys
import json
import time
import argparse
import urllib.request

from util import calculate_file_hash, sort_dict_keys, get_remote_content

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
config_playlist_proxy_rtp_url = config.get("playlist_proxy_rtp_url", config.get("playlist_udpxy_url", "http://127.0.0.1:8080/rtp/"))
config_playlist_proxy_rtsp_url = config.get("playlist_proxy_rtsp_url", "http://127.0.0.1:8080/rtsp/")
config_playlist_save_path = config.get("playlist_save_path", "playlist.m3u")
config_playlist_mc_save_path = config.get("playlist_mc_save_path", "playlist_mc.m3u")
config_playlist_ignored_save_path = config.get("playlist_ignored_save_path", "playlist_ignored.m3u")
config_playlist_ignored_mc_save_path = config.get("playlist_ignored_mc_save_path", "playlist_ignored_mc.m3u")
config_playlist_rtsp_save_path = config.get("playlist_rtsp_save_path", "playlist_rtsp.m3u")
config_playlist_rtsp_raw_save_path = config.get("playlist_rtsp_raw_save_path", "playlist_rtsp_raw.m3u")
config_playlist_raw_path = config.get("playlist_raw_path", config.get("sniff_save_path", "playlist_raw.json"))
config_playlist_extract_channel_info_from_epg = config.get("playlist_extract_channel_info_from_epg", False)
config_playlist_rtsp = config.get("playlist_rtsp", False)
config_playlist_catchup = config.get("playlist_catchup", False)
config_playlist_catchup_format = config.get("playlist_catchup_format", "?playseek=${(b)yyyyMMddHHmmss}-${(e)yyyyMMddHHmmss}")
config_playlist_mc_catchup_proxy = config.get("playlist_mc_catchup_proxy", False)
config_playlist_raw_request_marker = config.get("sniff_marker", "9b1d0e32c7ef44769ba2a65958faddf4")
config_playlist_raw_request_useragent = config.get("useragent", "okhttp/3.3.1")
config_epg_server_url = config.get("epg_server_url", "http://210.13.21.3")
config_sniff_token_path = config.get("sniff_token_path", "playlist_token.json")

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
print("config_playlist_tvg_img_url:", config_playlist_tvg_img_url)
print("config_playlist_ignore_channel_list:", config_playlist_ignore_channel_list)
print("config_playlist_additional:", config_playlist_additional)
print("config_playlist_proxy_rtp_url:", config_playlist_proxy_rtp_url)
print("config_playlist_proxy_rtsp_url:", config_playlist_proxy_rtsp_url)
print("config_playlist_save_path:", config_playlist_save_path)
print("config_playlist_mc_save_path:", config_playlist_mc_save_path)
print("config_playlist_ignored_save_path:", config_playlist_ignored_save_path)
print("config_playlist_ignored_mc_save_path:", config_playlist_ignored_mc_save_path)
print("config_playlist_rtsp_save_path:", config_playlist_rtsp_save_path)
print("config_playlist_rtsp_raw_save_path:", config_playlist_rtsp_raw_save_path)
print("config_playlist_raw_path:", config_playlist_raw_path)
print("config_playlist_extract_channel_info_from_epg:", config_playlist_extract_channel_info_from_epg)
print("config_playlist_rtsp", config_playlist_rtsp)
print("config_playlist_catchup", config_playlist_catchup)
print("config_playlist_catchup_format", config_playlist_catchup_format)
print("config_playlist_mc_catchup_proxy", config_playlist_mc_catchup_proxy)
print("config_playlist_raw_request_marker:", config_playlist_raw_request_marker)
print("config_playlist_raw_request_useragent:", config_playlist_raw_request_useragent)
print("config_epg_server_url:", config_epg_server_url)
print("config_sniff_token_path:", config_sniff_token_path)

need_pull_playlist = True
need_update_playlist = True
flag_for_update_playlist_first_run = True

token_hash_path = os.path.join(DIR_SCRIPT, "last_token_hash.txt")
if os.path.exists(token_hash_path):
    with open(token_hash_path, "r") as f_token_hash:
        last_token_hash = f_token_hash.read()
elif os.path.exists(config_sniff_token_path):
    last_token_hash = calculate_file_hash(config_sniff_token_path)
else:
    last_token_hash = "-"

raw_playlist_hash_path = os.path.join(DIR_SCRIPT, "last_raw_playlist_hash.txt")
if os.path.exists(raw_playlist_hash_path):
    with open(raw_playlist_hash_path, "r") as f_raw_playlist_hash:
        last_raw_playlist_hash = f_raw_playlist_hash.read()
elif os.path.exists(config_playlist_raw_path):
    last_raw_playlist_hash = calculate_file_hash(config_playlist_raw_path)
else:
    last_raw_playlist_hash = "-"

while True:
    if not os.path.exists(config_sniff_token_path):
        print("Token not found in", config_sniff_token_path)
        if not config_playlist_watcher_no_exit:
            sys.exit(1)
        time.sleep(config_playlist_watcher_interval)
        continue
    
    if not need_pull_playlist:
        sniff_token_hash = calculate_file_hash(config_sniff_token_path)
        if sniff_token_hash != last_token_hash:
            need_pull_playlist = True
            last_token_hash = sniff_token_hash
            with open(token_hash_path, "w") as f_sniff_token_hash:
                f_sniff_token_hash.write(last_token_hash)
                
    if need_pull_playlist:
        print("need_pull_playlist is True, time to pull playlist!")
        with open(config_sniff_token_path, "r", encoding="utf-8") as f_sniff_token:
            token_data = json.load(f_sniff_token)
        user_token = token_data.get("token", "")
        dip = token_data.get("dip", "210.13.0.147")
        dport = token_data.get("dport", 8080)
        url = f"http://{dip}:{dport}/bj_stb/V1/STB/channelAcquire"
        json_data = json.dumps({'UserToken': user_token}).encode('utf-8')
        request = urllib.request.Request(url, data=json_data, headers={'Content-Type': 'application/json; charset=utf-8', 'User-Agent': config_playlist_raw_request_useragent, "x-zz-marker": config_playlist_raw_request_marker})
        response = urllib.request.urlopen(request)
        result = response.read().decode('utf-8')
        try:
            playlist = json.loads(result)
            playlist = sort_dict_keys(playlist)
            return_code = playlist.get("returnCode", -1)
            if return_code == 0:
                playlist = playlist.get("channleInfoStruct", [])
                playlist = sorted(playlist, key=lambda x: x.get("userChannelID", 0))
                with open(config_playlist_raw_path, "w", encoding="utf-8") as f_raw_playlist_save:
                    json.dump(playlist, f_raw_playlist_save, indent=2, ensure_ascii=False)
                    print("RAW playlist saved to", config_playlist_raw_path)
                    need_pull_playlist = False
            else:
                print("get_raw_playlist_err: return_code is", return_code)
                print(result)
        except Exception as e:
            print("get_raw_playlist_err:", e.__class__.__name__, e)
            print(result)

    if not need_update_playlist or flag_for_update_playlist_first_run:
        if flag_for_update_playlist_first_run:
            flag_for_update_playlist_first_run = False
            print("First run, force to update playlist hash!")
        raw_playlist_hash = calculate_file_hash(config_playlist_raw_path)
        if raw_playlist_hash != last_raw_playlist_hash:
            print("Raw playlist changed, need update playlist!")
            print("Old hash:", last_raw_playlist_hash)
            print("New hash:", raw_playlist_hash)
            need_update_playlist = True
            last_raw_playlist_hash = raw_playlist_hash
            with open(raw_playlist_hash_path, "w") as f_raw_playlist_hash:
                f_raw_playlist_hash.write(last_raw_playlist_hash)

    if need_update_playlist:
        print("need_update_playlist is True, time to update playlist!")
        epg_channel_map = {}
        if config_playlist_extract_channel_info_from_epg:
            try:
                url_epggroup = f"{config_epg_server_url}/epggroup/201.json"
                print("Fetching epg group data from", url_epggroup)
                status_code, data_epggroup = get_remote_content(url_epggroup)
                if status_code != 200:
                    raise Exception(f"Fetch epg group data failed with status code {status_code}")
                data_epggroup = json.loads(data_epggroup)
                # more / for prevent relative path issue
                url_epgpage = f"{config_epg_server_url}/{data_epggroup['group_channel']}"
                print("Fetching epg page data from", url_epgpage)
                status_code, data_epgpage = get_remote_content(url_epgpage)
                if status_code != 200:
                    raise Exception(f"Fetch epg page data failed with status code {status_code}")
                data_epgpage = json.loads(data_epgpage)
                url_epgcategory = f"{config_epg_server_url}/{data_epgpage['elements'][0]['items'][0]['datalink']}"
                print("Fetching epg category data from", url_epgcategory)
                status_code, data_epgcategory = get_remote_content(url_epgcategory)
                if status_code != 200:
                    raise Exception(f"Fetch epg category data failed with status code {status_code}")
                data_epgcategory = json.loads(data_epgcategory)
                for channel in data_epgcategory.get("epgCategorydtl", []):
                    epg_channel_map[channel["code"]] = {
                        "title": channel.get("title", "")
                    }
            except Exception as e:
                print("Fetch epg data error:", e.__class__.__name__, e)
        with open(config_playlist_raw_path, "r", encoding="utf-8") as f_raw_playlist_save:
            channel_list = json.load(f_raw_playlist_save)
        channel_list = sorted(channel_list, key = lambda i: i['userChannelID'])
        # print(channel_list)
        zz_playlist = []
        for channel in channel_list:
            channel_id_sys = channel["channelID"]
            channel_id = channel["userChannelID"]
            channel_url = channel["channelURL"]
            if channel_url.startswith("igmp://"):
                igmp_ip_port = channel_url[7:]
            else:
                print(f"Channel {channel_id} URL is not start from igmp://, ignored")
                continue
            channel_rtsp_url = channel.get("timeShiftURL", "")
            if not channel_rtsp_url.startswith("rtsp://"):
                channel_rtsp_url = None
            channel_name = channel["channelName"].strip()
            channel_timeshift = channel.get("timeShift", False)
            zz_playlist.append({
                "channel_id": channel_id,
                "channel_id_sys": channel_id_sys,
                "igmp_ip_port": igmp_ip_port,
                "channel_name": channel_name,
                "channel_rtsp_url": channel_rtsp_url,
                "channel_timeshift": channel_timeshift
            })
        for channel_name, channel_data in config_playlist_additional.items():
            zz_playlist.append({"channel_id": channel_data["channel_id"], "igmp_ip_port": channel_data["igmp_ip_port"], "channel_name": channel_name})
        zz_playlist = sorted(zz_playlist, key=lambda x: x.get("channel_id", 0))
        need_update_playlist = False
        # print(zz_playlist)
        m3u_header = "#EXTM3U name=\"bj-unicom-iptv\"" if epg_disable else f"#EXTM3U name=\"bj-unicom-iptv\" x-tvg-url=\"{config_playlist_epg_url}\""
        line_unicast = [m3u_header]
        line_multicast = [m3u_header]
        line_rtsp = [m3u_header]
        line_rtsp_raw = [m3u_header]
        line_unicast_ignored = [m3u_header]
        line_multicast_ignored = [m3u_header]
        for channel in zz_playlist:
            flag_ignore_channel = False
            if channel["channel_name"] in config_playlist_ignore_channel_list:
                print("Ignore channel:", channel["channel_name"])
                flag_ignore_channel = True
                #continue
            channel_name_from_epg = None
            channel_id_sys = channel.get("channel_id_sys", None)
            if config_playlist_extract_channel_info_from_epg and channel_id_sys is not None:
                if channel_id_sys in epg_channel_map.keys():
                    channel_name_from_epg = epg_channel_map[channel_id_sys].get("title", None)
            tvg_mapper_channel = tvg_mapper.get(channel["channel_name"], {})
            info_line = f'#EXTINF:-1 channel-number="{channel["channel_id"]}"'
            tvg_id = channel["channel_id"]
            if not epg_disable:
                tmp_epg_data = tvg_mapper_channel.copy()
                if not "tvg-id" in tmp_epg_data.keys():
                    tmp_epg_data["tvg-id"] = channel["channel_id"]
                if channel_name_from_epg is not None:
                    tmp_epg_data["tvg-name"] = channel_name_from_epg
                    if channel_name_from_epg != channel["channel_name"]:
                        tmp_epg_data["zz-raw-name"] = channel["channel_name"]
                if not "tvg-name" in tmp_epg_data.keys():
                    tmp_epg_data["tvg-name"] = channel["channel_name"]
                if "tvg-logo" in tmp_epg_data.keys():
                    tmp_epg_data["tvg-logo"] = config_playlist_tvg_img_url + tmp_epg_data["tvg-logo"]
                info_line = info_line + f' tvg-id="{tmp_epg_data.pop("tvg-id")}" tvg-name="{tmp_epg_data.pop("tvg-name")}"'
                for k in tmp_epg_data.keys():
                    info_line = info_line + f' {k}="{tmp_epg_data[k]}"'
            uc_url_line = config_playlist_proxy_rtp_url + channel["igmp_ip_port"]
            mc_url_line = "rtp://" + channel["igmp_ip_port"]
            rtsp_url_raw_line = channel.get("channel_rtsp_url", None)
            rtsp_url_line = None
            info_line_raw = info_line
            if rtsp_url_raw_line is not None:
                rtsp_url_line = config_playlist_proxy_rtsp_url + rtsp_url_raw_line[7:]
                if config_playlist_catchup:
                    catchup_source_raw = rtsp_url_raw_line.replace("/PLTV/", "/TVOD/") + config_playlist_catchup_format
                    catchup_source = rtsp_url_line.replace("/PLTV/", "/TVOD/") + config_playlist_catchup_format
                    info_line_raw = info_line_raw + f' catchup="default" catchup-source="{catchup_source_raw}"'
                    info_line = info_line + f' catchup="default" catchup-source="{catchup_source}"'
            if channel_name_from_epg is not None:
                info_line_channel_name = channel_name_from_epg
            else:
                info_line_channel_name = channel["channel_name"]
            info_line_raw = info_line_raw + f',{info_line_channel_name}'
            info_line = info_line + f',{info_line_channel_name}'
            if flag_ignore_channel:
                line_unicast_ignored.append(info_line)
                line_unicast_ignored.append(uc_url_line)
                if config_playlist_mc_catchup_proxy:
                    line_multicast_ignored.append(info_line)
                else:
                    line_multicast_ignored.append(info_line_raw)
                line_multicast_ignored.append(mc_url_line)
                continue
            line_unicast.append(info_line)
            line_unicast.append(uc_url_line)
            if config_playlist_mc_catchup_proxy:
                line_multicast.append(info_line)
            else:
                line_multicast.append(info_line_raw)
            line_multicast.append(mc_url_line)
            if rtsp_url_raw_line is not None:
                line_rtsp.append(info_line)
                line_rtsp.append(rtsp_url_line)
                line_rtsp_raw.append(info_line_raw)
                line_rtsp_raw.append(rtsp_url_raw_line)
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
        if config_playlist_rtsp:
            result_rtsp = "\n".join(line_rtsp)
            result_rtsp_raw = "\n".join(line_rtsp_raw)
            print("Writting rtsp playlist to", config_playlist_rtsp_save_path)
            with open(config_playlist_rtsp_save_path, "w", encoding="utf-8") as f_rtsp_m3u:
                f_rtsp_m3u.write(result_rtsp)
            print("Writting rtsp raw playlist to", config_playlist_rtsp_raw_save_path)
            with open(config_playlist_rtsp_raw_save_path, "w", encoding="utf-8") as f_rtsp_raw_m3u:
                f_rtsp_raw_m3u.write(result_rtsp_raw)
    if not config_playlist_watcher_no_exit:
            sys.exit(0)

    time.sleep(config_playlist_watcher_interval)
