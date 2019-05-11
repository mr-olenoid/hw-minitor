import yaml
import requests
import json
import pingparsing
import threading
from requests.adapters import HTTPAdapter

import time
from prometheus_client import start_http_server, Gauge, Info


red_fish_url = '/redfish/v1/'
connection_timeout = 15.0
connection_retry = 5

server_general = Info("server_general_info", "Server general info", ['serverip'])
server_ping = Gauge('srver_ping', 'Server ping', ['serverip'])


def conf_loader():
    try:
        from yaml import CLoader as Loader, CDumper as Dumper
    except ImportError:
        from yaml import Loader, Dumper
    with open('config.yaml', 'r') as stream:
        try:
            data = yaml.load(stream)
        except yaml.YAMLError as error:
            print(error)
            exit()
        finally:
            return data


#common stuff
def srv_stats(item, rf_id, user_id, user_pass):
    #print(item)
    #print(threading.current_thread())
    ping_parser = pingparsing.PingParsing()
    transmitter = pingparsing.PingTransmitter()
    transmitter.destination_host = item
    transmitter.count = 1
    result = transmitter.ping()
    if ping_parser.parse(result).as_dict()['rtt_avg'] is None:
        ping = -1
    else:
        ping = ping_parser.parse(result).as_dict()['rtt_avg']
    server_ping.labels(serverip=item).set(ping)
    total_url = "https://%s%sSystems/%s" % (item, red_fish_url, rf_id)
    session = requests.Session()
    session.mount('https://', HTTPAdapter(max_retries=connection_retry))
    try:
        data = session.get(total_url, auth=(user_id, user_pass), verify=False, timeout=connection_timeout)
    except requests.exceptions.RequestException as ex:
        print(ex)
    finally:
        stdout = json.loads(data.text)
        print(stdout)
        data_dict = {'Manufacturer': str(stdout['Manufacturer']),
                   'Status': str(stdout['Status']['Health']),
                   'Model': str(stdout['Model']),
                   'PowerState': str(stdout['PowerState']),
                   'hostName': str(stdout['HostName']),
                   'SerialNumber': str(stdout['SerialNumber'])}
        if 'SKU' in stdout:
            data_dict['SKU'] = str(stdout['SKU']) #service tag
        server_general.labels(serverip=item).info(data_dict)


def get_servers_data(cnf):
    for srv_type in cnf:
        for ip in srv_type['ips']:
            t = threading.Thread(target=srv_stats, args=(ip, srv_type['id'], srv_type['user_id'], srv_type['user_pass'],))
            t.start()


if __name__ == '__main__':
    config = conf_loader()
    # Start up the server to expose the metrics.
    start_http_server(config['config']['web_port'])
    # Generate some requests.
    while True:
        get_servers_data(config['config']['servers'])
        time.sleep(60 * 5)
