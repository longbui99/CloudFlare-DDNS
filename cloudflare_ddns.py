import os
import time
import json
import yaml
import requests
import argparse
from datetime import datetime
from pytz import timezone

CLOUDFLARE_API = "https://api.cloudflare.com/client/v4"
CURRENT_PATH = os.path.dirname(__file__)

os.environ['TZ'] = 'Etc/GMT'
time.tzset()


class Configuration:
    def __init__(self, file_path=CURRENT_PATH + "/config.yaml"):
        self.name = "Cloud Flare"
        self.load_credential(file_path)

    def load_credential(self, file_path):
        with open(file_path, 'r') as f:
            self.config = yaml.safe_load(f)['cloudflare']
            f.close()
        self.credentials = self.config['credentials']
        for key, value in self.credentials.items():
            setattr(self, key, value)
        self.zone = self.config['zone']
        self.domains = {value['name']: value for key, value in self.config['domains'].items()}

class IP:
    def __init__(self, ipv4=True, ipv6=False):
        self.ipv4 = ipv4
        self.ipv4_path = CURRENT_PATH + '/ipv4.txt'
        self.ipv6 = ipv6

    def update_ipv4_history(self, ipv4):
        res = False
        existing = list()
        with open(CURRENT_PATH + '/ipv4.txt', 'rw') as f:
            for ip_record in f.readlines():
                ip, timestamp = ip_record.split('|')
                existing.append(ip)
        if not len(existing) or ipv4 != existing[0]:
            res = True
        return res

    def load_ipv4(self):
        response = requests.get('https://1.1.1.1/cdn-cgi/trace')
        body = response.text.strip()
        address = dict([x.split('=') for x in body.split("\n")])
        if not os.path.exists(self.ipv4_path):
            open(self.ipv4_path, 'w').close()
        with open(self.ipv4_path, 'r') as f:
            last_ipv4 = f.read().strip()
            f.close()
        self.ipv4_id = address['ip']
        
    def save_ip(self):
        checkpoint_time = datetime.now().astimezone(timezone("Asia/Saigon"))
        converted_time = checkpoint_time.strftime("%Y, %b %d, %H:%M:%S (%z)")
        if self.ipv4_id:
            open(self.ipv4_path, 'a').write(f"""{converted_time}:\t{self.ipv4_id}\n""")

    def load_ipv6(self):
        pass

    def load_ip(self):
        if self.ipv4:
            self.load_ipv4()
        if self.ipv6:
            self.load_ipv6()

class CloudFlareDDNS:
    def __init__(self,  config, ip):
        self.endpoint = CLOUDFLARE_API
        self.config = config
        self.ip = ip

    def make_headers(self):
        return {
            'X-Auth-Email': self.config.email,
            'X-Auth-Key': self.config.api_key,
            'Authorization': f"Beader {self.config.api_token}"
        }
    
    def make_request(self, request_data):
        headers = self.make_headers()
        endpoint = request_data.get('endpoint', None)
        if not endpoint:
            return {}
        if 'params' in request_data:
            endpoint += "?" + '&'.join(request_data['params'])
        body = request_data.get('body') or dict()
        if request_data.get('method', 'get') in ['post', 'put']:
            headers.update({'Content-Type': 'application/json'})
        method = getattr(requests, request_data.get('method', 'get'))
        result = method(url=endpoint, headers=headers, json=body)
        if result.status_code >= 400:
            raise Exception(result.text)
        if result.text == "":
            return ""
        body = result.json()
        if isinstance(body, dict):
            if len(body.get('errors') or []):
                raise Exception(body.get('errors'))
        return body

    def get_dns_records(self):
        request_data = {
            'endpoint': f"{self.endpoint}/zones/{self.config.zone}/dns_records",
            'method': 'get'
        }
        payload = self.make_request(request_data)
        todo_domains = set(self.config.domains.keys())
        to_update_domains = []
        for dns in payload.get('result', []):
            if dns['name'] not in todo_domains:
                continue
            if self.ip.ipv4:
                if dns['type'] == "A" and dns["content"] != self.ip.ipv4_id:
                    to_update_domains.append(dns)
                    dns['new_content'] = self.ip.ipv4_id
        self.updating_domains = to_update_domains
    
    def update_dns_records(self):
        for dns in self.updating_domains:
            request_data = {
                'endpoint': f"{self.endpoint}/zones/{self.config.zone}/dns_records/{dns['id']}",
                'method': 'put',
                'body': {
                    'content': dns['new_content'],
                    'type': dns['type'],
                    'name': dns['name'],
                    'proxied': dns['proxied']
                }
            }
            self.make_request(request_data)
    
    def execute(self):
        self.get_dns_records()
        self.update_dns_records()
        self.ip.save_ip()
        
def parse_args():
    parser = argparse.ArgumentParser(description="Just an example", formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("-m", "--mode", help="archive mode", default='python3')
    parser.add_argument("-c", "--config", help="Config mode", default=CURRENT_PATH + '/config.yaml')
    parser.add_argument("-s", "--sleep", help="Sleep mode", default='5')
    args, unknown = parser.parse_known_args()
    config = vars(args)
    os.environ['MODE'] = config['mode']
    os.environ['CONFIG'] = config['config']
    os.environ['SLEEP'] = config['sleep']
    os.environ['PARAMS'] = json.dumps(config)

def execute(loop_count):
    try:
        config = Configuration(os.environ['CONFIG'])
        sleep = int(os.environ.get('SLEEP'))
        ip_config = IP(ipv4=True, ipv6=False)
        cloud_flare_ddns = CloudFlareDDNS(config, ip_config)
        index = 0
        while index <= loop_count:
            ip_config.load_ip()
            if ip_config.ipv4_id:
                cloud_flare_ddns.execute()
            index +=1
            if index <= loop_count:
                time.sleep(sleep)
    except Exception as e:
        open(CURRENT_PATH + "/error.logs", 'w').write(str(e))

if __name__ == '__main__':
    parse_args()
    loop_count = float('inf')
    if os.environ['MODE'] != 'python3':
        loop_count = 0
    execute(loop_count)