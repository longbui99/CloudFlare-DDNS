#!/bin/bash

cd /opt/source/proxy/cloudflare_ddns
source ./venv/bin/activate

python3 cloudflare_ddns.py -m sshs -c /opt/source/proxy/cloudflare_ddns/longbui.net.yaml
python3 cloudflare_ddns.py -m sshs -c /opt/source/proxy/cloudflare_ddns/vectordi.com.yaml
