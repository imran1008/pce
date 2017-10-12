#!/bin/python

import sys
sys.path.append('rpc')

pce_salt = __import__('pce-salt')
import config
import os
import socket

g_config = None

def ensure_root():
    if os.getuid() != 0:
        #print("operation requires root privileges")
        exit(1)

def get_real_hostname(hostname):
    if hostname == 'localhost':
        return socket.gethostname()
    else:
        return hostname

def get_allowed_targets(hostname):
    initiator_host = get_real_hostname(hostname)
    for initiator in g_config['initiators'][initiator_host]:
        if initiator['managed']:
            return initiator['targets']

def process_rescan(executor, hostname):
    print("Rescanning devices")
    executor.run(hostname, 'find /sys/class/scsi_host/host*/scan | while read line; do echo - - - > $line; done')
    executor.run(hostname, ['iscsiadm', '-m', 'session', '-R'], True)
    executor.run(hostname, ['systemctl', 'restart', 'multipathd'], True)
    executor.run(hostname, ['multipath', '-r'], True)

def process_login(executor, hostname):
    ensure_root()
    targets = get_allowed_targets(hostname)

    for target in targets:
        target_hostname = target['hostname']
        ifaces = target['ifaces']
        target_iqn = g_config['targets'][target_hostname]['iqn']

        print("Logging into " + target_hostname)
        for iface in ifaces:
            ip = g_config['iface_map'][target_hostname][iface]

            executor.run(hostname, ['iscsiadm', '-m', 'discovery', '-p', ip, '-o', 'delete'], True)
            executor.run(hostname, ['iscsiadm', '-m', 'discovery', '-I', iface, '-p', ip, '-t', 'st'], True)
            executor.run(hostname, ['iscsiadm', '-m', 'node', '-T', target_iqn, '--login', '-I', iface, '-p', ip], True)

        print("Logged into " + target_hostname)

    process_rescan(executor, hostname)

def process_logout(executor, hostname):
    ensure_root()
    targets = get_allowed_targets(hostname)

    for target in targets:
        target_hostname = target['hostname']
        ifaces = target['ifaces']
        target_iqn = g_config['targets'][target_hostname]['iqn']

        print("Logging out of " + target_hostname)
        for iface in ifaces:
            ip = g_config['iface_map'][target_hostname][iface]
            executor.run(hostname, ['iscsiadm', '-m', 'node', '-T', target_iqn, '--logout', '-I', iface, '-p', ip])

        print("Logged out of " + target_hostname)

def print_general_usage(arg0):
    print("usage: " + arg0 + " <command> <host>")
    print("    login      login to targets")
    print("    logout     logout of targets")
    print("    rescan     rescan devices")

def main(arg0, argv):
    global g_config

    executor = pce_salt.CommandExecutor()

    if len(argv) < 2:
        print_general_usage(arg0)
        exit(1)

    cmd = argv[0]
    hostname = argv[1]

    if cmd == 'init':
        config.init()

    elif cmd == 'login':
        g_config = config.get()
        process_login(executor, hostname)

    elif cmd == 'logout':
        g_config = config.get()
        process_logout(executor, hostname)

    elif cmd == 'rescan':
        g_config = config.get()
        process_rescan(executor, hostname)

    else:
        print_general_usage(arg0)

if __name__ == "__main__":
    main(sys.argv[0], sys.argv[1::])

