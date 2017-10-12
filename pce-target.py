#!/bin/python

import sys
sys.path.append('rpc')

pce_salt = __import__('pce-salt')

import config
import os
import socket

g_config = None

def lio(executor, hostname, argv, show_output=False):
    base_path = os.path.dirname(os.path.realpath(__file__))
    executor.send_file(hostname, base_path + '/files/lio.py', '/tmp/lio.py')
    args = ['python', '/tmp/lio.py']
    args.extend(argv)
    executor.run(hostname, args, show_output)

def ensure_root():
    if os.getuid() != 0:
        #print("operation requires root privileges")
        exit(1)

def get_real_hostname(hostname):
    if hostname == 'localhost':
        return socket.gethostname()
    else:
        return hostname

# Target configuration
def print_base_usage(arg0):
    print("usage: " + arg0 + " base init <hostname>")
    print("       " + arg0 + " base deinit <hostname>")

def process_base(executor, hostname, sub_cmd):
    target_hostname = get_real_hostname(hostname)
    target = g_config['targets'][target_hostname]
    target_iqn = target['iqn']
    target_ifaces = target['ifaces']

    if sub_cmd == 'init':
        ensure_root()

        # create the target object
        lio(executor, hostname, ['target', 'add', target_iqn])

        # add TPGs and portals for the target
        if g_config['use_multiple_tpgs']:
            for iface_idx,iface in enumerate(target_ifaces):
                tpg = iface_idx+1
                ip = g_config['iface_map'][target_hostname][iface]
                lio(executor, hostname, ['tpg', 'add', target_iqn, str(tpg)])
                lio(executor, hostname, ['portal', 'add', target_iqn, str(tpg), ip])

        else:
            lio(executor, hostname, ['tpg', 'add', target_iqn, '1'])
            for iface in target_ifaces:
                ip = g_config['iface_map'][target_hostname][iface]
                lio(executor, hostname, ['portal', 'add', target_iqn, '1', ip])

        # add initiators to the TPGs
        for _,initiator_host in g_config['initiators'].items():
            for initiator in initiator_host:
                should_process_target = False

                for allowed_target in initiator['targets']:
                    if allowed_target['hostname'] == target_hostname:
                        should_process_target = True

                if should_process_target:
                    lio(executor, hostname, ['acl',
                                   'add',
                                   target_iqn,
                                   initiator['iqn'],
                                   initiator['userid'],
                                   initiator['password'],
                                   initiator['in_userid'],
                                   initiator['in_password']])

    elif sub_cmd == 'deinit':
        ensure_root()
        lio(executor, hostname, ['target', 'remove', target_iqn])

    else:
        exit(1)

# Backstore configuration
def print_backstore_usage(arg0):
    print("usage: " + arg0 + " backstore add <hostname> <name> <size>")
    print("       " + arg0 + " backstore remove <hostname> <name>")
    print("       " + arg0 + " backstore rename <hostname> <old name> <new name>\n")
    print("       " + arg0 + " backstore copy <hostname> <old name> <new name>\n")

def process_backstore(executor, hostname, sub_cmd, backstore, size):
    target_hostname = get_real_hostname(hostname)
    target = g_config['targets'][target_hostname]
    target_iqn = target['iqn']
    backstore_path = target['backstore_path']

    if sub_cmd == 'add':
        ensure_root()
        path = backstore_path
        lio(executor, hostname, ['backstore', 'add', backstore_path, backstore, size])

    elif sub_cmd == 'remove':
        ensure_root()
        lio(executor, hostname, ['backstore', 'remove', backstore_path, backstore])

    else:
        exit(1)

def process_copy(executor, hostname, old_name, new_name, remove_old):
    target_hostname = get_real_hostname(hostname)
    target = g_config['targets'][target_hostname]
    backstore_path = target['backstore_path']

    if remove_old:
        lio(executor, hostname, ['backstore', 'rename', backstore_path, target['iqn'], old_name, new_name], True)
    else:
        lio(executor, hostname, ['backstore', 'copy', backstore_path, target['iqn'], old_name, new_name], True)

# LUN configuration
def print_lun_usage(arg0):
    print("usage: " + arg0 + " lun add <hostname> <lun> <backstore>")
    print("       " + arg0 + " lun add <hostname> <lun> <backstore> <initiator_iqn> <mapped_lun>")
    print("       " + arg0 + " lun remove <hostname> <lun>\n")
    print("If the 'initiator_iqn' and 'mapped_lun' aren't specified, the lun mapping will be applied to all")
    print("initiators")

def process_lun(executor, hostname, sub_cmd, lun, backstore, initiator_iqn, mapped_lun):
    target_hostname = get_real_hostname(hostname)
    target_iqn = g_config['targets'][target_hostname]['iqn']

    if sub_cmd == 'add':
        ensure_root()

        if initiator_iqn != None and mapped_lun != None:
            lio(executor, hostname, ['lun', 'add', target_iqn, lun, backstore, initiator_iqn, mapped_lun])
        else:
            lio(executor, hostname, ['lun', 'add', target_iqn, lun, backstore])

    elif sub_cmd == 'remove':
        ensure_root()
        lio(executor, hostname, ['lun', 'remove', target_iqn, lun])

    else:
        exit(1)

# LUN mapping configuration
def print_map_usage(arg0):
    print("usage: " + arg0 + " map <hostname> <dry-run>")

def process_map(executor, hostname, dry_run):
    target_hostname = get_real_hostname(hostname)
    target = g_config['targets'][target_hostname]
    disks = target['disks']

    if disks:
        arr = ['map', target['backstore_path'], target['iqn'], dry_run]

        for label,disk in disks.items():
            arr.extend([label, disk['size']])

        lio(executor, hostname, arr, True)

def print_general_usage(arg0):
    print("usage: " + arg0 + " <command> <sub-command> <host>")
    print("    base       initialize/deinitialize the target")
    print("    backstore  add/remove/rename/copy a backstore disk")
    print("    lun        add or remove a LUN")
    print("    map        update block devices and mapping based on config file")

def main(arg0, argv):
    global g_config

    executor = pce_salt.CommandExecutor()

    if len(argv) < 1:
        print_general_usage(arg0)
        exit(1)

    cmd = argv[0]

    if cmd == 'init':
        config.init()

    elif cmd == 'base':
        if len(argv) < 3:
            print_base_usage(arg0)
            exit(1)

        sub_cmd = argv[1]
        if sub_cmd != 'init' and sub_cmd != 'deinit':
            print_base_usage(arg0)
            exit(1)

        g_config = config.get()
        hostname = argv[2]
        process_base(executor, hostname, sub_cmd)

    elif cmd == 'backstore':
        if len(argv) < 3:
            print_backstore_usage(arg0)
            exit(1)

        sub_cmd = argv[1]
        hostname = argv[2]

        if sub_cmd == 'add':
            if len(argv) < 5:
                print_backstore_usage(arg0)
                exit(1)

            g_config = config.get()
            backstore = argv[3]
            size = argv[4]
            process_backstore(executor, hostname, sub_cmd, backstore, size)

        elif sub_cmd == 'remove':
            if len(argv) < 4:
                print_backstore_usage(arg0)
                exit(1)

            g_config = config.get()
            backstore = argv[3]
            process_backstore(executor, hostname, sub_cmd, backstore, None)

        elif sub_cmd == 'rename':
            if len(argv) < 5:
                print_backstore_usage(arg0)
                exit(1)

            g_config = config.get()
            old_name = argv[3]
            new_name = argv[4]
            process_copy(executor, hostname, old_name, new_name, True)

        elif sub_cmd == 'copy':
            if len(argv) < 5:
                print_backstore_usage(arg0)
                exit(1)

            g_config = config.get()
            old_name = argv[3]
            new_name = argv[4]
            process_copy(executor, hostname, old_name, new_name, False)

        else:
            print_backstore_usage(arg0)
            exit(1)

    elif cmd == 'lun':
        if len(argv) < 3:
            print_lun_usage(arg0)
            exit(1)

        g_config = config.get()
        sub_cmd = argv[1]
        hostname = argv[2]
        lun = None
        backstore = None
        initiator_iqn = None
        mapped_lun = None

        if sub_cmd == 'add':
            if len(argv) == 5:
                lun = argv[3]
                backstore = argv[4]

            elif len(argv) == 7:
                lun = argv[3]
                backstore = argv[4]
                initiator_iqn = argv[5]
                mapped_lun = argv[6]
            else:
                print_lun_usage(arg0)
                exit(1)

        elif sub_cmd == 'remove':
            if len(argv) < 4:
                print_lun_usage(arg0)
                exit(1)

            lun = argv[3]
        else:
            print_lun_usage(arg0)
            exit(1)

        process_lun(executor, hostname, sub_cmd, lun, backstore, initiator_iqn, mapped_lun)

    elif cmd == 'map':
        if len(argv) < 3:
            print_map_usage(arg0)
            exit(1)

        g_config = config.get()
        hostname = argv[1]
        dry_run = argv[2]
        process_map(executor, hostname, dry_run)

    else:
        print_general_usage(arg0)

if __name__ == "__main__":
    main(sys.argv[0], sys.argv[1::])

