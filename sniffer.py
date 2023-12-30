import os
import sys
import json
import random
from scapy.all import *
import urllib.request
import traceback

DIR_SCRIPT = os.path.dirname(os.path.realpath(sys.argv[0]))
DIR_RUNNING = os.getcwd()

marker_char = 'abcdefghijklmnopqrstuvwxyz0123456789'
marker = random.sample(marker_char, 32)
marker = "".join(marker)

CONFIG_PATH = os.path.join(DIR_SCRIPT, "config.json")
if os.path.exists(CONFIG_PATH):
    with open(CONFIG_PATH, "r", encoding="utf-8") as f_config_json:
        config = json.load(f_config_json)
else:
    config = {}

config_sniff_no_exit = config.get("sniff_no_exit", False)
config_sniff_interface = config.get("sniff_interface", "eth0")
config_sniff_filter = config.get("sniff_filter", "tcp port 8080")
config_sniff_save_path = config.get("sniff_save_path", "playlist_raw.json")

print("config_sniff_no_exit:", config_sniff_no_exit)
print("config_sniff_interface:", config_sniff_interface)
print("config_sniff_filter:", config_sniff_filter)
print("config_sniff_save_path:", config_sniff_save_path)
print("random_marker:", marker)

def get_raw_playlist(dip, dport, user_token, user_agent="okhttp/3.3.1"):
    url = f"http://{dip}:{dport}/bj_stb/V1/STB/channelAcquire"
    json_data = json.dumps({'UserToken': user_token}).encode('utf-8')
    request = urllib.request.Request(url, data=json_data, headers={'Content-Type': 'application/json; charset=utf-8', 'User-Agent': user_agent, "x-zz-marker": marker})
    response = urllib.request.urlopen(request)
    result = response.read().decode('utf-8')
    try:
        playlist = json.loads(result)
        return_code = playlist.get("returnCode", -1)
        if return_code != 0:
            print("get_raw_playlist_err: return_code is", return_code)
            print(result)
            return
        playlist = playlist.get("channleInfoStruct", [])
        with open(config_sniff_save_path, "w", encoding="utf-8") as f_sniff_save:
            json.dump(playlist, f_sniff_save, indent=2, ensure_ascii=False)
            print("RAW playlist saved to", config_sniff_save_path)
    except Exception as e:
        print("get_raw_playlist_err:", e.__class__.__name__, e)
        print(result)

def packet_callback(packet):
    if packet[TCP].payload:
        try:
            payload = bytes(packet[TCP].payload)
            if len(payload) < 10:
                return
            try:
                payload = payload.decode("utf-8")
            except UnicodeDecodeError:
                print("UnicodeDecodeError in payload, ignored")
                return
            if payload.startswith("POST /bj_stb/V1/STB/channelAcquire"):
                print("="*30)
                print("Discovered a channelAcquire request")
                sip = packet[IP].src
                dip = packet[IP].dst
                sport = packet[IP].sport
                dport = packet[IP].dport
                print("sip:", sip)
                print("sport:", sport)
                print("dip:", dip)
                print("dport:", dport)
                payload = payload.split("\r\n\r\n")
                if marker in payload[0]:
                    print("Marker found in payload header, ignored")
                    return
                user_token = json.loads(payload[1])
                user_token = user_token["UserToken"]
                print("user_token:", user_token)
                get_raw_playlist(dip, dport, user_token)
        except Exception as e:
            print("packet_callback_err:", e.__class__.__name__, e)
            print(traceback.format_exc())
            print(payload)

sniff(iface=config_sniff_interface, filter=config_sniff_filter, prn=packet_callback)