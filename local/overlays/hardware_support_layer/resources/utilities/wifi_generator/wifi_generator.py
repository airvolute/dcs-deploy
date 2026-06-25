import sys
import os
import argparse
import subprocess

USER = os.getenv('USER')
DEFAULT_SSID = USER.lower()
DEFAULT_KEY = "dronecore2024"
DEFAULT_CHANNEL = 1
SPACE = ' '
CON_STR = 'sudo nmcli con'
CON_ARRAY = ['sudo', 'nmcli', 'con']
DEVNULL = open(os.devnull, 'w')

def get_wifi_interfaces():
    try:
        result = subprocess.run(
            ['iw', 'dev'],
            capture_output=True,
            text=True,
            check=True
        )
        interfaces = []
        for line in result.stdout.splitlines():
            if "Interface" in line:
                interfaces.append(line.split()[1])
        return interfaces
    except subprocess.CalledProcessError as e:
        print("Failed to get Wi-Fi interfaces:", e)
        return []

def config_wifi(ap, args):
    freq = ('bg', 'a')[args.five_ghz]
    wifi = get_wifi_interfaces()[0] if get_wifi_interfaces() else "wlan1"
    cmds = [
        CON_ARRAY + ['add', 'type', 'wifi', 'ifname', wifi, 'mode', 'ap', 'con-name', ap, 'ssid', args.ssid],
        CON_ARRAY + ['modify', ap, '802-11-wireless.band', freq],
        CON_ARRAY + ['modify', ap, '802-11-wireless.channel', str(args.channel)],
        CON_ARRAY + ['modify', ap, '802-11-wireless-security.key-mgmt', 'wpa-psk'],
        CON_ARRAY + ['modify', ap, '802-11-wireless-security.proto', 'rsn'],
        CON_ARRAY + ['modify', ap, '802-11-wireless-security.group', 'ccmp'],
        CON_ARRAY + ['modify', ap, '802-11-wireless-security.pairwise', 'ccmp'],
        CON_ARRAY + ['modify', ap, '802-11-wireless-security.psk', args.key],
        CON_ARRAY + ['modify', ap, 'ipv4.method', 'shared']
    ]
    for cmd in cmds:
        subprocess.call(cmd, stdout=DEVNULL)
    print("SSID: "+ args.ssid, "Key: " + args.key, "5GHz: " + str(args.five_ghz))

def exist_connection(ap):
    cmd = CON_ARRAY + ['show', ap]
    ret = subprocess.call(cmd, stdout=DEVNULL, stderr=DEVNULL)
    return (ret == 0)

def set_connection(ap, enable):
    state = ('down', 'up')[enable]
    cmd = CON_ARRAY + [state, ap]
    ret = subprocess.call(cmd, stdout=DEVNULL)
    if ret==0:
        print(SPACE.join(('AP is', state)))

def delete_connection(ap):
    cmd = CON_ARRAY + ['delete', ap]
    ret = subprocess.call(cmd, stdout=DEVNULL)
    if ret == 0:
        print(('AP is deleted'))
    else:
        print(('Delete error'))

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-s", "--ssid", type=str, default=DEFAULT_SSID,
                        help="SSID wifi name. Default: {}".format(DEFAULT_SSID))
    parser.add_argument("-k", "--key", type=str, default=DEFAULT_KEY,
                    help="Wifi key. Default: {}".format(DEFAULT_KEY))
    parser.add_argument("-u", "--up", action='store_true',
                    help="Set connection up. Start access-point mode")
    parser.add_argument("-d", "--down", action='store_true',
                    help="Set connection down. Stop access-point mode")
    parser.add_argument("-ch", "--channel", type=int, default=DEFAULT_CHANNEL,
                    help="Wifi channel. Default: {}".format(DEFAULT_CHANNEL))
    parser.add_argument("-5g","--five_ghz", action='store_true',
                    help="Wifi frequency 5GHz")
    args = parser.parse_args()

    ap = USER.upper() + '_AP'

    if exist_connection(ap):
        set_connection(ap, False)
        if(args.down):
            return 0
        delete_connection(ap)
    config_wifi(ap, args)
    if(args.up):
        set_connection(ap, True)

if __name__ == "__main__":
    main()
