#! /usr/bin/python
# Copyright 2016 Odd Simon Simonsen @ BV Network AS (www.bvnetwork.no)
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# Some snippets borrowed from 'collectd-elasticsearch' plugin. Thank you.

import json
import urllib2

VERBOSE_LOGGING = False

CLUSTER_NAME = "elasticsearch"
CLUSTER_NODES = ["localhost"]
ADMIN_URLS = []
PROXY_URLS = []

COLLECTION_INTERVAL = 60

# Helpers

def fetch_url(url):
    response = None
    try:
        response = urllib2.urlopen(url, timeout=10)
        return json.load(response)
    except urllib2.URLError, e:
        collectd.error('find plugin: Error connecting to %s - %r' % (url, e))
        return None
    finally:
        if response is not None:
            response.close()

def log_verbose(msg):
    if not VERBOSE_LOGGING:
        return
    collectd.info('find plugin [verbose]: %s' % msg)

def new_value(value_type, value_name, value):
    val = collectd.Values(plugin='find')
    val.plugin_instance = CLUSTER_NAME
    val.type = value_type
    val.type_instance = value_name
    val.values = [value]
    return val

# Collect & Parse

def collect_cluster_health(data):
    # Collects high-level cluster health
    data['cluster_health'] = fetch_url(ADMIN_URLS[0]+'/_cluster/health')

def collect_cluster_stats(data):
    # Collects cluster stats for health, indices, nodes, jvm, fs
    data['cluster_stats'] = fetch_url(ADMIN_URLS[0]+'/_cluster/stats')

def collect_nodes(data):
    nodes = []
    for url in ADMIN_URLS:
        nodes.append(fetch_url(url+'/_nodes'))
    data['nodes'] = nodes

def collect_nodes_stats(data):
    # Collects nodes stats from all nodes
    nodes = []
    for url in ADMIN_URLS:
        nodes.append(fetch_url(url+'/_nodes/stats'))
    data['nodes_stats'] = nodes

def collect_indices_stats(data):
    # Collects stats from all indices at current node
    data['indices_stats'] = fetch_url(ADMIN_URLS[0]+'/_all/_stats')

def collect_proxy_status(data):
    # Checks status of all proxies
    nodes = []
    for url in PROXY_URLS:
        nodes.append(fetch_url(url+'/'))
    data['proxy_status'] = nodes

def parse_indices_totals(data, results):
    # Counts the main indexes (skipping the hidden ones)
    indices_count = 0
    docs_count = 0
    store_size = 0
    queries_current = 0
    indexing_current = 0
    for key, index in data['indices_stats']['indices'].items():
        if key in ['@admin', 'meta', 'runners']:
            continue                              # skip administrative indices
        if key.endswith('__stats') or key.endswith('__admin'):
            continue                              # skip feature indices
        indices_count += 1
        docs_count += index['total']['docs']['count']
        store_size += index['total']['store']['size_in_bytes']/1000000
        queries_current += index['total']['search']['query_current']
        indexing_current += index['total']['indexing']['index_current']
    # add data
    results.append(new_value('gauge', 'find.indices_count', indices_count))
    results.append(new_value('gauge', 'find.docs_count', docs_count))
    results.append(new_value('gauge', 'find.store_size', store_size))
    results.append(new_value('gauge', 'find.queries_current', queries_current))
    results.append(new_value('gauge', 'find.indexing_current',
                                                            indexing_current))

def parse_cluster_splits(data, results):
    # Makes sure all nodes report the same view of the cluster
    nodes = data['nodes']
    # quick and dirty way of counting unique variants
    unique_count = len(set([json.dumps(n, sort_keys=True) for n in nodes]))
    # add data
    results.append(new_value('gauge', 'find.splits',
                                unique_count > 1 and unique_count-1 or 0))

def parse_proxy_status(data, results):
    # Checks all proxy servers for operational status
    count = 0
    for result in data['proxy_status']:
        if int(result['status']) == 200:
            count += 1
    # add data
    results.append(new_value('gauge', 'find.proxies_available', count))
    results.append(new_value('gauge', 'find.proxies_missing',
                                                    len(PROXY_URLS)-count))

def dispatch_to_collectd(results):
    # sends off the values
    for val in results:
        log_verbose('Sending value[%s]: %s=%s' % (
                                val.type, val.type_instance, val.values[0]))
        val.dispatch()

# All collectors are called in turn to build the full data dictionary
collectors = [collect_cluster_health, collect_cluster_stats,
              collect_nodes_stats, collect_nodes,
              collect_indices_stats, collect_proxy_status]
# Each parser extract their relevant information in turn
parsers = [parse_indices_totals, parse_cluster_splits, parse_proxy_status]
# One (or more) displatchers can send or output the final results
displatchers = [dispatch_to_collectd]

def read_callback():
    """Called at each data collection according to interval."""
    data = {}
    for collector in collectors:
        collector(data)
    results = []
    for parser in parsers:
        parser(data, results)
    for dispatcher in displatchers:
        dispatcher(results)

# Initialize

def configure_callback(conf):
    """Called once at plugin load."""
    global CLUSTER_NAME, CLUSTER_NODES, COLLECTION_INTERVAL
    global ADMIN_URLS, PROXY_URLS, VERBOSE_LOGGING
    # read settings
    for node in conf.children:
        if node.key == 'ClusterName':
            CLUSTER_NAME = node.values[0]
        elif node.key == 'ClusterNodes':
            CLUSTER_NODES = node.values
        elif node.key == 'Verbose':
            VERBOSE_LOGGING = bool(node.values[0])
        elif node.key == 'Interval':
            COLLECTION_INTERVAL = int(node.values[0])
        else:
            collectd.warning('find plugin: Unknown config key: %s.' % node.key)
    # configure hosts
    for host in CLUSTER_NODES:
        ADMIN_URLS.append('http://%s:9200' % host)
        PROXY_URLS.append('http://%s:8000' % host)
    # register further callbacks
    collectd.register_read(read_callback, interval=COLLECTION_INTERVAL)
    collectd.info("find plugin started with interval = %d seconds" % (
                                                        COLLECTION_INTERVAL,))
    collectd.info("find plugin cluster %r nodes %r" % (CLUSTER_NAME,
                                                        CLUSTER_NODES))
    collectd.info("find plugin verbose logging = %r" % VERBOSE_LOGGING)

# The following classes are there to launch the plugin manually
# with something like ./elasticsearch_collectd.py for development
# purposes. They basically mock the calls on the "collectd" symbol
# so everything prints to stdout.
class CollectdMock(object):

    def __init__(self):
        self.value_mock = CollectdValuesMock

    def info(self, msg):
        print 'INFO: {}'.format(msg)

    def warning(self, msg):
        print 'WARN: {}'.format(msg)

    def error(self, msg):
        print 'ERROR: {}'.format(msg)
        sys.exit(1)

    def Values(self, plugin='find'):
        return (self.value_mock)()

    def register_read(self, callback, interval):
        pass

class CollectdValuesMock(object):

    def dispatch(self):
        print self

    def __str__(self):
        attrs = []
        for name in dir(self):
            if not name.startswith('_') and name is not 'dispatch':
                attrs.append("{}={}".format(name, getattr(self, name)))
        return "<CollectdValues {}>".format(' '.join(attrs))

class CollectdConfigMock(object):

    def __init__(self):
        self.parent = None
        self.key = 'dummy'
        self.values = 0
        self.children = tuple()


if __name__ == '__main__':
    import sys
    collectd = CollectdMock()
    configure_callback(CollectdConfigMock())
    read_callback()
else:
    import collectd
    collectd.register_config(configure_callback)
