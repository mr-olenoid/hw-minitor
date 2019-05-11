import requests
import json
import pingparsing
import threading
from requests.adapters import HTTPAdapter
import time
import pika
import urllib3
import time
import mysql.connector as mariadb
import os


red_fish_url = '/redfish/v1/'
connection_timeout = 15.0
connection_retry = 5

#global variables
servers_no_ping = []
servers_heath = []

rabbit_address = os.environ['RABBIT_ADDRESS']
rabbit_port = os.environ['RABBIT_PORT']
rabbit_user = os.environ['RABBIT_USER']
rabbit_password = os.environ['RABBIT_PASSWORD']

#vendor specific variables
v_vars = {'fan': {'Huawei': 'Name', 'default': 'FanName'}, 
        'PhysicalContext': {'Huawei': 'Name', 'default': 'PhysicalContext'}
        }

def get_vendor_specific(data, vendor):
    if vendor not in v_vars[data]:
        return v_vars[data]['default']
    return v_vars[data][vendor]

def conf_loader_sql(ip, user, password, database):
    connection = mariadb.connect(host=ip, user=user, password=password, database=database)
    cursor = connection.cursor()
    query = "select * from hardwareServers;"
    cursor.execute(query)
    result = cursor.fetchall()
    connection.close()
    return result

def msg_make(serverName, message, origin, severity):
    return json.dumps({'name': serverName, 'message': message, 'origin': origin, 'severity': severity})


#common stuff
def srv_stats(server_ip, rf_id, user_id, user_pass):
    #rabbit
    credentials = pika.PlainCredentials(rabbit_user, rabbit_password)
    connection = pika.BlockingConnection(pika.ConnectionParameters(rabbit_address, rabbit_port, '/', credentials))#add to config
    channel = connection.channel()
    channel.exchange_declare(exchange='alarms', exchange_type='fanout')
    #endrabbit
    ping_parser = pingparsing.PingParsing()
    transmitter = pingparsing.PingTransmitter()
    transmitter.destination_host = server_ip
    transmitter.count = 3
    result = transmitter.ping()
    if ping_parser.parse(result).as_dict()['rtt_avg'] is None: # and server_ip not in servers_down:
        time.sleep(10)
        if ping_parser.parse(result).as_dict()['rtt_avg'] is None:
            if server_ip not in servers_no_ping:
                channel.basic_publish(exchange='alarms',
                                    routing_key='',
                                    body=msg_make(server_ip, 'Host unreachable: ' + server_ip, 'hardwareServers', 'info'))#change for actual subscriber group
                                    #server ilo unavalable
                servers_no_ping.append(server_ip)
            return
    #report heath restore
    elif server_ip in servers_no_ping:
        channel.basic_publish(exchange='alarms',
                                routing_key='',
                                body=msg_make(server_ip, 'Host conectivity restored: ' + server_ip, 'hardwareServers', 'info'))#change for actual subscriber group
        servers_no_ping.remove(server_ip)

    #termals, fan state, overall state
    total_url = "https://%s%sSystems/%s" % (server_ip, red_fish_url, rf_id)
    session = requests.Session()
    session.mount('https://', HTTPAdapter(max_retries=connection_retry))
    try:
        data = session.get(total_url, auth=(user_id, user_pass), verify=False, timeout=connection_timeout)
    except requests.exceptions.RequestException as ex:
        print(ex)
    
    stdout = json.loads(data.text)
    model = str(stdout['Model'])
    vendor = stdout['Manufacturer']
    if stdout['Status']['Health'] != "OK" and {server_ip, 'Status', 'Health'} not in servers_heath:
        channel.basic_publish(exchange='alarms',
                            routing_key='',
                            body=msg_make(server_ip, 'Server health deteriorated: ' + str(stdout['Model']) + " " + server_ip, 'hardwareServers', 'warning'))
        servers_heath.append({server_ip, 'Status', 'Health'})
    elif stdout['Status']['Health'] == "OK" and {server_ip, 'Status', 'Health'} in servers_heath:
        channel.basic_publish(exchange='alarms',
                            routing_key='',
                            body=msg_make(server_ip, 'Server health restored: ' + str(stdout['Model']) + " " + server_ip, 'hardwareServers', 'warning'))
        servers_heath.remove({server_ip, 'Status', 'Health'})

    total_url = "https://%s%sChassis/%s/Thermal" % (server_ip, red_fish_url, rf_id)
    #print(total_url)
    try:
        data = session.get(total_url, auth=(user_id, user_pass), verify=False, timeout=connection_timeout)
    except requests.exceptions.RequestException as ex:
        print(ex)
    stdout = json.loads(data.text)

    for fan in stdout['Fans']:
        if fan['Status']['State'] != "Absent":
            if fan['Status']['Health'] != "OK" and {server_ip, fan[get_vendor_specific('fan', vendor)]} not in servers_heath:
                channel.basic_publish(exchange='alarms',
                                    routing_key='',
                                    body=msg_make(server_ip, 'Fan health deteriorated: ' + fan[get_vendor_specific('fan', vendor)] + " " + model + " " + server_ip, 'hardwareServers', 'warning'))
                servers_heath.append({server_ip, fan[get_vendor_specific('fan', vendor)]})
            elif fan['Status']['Health'] == "OK" and {server_ip, fan[get_vendor_specific('fan', vendor)]} in servers_heath:
                channel.basic_publish(exchange='alarms',
                                    routing_key='',
                                    body=msg_make(server_ip, 'Fan health restored: ' + fan[get_vendor_specific('fan', vendor)] + " " + model + " " + server_ip , 'hardwareServers', 'warning'))
                servers_heath.remove({server_ip, fan[get_vendor_specific('fan', vendor)]})

    for temp in stdout['Temperatures']:
        if temp['Status']['State'] != "Absent":
            if temp['Status']['Health'] != "OK" and {server_ip, temp[get_vendor_specific('PhysicalContext', vendor)]} not in servers_heath:
                channel.basic_publish(exchange='alarms',
                                    routing_key='',
                                    body=msg_make(server_ip, "%s high temperature in system %s, ip: %s, temp = %s" % (temp[get_vendor_specific('PhysicalContext', vendor)], model, server_ip, temp['ReadingCelsius']) , 'hardwareServers', 'warning'))
                servers_heath.append({server_ip, temp[get_vendor_specific('PhysicalContext', vendor)]})
            elif temp['Status']['Health'] == "OK" and {server_ip, temp[get_vendor_specific('PhysicalContext', vendor)]} in servers_heath:
                channel.basic_publish(exchange='alarms',
                                    routing_key='',
                                    body=msg_make(server_ip, "%s temperature normalized in system %s, ip: %s, temp = %s" % (temp[get_vendor_specific('PhysicalContext', vendor)], model, server_ip, temp['ReadingCelsius']) , 'hardwareServers', 'warning'))
                servers_heath.remove({server_ip, temp[get_vendor_specific('PhysicalContext', vendor)]})
    connection.close()


def get_servers_data(srv_list):
        for srv in srv_list:
            t = threading.Thread(target=srv_stats, args=(srv['ip'], srv['id'], srv['user_id'], srv['user_pass'],))
            t.start()


if __name__ == '__main__':
    db_address = os.environ['DB_ADDRESS']
    db_user = os.environ['DB_USER']
    db_password = os.environ['DB_PASSWORD']
    db_name = os.environ['DB_NAME']

    user_id = os.environ['REDFISH_USER']
    user_pass = os.environ['REDFISH_PASSWORD']

    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    srv_list = []
    servers = conf_loader_sql(db_address, db_user, db_password ,  db_name)
    for srv in servers:
        srv_list.append({'ip': srv[0], 'id': srv[3], 'user_id': user_id, 'user_pass': user_pass })
    while True:
        get_servers_data(srv_list)
        time.sleep(60 *5)