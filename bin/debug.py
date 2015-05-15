#!/usr/bin/env python
#
# Copyright 2014 Huawei Technologies Co. Ltd
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Scripts to delete cluster and it hosts"""

import logging
import os
import re
import socket
import sys
import time
import os.path
import sys
import simplejson as json


current_dir = os.path.dirname(os.path.realpath(__file__))
sys.path.append(current_dir)


import switch_virtualenv


from compass.db.api import cluster as cluster_api
from compass.db.api import database
from compass.db.api import host as host_api
from compass.db.api import user as user_api
from compass.utils import flags
from compass.utils import logsetting
from compass.utils import setting_wrapper as setting
from compass.apiclient.restful import Client
import client as bin_client

flags.add('clusternames',
          help='comma seperated cluster names',
          default='')
flags.add_bool('delete_hosts',
               help='if all hosts related to the cluster will be deleted',
               default=False)


def delete_clusters():
    clusternames = [
        clustername
        for clustername in flags.OPTIONS.clusternames.split(',')
        if clustername
    ]
    user = user_api.get_user_object(setting.COMPASS_ADMIN_EMAIL)
    list_cluster_args = {}
    if clusternames:
        list_cluster_args['name'] = clusternames
    clusters = cluster_api.list_clusters(
        user=user, **list_cluster_args
    )
    delete_underlying_host = flags.OPTIONS.delete_hosts
    for cluster in clusters:
        cluster_id = cluster['id']
        cluster_api.del_cluster(
            cluster_id, True, False, delete_underlying_host, user=user
        )
        
def _login(client,compass_user_email,compass_user_password):
    """get apiclient token."""
    status, resp = client.get_token(compass_user_email,compass_user_password
    )
    logging.info(
        'login status: %s, resp: %s',
        status, resp
    )
    if status >= 400:
        raise Exception(
            'failed to login %s with user %s',compass_user_email,compass_user_password
        )
    return resp['token']

def _get_cluster_host_status(client,cluster_id,host_mapping):
    cluster_installed = False
    cluster_failed = False
    hosts_installed = {}
    hosts_failed = {}
    install_finished = False
    deployment_failed = False
    status, cluster_state = client.get_cluster_state(cluster_id)
    print 'get cluster %s state status %s: %s' %(cluster_id, status, cluster_state)
    
    if status >= 400:
        raise Exception(
            'failed to acquire cluster %s state' % cluster_id
        )
    if cluster_state['state'] in ['UNINITIALIZED', 'INITIALIZED']:
        if current_time >= action_timeout:
            deployment_failed = True
            exit
    if cluster_state['state'] == 'SUCCESSFUL':
        cluster_installed = True
    if cluster_state['state'] == 'ERROR':
        cluster_failed = True
    for hostname, host_id in host_mapping.items():
        status, host_state = client.get_cluster_host_state(
            cluster_id, host_id
        )
        print 'get cluster %s host %s state status %s: %s'%(cluster_id, host_id, status, host_state)
        if status >= 400:
            raise Exception(
                'failed to acquire cluster %s host %s state' % (
                    cluster_id, host_id
                )
            )
        if host_state['state'] in ['UNINITIALIZED', 'INITIALIZED']:
            raise Exception(
                'unintended status for host %s: %s' % (
                    hostname, host_state
                )
            )
        if host_state['state'] == 'SUCCESSFUL':
            hosts_installed[host_id] = True
        else:
            hosts_installed[host_id] = False
        if host_state['state'] == 'ERROR':
            hosts_failed[host_id] = True
        else:
            hosts_failed[host_id] = False

    cluster_finished = cluster_installed or cluster_failed
    hosts_finished = {}
    for _, host_id in host_mapping.items():
        hosts_finished[host_id] = (
            hosts_installed.get(host_id, False) or
            hosts_failed.get(host_id, False)
        )
    if cluster_finished:
        if not all(hosts_finished.values()):
            raise Exception(
                'some host are not finished: %s' % hosts_finished
            )
        print ('all clusters/hosts are installed.')
        install_finished = True
        exit
    else:
        print ('there are some clusters/hosts in installing. \r\nsleep 10 seconds and retry')
        time.sleep(2.0)
    
if __name__ == '__main__':
    COMPASS_SERVER_URL="http://10.1.0.12/api"
    COMPASS_USER_EMAIL="admin@huawei.com"
    COMPASS_USER_PASSWORD="admin"
    
    logsetting.init()
    
    client = Client(COMPASS_SERVER_URL)
    _login(client,COMPASS_USER_EMAIL,COMPASS_USER_PASSWORD)
    status, resp = client.list_hosts()
    #print '\r\nget all hosts status: %s resp\r\n' % (status)
    #print json.dumps(resp,indent=2)  
    if status >= 400:
        msg = 'failed to get subnets'
        raise Exception(msg)
    host_mapping = {}
    for host in resp:
        host_mapping[host['hostname']] = host['id']
    print '\r\nget hostmapping: %s \r\n' % (host_mapping) 
    
    status, resp = client.list_clusters()
    #print '\r\nget all cluster status: %s resp: \r\n' % (status) 
    #print json.dumps(resp,indent=2)
    if status >= 400:
        msg = 'failed to get subnets'
        raise Exception(msg)
        
    cluster_id = resp[0]['id']
    print '\r\n_get_cluster_host_status:%s\r\n' %cluster_id
    _get_cluster_host_status(client, cluster_id, host_mapping)

    



