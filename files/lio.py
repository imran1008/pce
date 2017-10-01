#!/bin/python

import os
import re
import subprocess
import sys

re_ls_obj = re.compile('.*o- ([^ ]*) .*')
re_tpg_num = re.compile('.*o- tpg([0-9]*).*')
re_lun_num = re.compile('.*o- lun([0-9]*).*fileio/([^ ]*)\s.*')

def save_config(env):
    subprocess.call(['targetcli', 'saveconfig'], stdout=open(os.devnull, 'wb'), env=env)

def ls(path, filter, env):
    out = subprocess.Popen(["targetcli", "ls", path, "1"], stdout=subprocess.PIPE, env=env)
    first_skipped = False

    obj_list = []

    for bytes in out.stdout:
        if first_skipped == False:
            first_skipped = True
            continue

        line = bytes.decode('utf-8')

        if filter:
            filtered_obj_name = filter.match(line).groups()
            obj_list.append(filtered_obj_name)
        else:
            obj_name = re_ls_obj.match(line).group(1)
            obj_list.append(obj_name)

    return obj_list

def get_tpgs(target, env):
    return ls('/iscsi/' + target, re_tpg_num, env)

def ensure_root():
    if os.getuid() != 0:
        print("targetcli requires root privileges")
        exit(1)

def find_unused_lun(state, installed_luns):
    if not ('empty_slot' in state):
        state['empty_slot'] = 1
        state['search_installed_luns'] = True

    # If we already know that we won't find an unused slot in the installed
    # LUNs, we can just increment the empty_slot count by one and return it
    if not state['search_installed_luns']:
        empty_slot = state['empty_slot']
        state['empty_slot'] += 1
        return empty_slot

    did_full_scan = True
    current_lun = 0

    # Locate the first LUN slot that is unused
    for lun,_ in installed_luns:
        current_lun = int(lun)

        # If the current lun in the list is less than our starting point,
        # we skip the iteration
        if current_lun < state['empty_slot']:
            continue

        # The slot we were checking is filled, we need to move to the next
        # slot and try again
        elif current_lun == state['empty_slot']:
            state['empty_slot'] += 1

        # We found a gap!
        else:
            did_full_scan = False
            break

    if did_full_scan:
        state['search_installed_luns'] = False

    empty_slot = state['empty_slot']
    state['empty_slot'] += 1
    return empty_slot

# Target configuration
def print_target_usage(arg0):
    print("usage: " + arg0 + " target add [<target>]")
    print("       " + arg0 + " target remove <target>\n")
    print("If the 'target' name is not specified when adding a new object,")
    print("an auto-generated name will be used")

def process_target(sub_cmd, target, env):
    subprocess.call(['targetcli', 'set', 'global', 'auto_add_default_portal=false'], env=env)
    subprocess.call(['targetcli', 'set', 'global', 'auto_add_mapped_luns=true'], env=env)

    if sub_cmd == 'add':
        ensure_root()

        if target != None:
            subprocess.call(['targetcli', '/iscsi', 'create', target], env=env)
        else:
            subprocess.call(['targetcli', '/iscsi', 'create'], env=env)

    elif sub_cmd == 'remove':
        ensure_root()
        subprocess.call(['targetcli', '/iscsi', 'delete', target], env=env)

    else:
        exit(1)

# LUN mapping configuration
def print_map_usage(arg0):
    print("usage: " + arg0 + " <path> <target> (<backstore name> <backstore size>)...\n")
    print("The 'backstore name' and 'backstore size' must be provided in pairs")

def parse_input_list(args):
    input_list = []
    name = None
    size = None

    for arg in args:
        if not name:
            name = arg
        else:
            size = arg
            input_list.append({
                'name': name,
                'size': size
            })
            name = None
            size = None

    return input_list

def process_map(path, target, dry_run, input_list, env):
    # Get the first TPG of the target
    tpgs = get_tpgs(target, env)
    tpg = tpgs[0][0]

    # Get a list of LUNs of the first TPG
    installed_luns = ls('/iscsi/' + target + '/tpg' + tpg + '/luns', re_lun_num, env)

    # Create a list of additions.
    search_state = {}
    additions = []
    for backstore in input_list:
        found = False

        for lun in installed_luns:
            if backstore['name'] == lun[1]:
                found = True
                break

        if not found:
            empty_slot = find_unused_lun(search_state, installed_luns)
            additions.append([empty_slot, backstore])

    # Create a list of removals.
    removals = installed_luns[:]
    for backstore in input_list:
        for x in removals:
            if x[1] == backstore['name']:
                removals.remove(x)
                break

    # Add new LUNs
    if len(additions) > 0:
        print("Add LUNs:")
        for addition in additions:
            lun = str(addition[0])
            name = addition[1]['name']
            size = addition[1]['size']

            print('[' + lun + "] = " + name)
            if not dry_run:
                process_backstore('add', path, name, size, env)
                process_lun('add', target, lun, name, None, None, env)

    # Remove LUNs
    if len(removals) > 0:
        print("Removed LUNs:")
        for removal in removals:
            lun = str(removal[0])
            name = removal[1]
            print('[' + lun + "] = " + name)
            if not dry_run:
                process_backstore('remove', path, name, None, env)

    return not(dry_run)

# Backstore configuration
def print_backstore_usage(arg0):
    print("usage: " + arg0 + " backstore add <path> <backstore> [<size>]")
    print("       " + arg0 + " backstore remove <path> <backstore>")
    print("       " + arg0 + " backstore rename <path> <target> <old name> <new name>")
    print("       " + arg0 + " backstore copy <path> <target> <old name> <new name>")

def process_backstore(sub_cmd, path, backstore, size, env):
    if sub_cmd == 'add':
        ensure_root()

        if size != None:
            subprocess.call(['targetcli', '/backstores/fileio', 'create', backstore, path + '/' + backstore, size],
                            env=env)
        else:
            subprocess.call(['targetcli', '/backstores/fileio', 'create', backstore, path + '/' + backstore],
                            env=env)

    elif sub_cmd == 'remove':
        ensure_root()
        subprocess.call(['targetcli', '/backstores/fileio', 'delete', backstore], env=env)
        os.remove(path + '/' + backstore)

    else:
        print_backstore_usage(argv[0])
        exit(1)

def process_copy(path, target, old_name, new_name, remove_old, env):
    # Get the first TPG of the target
    tpgs = get_tpgs(target, env)
    tpg = tpgs[0][0]

    # Get a list of LUNs of the first TPG
    installed_luns = ls('/iscsi/' + target + '/tpg' + tpg + '/luns', re_lun_num, env)

    # Ensure the new name is unique
    for lun in installed_luns:
        if new_name == lun[1]:
            print("Error: The destination object already exists!")
            exit(1)

    # Find an empty LUN slot or get a new one
    search_state = {}
    lun = find_unused_lun(search_state, installed_luns)
   
    # Perform a copy-on-write duplicate of the backstore
    subprocess.call(['cp', '--reflink=auto', path + '/' + old_name, path + '/' + new_name])

    # Add the new backstore
    process_backstore('add', path, new_name, None, env)
    process_lun('add', target, str(lun), new_name, None, None, env)

    # Remove the old backstore
    if remove_old:
        process_backstore('remove', path, old_name, None, env)

    print("\nIMPORTANT!!")
    print("------------")
    print("Update your config.py to reflect the new name")

# LUN configuration
def print_lun_usage(arg0):
    print("usage: " + arg0 + " lun <add/remove> <target> <lun> [<backstore>] [<initiator_iqn> <mapped_lun>]\n")
    print("The 'backstore' object name must be specified when adding a LUN. The object name must correspond")
    print("to a fileio object. If the 'initiator_iqn' and 'mapped_lun' aren't specified, the lun mapping")
    print(" will be applied to all initiators")

def process_lun(sub_cmd, target, lun, backstore, initiator_iqn, mapped_lun, env):
    if sub_cmd == 'add':
        ensure_root()
        tpgs = get_tpgs(target, env)

        if initiator_iqn != None and mapped_lun != None:
            for tpg in tpgs:
                subprocess.call(['targetcli',
                                 '/iscsi/' + target + '/tpg' + tpg[0] + '/luns',
                                 'create',
                                 '/backstores/fileio/' + backstore,
                                 lun,
                                 'false'],
                                 stdout=open(os.devnull, 'wb'), env=env)

                subprocess.call(['targetcli',
                                 '/iscsi/' + target + '/tpg' + tpg[0] + '/acls/' + initiator_iqn,
                                 'create',
                                 mapped_lun,
                                 lun],
                                 stdout=open(os.devnull, 'wb'), env=env)
            
        else:
            for tpg in tpgs:
                subprocess.call(['targetcli',
                                 '/iscsi/' + target + '/tpg' + tpg[0] + '/luns',
                                 'create',
                                 '/backstores/fileio/' + backstore,
                                 lun],
                                 stdout=open(os.devnull, 'wb'), env=env)

    elif sub_cmd == 'remove':
        ensure_root()
        tpgs = get_tpgs(target, env)

        for tpg in tpgs:
            subprocess.call(['targetcli', '/iscsi/' + target + '/tpg' + tpg[0] + '/luns', 'delete', lun],
                            stdout=open(os.devnull, 'wb'), env=env)

    else:
        exit(1)

# Portal configuration
def print_portal_usage(arg0):
    print("usage: " + arg0 + " portal <add/remove> <target> <tpg> <ip-address>")

def process_portal(sub_cmd, target, tpg, ip, env):
    if sub_cmd == 'add':
        ensure_root()
        subprocess.call(['targetcli', '/iscsi/' + target + '/tpg' + tpg + '/portals', 'create', ip, '3260'], env=env)

    elif sub_cmd == 'remove':
        ensure_root()
        subprocess.call(['targetcli', '/iscsi/' + target + '/tpg' + tpg + '/portals', 'delete', ip, '3260'], env=env)

    else:
        exit(1)

# Initiator configuration
def print_acl_usage(arg0):
    print("usage: " + arg0 + " acl <add/remove> <initiator> [<userid>] [<password>] [<in_userid>] [<in_password>]\n")
    print("The credentials are required only when adding a new ACL object")

def set_acl_auth(target, initiator, tpg, name, value, env):
    subprocess.call(['targetcli',
                     '/iscsi/' + target + '/tpg' + tpg + '/acls/' + initiator,
                     'set',
                     'auth',
                     name + '=' + value], env=env)

def process_acl(sub_cmd, target, initiator, userid, password, in_userid, in_password, env):
    if sub_cmd == 'add':
        ensure_root()
        tpgs = get_tpgs(target, env)

        for tpg in tpgs:
            tpg_num = tpg[0]
            subprocess.call(['targetcli', '/iscsi/' + target + '/tpg' + tpg_num + '/acls', 'create', initiator], env=env)
            set_acl_auth(target, initiator, tpg_num, 'userid', userid, env)
            set_acl_auth(target, initiator, tpg_num, 'password', password, env)
            set_acl_auth(target, initiator, tpg_num, 'mutual_userid', in_userid, env)
            set_acl_auth(target, initiator, tpg_num, 'mutual_password', in_password, env)

    elif sub_cmd == 'remove':
        ensure_root()
        tpgs = get_tpgs(target, env)

        for tpg in tpgs:
            subprocess.call(['targetcli', '/iscsi/' + target + '/tpg' + tpg[0] + '/acls', 'delete', initiator], env=env)

    else:
        exit(1)

# Target Portal Group configuration
def print_tpg_usage(arg0):
    print("usage: " + arg0 + " tpg <add/remove> <target> <tpg>")

def process_tpg(sub_cmd, target, tpg, env):
    if sub_cmd == 'add':
        ensure_root()
        subprocess.call(['targetcli', '/iscsi/' + target, 'create', tpg], env=env)
        subprocess.call(['targetcli', '/iscsi/' + target + '/tpg' + tpg, 'set', 'attribute', 'authentication=1'], env=env)

    elif sub_cmd == 'remove':
        ensure_root()
        subprocess.call(['targetcli', '/iscsi/' + target, 'delete', tpg], env=env)

    else:
        exit(1)

def print_general_usage(arg0):
    print("usage: " + arg0 + " <command>\n")
    print("    target     add/remove a target")
    print("    backstore  add/remove/rename a backstore disk")
    print("    tpg        add/remove a TPG for the specified target")
    print("    portal     add/remove a portal in the specified TPG")
    print("    acl        add/remove an ACL for all TPGs in the specified target")
    print("    lun        add/remove a LUN for all ACLs in the specified target")
    print("    map        update the lun mappings to the specified backstores")

def main(argv):
    env = os.environ
    env["TERM"] = "dumb"

    arg0 = argv[0]

    if len(argv) < 2:
        print_general_usage(arg0)
        exit(1)

    cmd = argv[1]

    if cmd == 'lun':
        if len(argv) < 3:
            print_lun_usage(arg0)
            exit(1)

        sub_cmd = argv[2]
        target = argv[3]
        lun = argv[4]
        backstore = None
        initiator_iqn = None
        mapped_lun = None

        if sub_cmd == 'add':
            if len(argv) == 6:
                backstore = argv[5]

            elif len(argv == 8):
                backstore = argv[5]
                initiator_iqn = argv[6]
                mapped_lun = argv[7]

            else:
                print_lun_usage(arg0)
                exit(1)

        elif sub_cmd == 'remove':
            if len(argv) != 5:
                print_lun_usage(arg0)
                exit(1)
         
        else:
            print_lun_usage(arg0)
            exit(1)

        process_lun(sub_cmd, target, lun, backstore, initiator_iqn, mapped_lun, env)
        save_config(env)

    elif cmd == 'backstore':
        if len(argv) < 5:
            print_backstore_usage(arg0)
            exit(1)

        sub_cmd = argv[2]
        path = argv[3]

        if sub_cmd == 'add':
            backstore = argv[4]
            size = None

            if len(argv) >= 6:
                size = argv[5]

            process_backstore(sub_cmd, path, backstore, size, env)

        elif sub_cmd == 'remove':
            backstore = argv[4]
            process_backstore(sub_cmd, path, backstore, None, env)

        elif sub_cmd == 'rename':
            target = argv[4]
            old_name = argv[5]
            new_name = argv[6]

            process_copy(path, target, old_name, new_name, True, env)

        elif sub_cmd == 'copy':
            target = argv[4]
            old_name = argv[5]
            new_name = argv[6]

            process_copy(path, target, old_name, new_name, False, env)

        else:
            print_backstore_usage(arg0)
            exit(1)

        save_config(env)

    elif cmd == 'portal':
        if len(argv) < 3:
            print_portal_usage(arg0)
            exit(1)

        sub_cmd = argv[2]

        if sub_cmd != 'add' and sub_cmd != 'remove':
            print_portal_usage(arg0)
            exit(1)

        target = argv[3]
        tpg = argv[4]
        ip = argv[5]

        process_portal(sub_cmd, target, tpg, ip, env)
        save_config(env)

    elif cmd == 'acl':
        if len(argv) < 3:
            print_acl_usage(arg0)
            exit(1)

        sub_cmd = argv[2]
        target = argv[3]
        initiator = argv[4]
        userid = None
        password = None
        in_userid = None
        in_password = None

        if sub_cmd == 'add':
            if len(argv) != 9:
                print_acl_usage(arg0)
                exit(1)

            userid = argv[5]
            password = argv[6]
            in_userid = argv[7]
            in_password = argv[8]

        elif sub_cmd == 'remove':
            if len(argv) != 5:
                print_acl_usage(arg0)
                exit(1)

        else:
            print_acl_usage(arg0)
            exit(1)

        process_acl(sub_cmd, target, initiator, userid, password, in_userid, in_password, env)
        save_config(env)

    elif cmd == 'tpg':
        if len(argv) < 3:
            print_tpg_usage(arg0)
            exit(1)

        sub_cmd = argv[2]
        target = argv[3]
        tpg = argv[4]

        if sub_cmd == 'add':
            if len(argv) != 5:
                print_tpg_usage(argv[0])
                exit(1)

        elif sub_cmd == 'remove':
            if len(argv) != 5:
                print_tpg_usage(argv[0])
                exit(1)

        else:
            print_tpg_usage(argv[0])
            exit(1)

        process_tpg(sub_cmd, target, tpg, env)
        save_config(env)

    elif cmd == 'target':
        if len(argv) < 3:
            print_target_usage(arg0)
            exit(1)

        sub_cmd = argv[2]
        target = None

        if sub_cmd == 'add':
            if len(argv) >= 4:
                target = argv[3]

        elif sub_cmd == 'remove':
            if len(argv) != 4:
                print_target_usage(argv[0])
                exit(1)

            target = argv[3]

        else:
            print_target_usage(argv[0])
            exit(1)

        process_target(sub_cmd, target, env)
        save_config(env)

    elif cmd == 'map':
        if len(argv) < 7 or (len(argv) - 5) % 2 == 1:
            print_map_usage(argv[0])
            exit(1)

        # Get the LIO path to the backstores
        path = argv[2]

        # Get the target IQN
        target = argv[3]

        # Check if we should do a dry run
        dry_run = argv[4] != 'false'

        # Parse the input list into a table
        input_list = parse_input_list(argv[5:])

        if process_map(path, target, dry_run, input_list, env):
            save_config(env)

    else:
        print_general_usage(arg0)

if __name__ == "__main__":
    main(sys.argv)


