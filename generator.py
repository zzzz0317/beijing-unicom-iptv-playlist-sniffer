import os
import json
import copy
import argparse

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

def convert_rtsp_ts2hls(source_info: dict):
    result_info = copy.deepcopy(source_info)
    if result_info["type"] == "rtsp":
        if result_info["addr"].endswith(".smil"):
            result_info["addr"] = "http://" + source_info["addr"][7:] + "/index.m3u8?fmt=ts2hls"
    else:
        raise Exception(f"Unsupported ts2hls format: " + result_info["type"])
    result_info["type"] = "http"
    return result_info

def generate_m3u_playlist(
    json_path_list: list[str], 
    key_live: list[str],
    key_timeshift: list[str], 
    rtp_proxy_url: str = "",
    rtsp_proxy_url: str = "",
    multi_source: bool = False, 
    tag_include: list[str] = [],
    tag_exclude: list[str] = ["ignore"],
    epg_url: str = "", 
    logo_url: str = "", 
    catchup_param: str = "playseek=${(b)yyyyMMddHHmmss}-${(e)yyyyMMddHHmmss}",
    keep_channel_acquire_name: bool = False
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
                if k in playlist_data_previous[channel_name]["live"].keys():
                    channel["live"][k] = playlist_data_previous[channel_name]["live"][k]
                elif k.endswith("-httpproxy"):
                    kk = k[:-10]
                    if kk in playlist_data_previous[channel_name]["live"].keys():
                        channel["live"][k] = convert_http_proxy(
                            playlist_data_previous[channel_name]["live"][kk],
                            rtp_proxy_url, rtsp_proxy_url
                        )
                elif k.endswith("-ts2hls"):
                    kk = k[:-7]
                    if kk in playlist_data_previous[channel_name]["live"].keys():
                        channel["live"][k] = convert_rtsp_ts2hls(
                            playlist_data_previous[channel_name]["live"][kk]
                        )
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
                elif k.endswith("-ts2hls"):
                    kk = k[:-7]
                    if kk in playlist_data_previous[channel_name]["timeshift"].keys():
                        channel["timeshift"][k] = convert_rtsp_ts2hls(
                            playlist_data_previous[channel_name]["timeshift"][kk]
                        )
    
    playlist_data = copy.deepcopy(playlist_data)
    channel_del_list = []
    for channel_name, channel in playlist_data.items():
        if len(tag_exclude) > 0:
            flag_exclude = False
            for tag in tag_exclude:
                if tag in channel["flag"]:
                    flag_exclude = True
                    break
            if flag_exclude:
                channel_del_list.append(channel_name)
                continue
        elif len(tag_include) > 0:
            flag_include = False
            if "flag" in channel.keys():
                for tag in tag_include:
                    if tag in channel["flag"]:
                        flag_include = True
                        break
            if not flag_include:
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
        if not multi_source:
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
            
    # test_result = json.dumps(playlist_data, indent=2, ensure_ascii=False)
    # print(test_result)
    m3u_content = [
        f"#EXTM3U name=\"bj-unicom-iptv\" x-tvg-url=\"{epg_url}\"" if epg_url else "#EXTM3U name=\"bj-unicom-iptv\"",
    ]
    for channel_name, channel in playlist_data.items():
        source_list = []
        for live_data in list(channel["live"].values()):
            live_addr = live_data["addr"]
            source_list.append(live_addr)
        if len(source_list) == 0:
            continue
        info_line = f"#EXTINF:-1 channel-number=\"{channel['chno']}\""
        info_line += f" tvg-id=\"{channel['tvg_id']}\"" if channel.get('tvg_id') else ""
        info_line += f" tvg-name=\"{channel['tvg_name']}\"" if channel.get('tvg_name') else ""
        if logo_url:
            info_line += f" tvg-logo=\"{logo_url}{channel['logo']}\"" if channel.get('logo') else ""
        info_line += f" group-title=\"{channel['group_title']}\"" if channel.get('group_title') else ""
        info_line += f" zz-definition=\"{channel['definition']}\"" if channel.get('definition') else ""
        if not keep_channel_acquire_name and channel.get('tvg_name') and channel['tvg_name'] != channel_name:
            info_line += f" zz-raw-name=\"{channel_name}\""
        if len(channel["timeshift"].keys()) > 0:
            timeshift_url = list(channel["timeshift"].values())[0]["addr"]
            if "?" in timeshift_url:
                timeshift_url += "&"
            else:
                timeshift_url += "?"
            timeshift_url += catchup_param
            info_line += f' catchup="default" catchup-source="{timeshift_url}"'
        if not keep_channel_acquire_name and channel.get('tvg_name'):
            info_line += f",{channel['tvg_name']}"
        else:
            info_line += f",{channel_name}"
        m3u_content.append(info_line)
        m3u_content.extend(source_list)
    return "\n".join(m3u_content)
    


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate M3U playlist from ZZ JSON playlist(s).")
    subparsers = parser.add_subparsers(dest="command")
    parser_convert = subparsers.add_parser("convert", help="Convert playlist format.")
    parser_convert.add_argument("source", nargs="+", help="Path(s) to ZZ JSON playlist file(s).")
    parser_convert.add_argument("--key-live", nargs="+", default=["bjunicom-multicast"], help="Keys for live sources to include.")
    parser_convert.add_argument("--key-timeshift", nargs="+", default=["bjunicom-rtsp"], help="Keys for timeshift sources to include.")
    parser_convert.add_argument("--rtp-proxy-url", default="http://iptv.local:8080/rtp/", help="RTP proxy URL.")
    parser_convert.add_argument("--rtsp-proxy-url", default="http://iptv.local:8080/rtsp/", help="RTSP proxy URL.")
    parser_convert.add_argument("--multi-source", action="store_true", help="Enable multi source mode.")
    parser_convert.add_argument("--tag-include", nargs="+", default=[], help="Only include channels with these tags.")
    parser_convert.add_argument("--tag-exclude", nargs="+", default=["ignore"], help="Exclude channels with these tags.")
    parser_convert.add_argument("--keep-ignored-channel", action="store_true", help="Keep channels marked as ignore.")
    parser_convert.add_argument("--keep-channel-acquire-name", action="store_true", help="Use channel name from channelAcquire API")
    parser_convert.add_argument("--epg-url", default="https://raw.githubusercontent.com/zzzz0317/beijing-unicom-iptv-playlist/refs/heads/main/epg.xml.gz", help="EPG URL.")
    parser_convert.add_argument("--logo-url", default="https://raw.githubusercontent.com/zzzz0317/beijing-unicom-iptv-playlist/refs/heads/main/img/", help="Logo URL.")
    parser_convert.add_argument("--catchup-param", default="playseek=${(b)yyyyMMddHHmmss}-${(e)yyyyMMddHHmmss}", help="Catchup parameter.")
    parser_convert.add_argument("--output", default=None, help="Output M3U playlist file path.")
    args = parser.parse_args()
    
    if args.command == "convert":
        exclude_tags = args.tag_exclude
        if args.keep_ignored_channel and "ignore" in exclude_tags:
            exclude_tags.remove("ignore")
        txt = generate_m3u_playlist(
            json_path_list=args.source,
            key_live=args.key_live,
            key_timeshift=args.key_timeshift,
            rtp_proxy_url=args.rtp_proxy_url,
            rtsp_proxy_url=args.rtsp_proxy_url,
            multi_source=args.multi_source,
            tag_include=args.tag_include,
            tag_exclude=exclude_tags,
            epg_url=args.epg_url,
            logo_url=args.logo_url,
            catchup_param=args.catchup_param,
            keep_channel_acquire_name=args.keep_channel_acquire_name,
        )
        if args.output is None:
            print(txt)
        else:
            with open(args.output, "w", encoding="utf-8") as f_out:
                f_out.write(txt)
            print("Writting M3U playlist to", args.output)
    else:
        parser.print_help()
