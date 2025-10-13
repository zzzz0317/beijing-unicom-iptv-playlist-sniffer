import os
import json
import copy

def convert_http_proxy(source_info: dict, rtp_proxy_url: str, rtsp_proxy_url: str):
    result_info = copy.deepcopy(source_info)
    if result_info["type"] == "rtp":
        result_info["addr"] = rtp_proxy_url + source_info["addr"][6:]
    elif result_info["type"] == "rtsp":
        result_info["addr"] = rtsp_proxy_url + source_info["addr"][7:]
    else:
        raise Exception(f"Unsupported http proxy format: " + result_info["type"])
    result_info["type"] = "http"
    return result_info

def generate_m3u_playlist(
    json_path_list: list[str], 
    key_live: list[str], key_timeshift: list[str], 
    rtp_proxy_url: str, rtsp_proxy_url: str, 
    single_source: bool, remove_ignored_channel: bool, 
    epg_url: str, logo_url: str, 
    catchup_param: str,
    epg_name_is_channel_name: bool
    ):
    playlist_data = {}
    for zz_playlist_path in json_path_list:
        if not os.path.exists(zz_playlist_path):
            print("playlist file not exist:", zz_playlist_path)
            continue
        with open(zz_playlist_path, "r", encoding="utf-8") as f_playlist:
            zz_playlist_content = json.load(f_playlist)
        for channel_name, channel in zz_playlist_content.items():
            if channel_name in playlist_data:
                for check_key in ["chno", "logo", "group_title", "definition"]:
                    if playlist_data[channel_name].get(check_key, None) is None:
                        playlist_data[channel_name][check_key] = channel.get(check_key, None)
                if playlist_data[channel_name].get("tvg_id", None) is None and playlist_data[channel_name].get("tvg_name", None) is None:
                    playlist_data[channel_name]["tvg_id"] = channel.get("tvg_id", None)
                    playlist_data[channel_name]["tvg_name"] = channel.get("tvg_name", None)
                exist_live_key = playlist_data[channel_name].get("live", {}).keys()
                exist_timeshift_key = playlist_data[channel_name].get("timeshift", {}).keys()
                for k, live_data in channel.get("live", {}).items():
                    if k in exist_live_key:
                        continue
                    playlist_data[channel_name]["live"][k] = live_data
                for k, timeshift_data in channel.get("timeshift", {}).items():
                    if k in exist_timeshift_key:
                        continue
                    playlist_data[channel_name]["timeshift"][k] = timeshift_data
            else:
                playlist_data[channel_name] = channel
                if channel.get("live", None) is None:
                    playlist_data[channel_name]["live"] = {}
                if channel.get("timeshift", None) is None:
                    playlist_data[channel_name]["timeshift"] = {}
    playlist_data = copy.deepcopy(playlist_data)
    playlist_data_previous = copy.deepcopy(playlist_data)
    for channel_name, channel in playlist_data.items():
        if len(key_live) > 0:
            channel["live"] = {}
            for k in key_live:
                if k.endswith("-httpproxy"):
                    kk = k[:-10]
                    if kk in playlist_data_previous[channel_name]["live"].keys():
                        channel["live"][k] = convert_http_proxy(
                            playlist_data_previous[channel_name]["live"][kk],
                            rtp_proxy_url, rtsp_proxy_url
                        )
                if k in playlist_data_previous[channel_name]["live"].keys():
                    channel["live"][k] = playlist_data_previous[channel_name]["live"][k]
        if len(key_timeshift) > 0:
            channel["timeshift"] = {}
            for k in key_timeshift:
                if k in playlist_data_previous[channel_name]["timeshift"].keys():
                    channel["timeshift"][k] = playlist_data_previous[channel_name]["timeshift"][k]
                elif k.endswith("-httpproxy"):
                    kk = k[:-10]
                    if kk in playlist_data_previous[channel_name]["timeshift"].keys():
                        channel["timeshift"][k] = convert_http_proxy(
                            playlist_data_previous[channel_name]["timeshift"][kk],
                            rtp_proxy_url, rtsp_proxy_url
                        )
    
    playlist_data = copy.deepcopy(playlist_data)
    channel_del_list = []
    for channel_name, channel in playlist_data.items():
        if remove_ignored_channel and "ignore" in channel["flag"]:
            channel_del_list.append(channel_name)
            continue
        flag_first_timeshift = True
        tkey_del_list = []
        for tkey in channel["timeshift"].keys():
            if flag_first_timeshift:
                flag_first_timeshift = False
                continue
            tkey_del_list.append(tkey)
        for tkey in tkey_del_list:
            del channel["timeshift"][tkey]
        if single_source:
            flag_first_source = True
            lkey_del_list = []
            for lkey in channel["live"].keys():
                if flag_first_source:
                    flag_first_source = False
                    continue
                lkey_del_list.append(lkey)
            for lkey in lkey_del_list:
                del channel["live"][lkey]
    for ckey in channel_del_list:
        del playlist_data[ckey]
            
    test_result = json.dumps(playlist_data, indent=2, ensure_ascii=False)
    # print(test_result)
    with open("test.json", "w", encoding="utf-8") as f_test:
        f_test.write(test_result)
    m3u_content = [
        f"#EXTM3U name=\"bj-unicom-iptv\" x-tvg-url=\"{epg_url}\"" if epg_url else "#EXTM3U name=\"bj-unicom-iptv\"",
    ]
    for channel_name, channel in playlist_data.items():
        info_line = f"#EXTINF:-1 channel-number=\"{channel['chno']}\""
        info_line += f" tvg-id=\"{channel['tvg_id']}\"" if channel['tvg_id'] else ""
        info_line += f" tvg-name=\"{channel['tvg_name']}\"" if channel['tvg_name'] else ""
        if logo_url:
            info_line += f" tvg-logo=\"{logo_url}{channel['logo']}\"" if channel['logo'] else ""
        info_line += f" group-title=\"{channel['group_title']}\"" if channel['group_title'] else ""
        info_line += f" zz-definition=\"{channel['definition']}\"" if channel['definition'] else ""
        if channel['tvg_name'] and channel['tvg_name'] != channel_name:
            info_line += f" zz-raw-name=\"{channel_name}\""
        if len(channel["timeshift"].keys()) > 0:
            timeshift_url = list(channel["timeshift"].values())[0]["addr"]
            if "?" in timeshift_url:
                timeshift_url += "&"
            else:
                timeshift_url += "?"
            timeshift_url += catchup_param
            info_line += f' catchup="default" catchup-source="{timeshift_url}"'
        if epg_name_is_channel_name and channel['tvg_name']:
            info_line += f",{channel['tvg_name']}"
        else:
            info_line += f",{channel_name}"
        print(info_line)
        m3u_content.append(info_line)
        for live_data in list(channel["live"].values()):
            live_addr = live_data["addr"]
            print(live_addr)
            m3u_content.append(live_addr)
    return "\n".join(m3u_content)
    


if __name__ == "__main__":
    txt = generate_m3u_playlist(
        ["playlist_zz.json", "playlist_zz2.json"],
        ["bjunicom-multicast-httpproxy", "bjunicom-rtsp-httpproxy", "bjunicom-rtsp", "bjunicom-multicast", "lalala", "lalala-httpproxy", "bjunicom-multicast2-httpproxy", "bjunicom-multicast2"],
        ["bjunicom-rtsp-httpproxy", "bjunicom-rtsp"],
        "http://127.0.0.1:8080/rtp/",
        "http://127.0.0.1:8080/rtsp/",
        False,
        True,
        "https://raw.githubusercontent.com/zzzz0317/beijing-unicom-iptv-playlist/refs/heads/main/epg.xml.gz",
        "https://raw.githubusercontent.com/zzzz0317/beijing-unicom-iptv-playlist/refs/heads/main/img/",
        "playseek=${(b)yyyyMMddHHmmss}-${(e)yyyyMMddHHmmss}",
        True
    )
    with open("test2.m3u", "w", encoding="utf-8") as f_test:
        f_test.write(txt)