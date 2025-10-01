import os
import sys
import json
import random
import time
import argparse
from scapy.all import *
import urllib.request
import traceback

from util import get_time_str

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

config_sniff_no_exit = config.get("sniff_no_exit", False)
if args.no_exit:
    config_sniff_no_exit = True
config_sniff_interface = config.get("sniff_interface", "eth0")
config_sniff_filter = config.get("sniff_filter", "tcp port 8080")
config_sniff_token_path = config.get("sniff_token_path", "playlist_token.json")
marker = config.get("sniff_marker", "9b1d0e32c7ef44769ba2a65958faddf4")

print("config_sniff_no_exit:", config_sniff_no_exit)
print("config_sniff_interface:", config_sniff_interface)
print("config_sniff_filter:", config_sniff_filter)
print("config_playlist_raw_request_marker:", marker)

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
                with open(os.path.join(DIR_SCRIPT, "user_token.log"), "a", encoding="utf-8") as f_user_token_log:
                    txt = f"{get_time_str()}\t{sip}:{sport}->{dip}:{dport}\t{user_token}\n"
                    f_user_token_log.write(txt)
                with open(config_sniff_token_path, "w", encoding="utf-8") as f_sniff_token:
                    json.dump({"token": user_token, "dip": dip, "dport": dport}, f_sniff_token, indent=2, ensure_ascii=False)
                    print("Token saved to", config_sniff_token_path)
                    if not config_sniff_no_exit:
                        sys.exit(0)
        except Exception as e:
            print("packet_callback_err:", e.__class__.__name__, e)
            print(traceback.format_exc())
            print(payload)

sniff(iface=config_sniff_interface, filter=config_sniff_filter, prn=packet_callback)
