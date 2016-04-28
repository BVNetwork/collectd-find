# collectd plugin for Episerver Find clusters

Plugin that collects some additional key indicators for Find Raw clusters.

## Install

1. Install `collectd-python` plugin if not already available.
2. Copy `collectd_find.py` to where `collectd-python` is installed. For
   SignalFx variant this is `/opt/signalfx-collectd-plugin/`.
3. Copy `collectd_find.conf` to where `collectd` stores additional
   configuration files. Name and store the file with a named number prefix,
   typically as `/etc/collectd.d/managed_config/20-elasticsearch.conf` or
   similar.
4. Update the config file to reflect correct cluster values, particularly
   the `ClusterName` as used for reporting dimension on all collected data as
   well as `ClusterNodes` to name the addresses of nodes in the cluster for
   checks:

        <Plugin "python">
            ModulePath "/opt/signalfx-collectd-plugin/"
            Import "collectd_find"
            <Module "collectd_find">
                ClusterName "elasticsearch"
                ClusterNodes "10.0.0.10" "10.0.0.11"
                Interval 60
                Verbose false
            </Module>
        </Plugin>
