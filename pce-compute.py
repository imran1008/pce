#!/bin/python

import sys
sys.path.append('rpc')

pce_salt = __import__('pce-salt')

import config
import copy
import jinja2
import os
import re
import tempfile

g_uuid_re = re.compile('(.*):\n    ([a-zA-Z0-9]+) dm-\d+ LIO-ORG,(.*)$')
g_guest_re = re.compile('^     [^ ]+\s+([^ ]+)\s+(.*)$')
g_config = None

def print_general_usage(arg0):
    print("usage: " + arg0 + " <command>")
    print("    list       list all VMs")
    print("    define     create a VM")
    print("    undefine   destroy a VM")
    print("    reload     reload a VM config")

def print_define_usage(arg0):
    print("usage: " + arg0 + " define <host> <guest>")

def print_undefine_usage(arg0):
    print("usage: " + arg0 + " undefine <host> <guest>")

def print_reload_usage(arg0):
    print("usage: " + arg0 + " reload <guest>")

def getDiskId(executor, hostname, label):
    print("Looking up UUID for disk " + label)
    output = executor.run(hostname, 'multipath -l | grep "LIO-ORG,' + label +'$"')

    uuidMatch = g_uuid_re.match(output)
    assert uuidMatch != None, "Disk is unknown. Maybe you need to rescan your devices"

    groups = uuidMatch.groups()
    assert len(groups) == 3, "Response text does not have correct number of tokens"

    responseHostname = groups[0]
    assert responseHostname == hostname, "Invalid hostname in response"

    responseLabel = groups[2]
    assert responseLabel == label, "Invalid volume label in response"

    responseUUID = groups[1]
    assert len(responseUUID) == 33, "UUID is not of the correct size"
    assert responseUUID.startswith('36001405'), "UUID doesn't have the correct prefix"

    return responseUUID

def getAttachedDisksForGuest(executor, hostname, guestname):
    # Add the bootable disks
    disks = {}
    for _,target in g_config['targets'].items():
        for name,disk in target['disks'].items():
            if 'instance' in disk and disk['instance'] == guestname and 'bootOrder' in disk:
                uuid = getDiskId(executor, hostname, name)
                bootOrder = disk['bootOrder']

                disks[bootOrder] = {
                    'uuid': uuid,
                    'type': disk['type'],
                    'bootOrder': bootOrder
                }

    sortedDisks = []
    for _,disk in disks.items():
        sortedDisks.append(disk)

    # Add the non-bootable disks
    for _,target in g_config['targets'].items():
        for name,disk in target['disks'].items():
            if 'instance' in disk and disk['instance'] == guestname and not ('bootOrder' in disk):
                uuid = getDiskId(executor, hostname, name)

                sortedDisks.append({
                    'uuid': uuid,
                    'type': disk['type'],
                    'bootOrder': None
                })

    return sortedDisks

def getListOfDefinedGuestsInHost(executor, hostname):
    assert hostname in g_config['computeNodes'], "Unknown compute node"

    output = executor.run(hostname, 'virsh list --all')
    lines = output.split('\n')[2:]
    guests = {} 

    for line in lines:
        match = g_guest_re.match(line)
        if match != None:
            groups = match.groups()
            assert len(groups) == 2, "Response text does not have correct number of tokens"

            name = groups[0]
            status = groups[1]

            guests[name] = {
                'host': hostname,
                'status': status,
                'title': g_config['computeInstances'][name]['title']
            }

    return guests

def getListOfDefinedGuestsInAllHosts(executor):
    hosts = g_config['computeNodes']
    mergedGuests = {}

    for host in hosts:
        guests = getListOfDefinedGuestsInHost(executor, host)

        # Make sure the guest list isn't already in the mergedGuest list
        for name,guest in guests.items():
            assert not (name in mergedGuests), "Guest is already in another compute node!"
            mergedGuests[name] = guest

    return mergedGuests

def defineVM(executor, hostname, guestname):
    # Make sure guest isn't already defined
    guests = getListOfDefinedGuestsInAllHosts(executor)
    assert not guestname in guests, "Guest is already defined"

    # Load the template
    env = jinja2.Environment(loader=jinja2.FileSystemLoader('files'))
    template = env.get_template('vm.xml')

    # Render the VM guest description
    context = copy.deepcopy(g_config['computeInstances'][guestname])
    context['name'] = guestname
    context['disks'] = getAttachedDisksForGuest(executor, hostname, guestname)
    xml = template.render(context)

    # Send it to the VM host machine
    f = tempfile.NamedTemporaryFile(delete=False)
    f.write(str.encode(xml))
    f.close()
    executor.send_file(hostname, f.name, '/tmp/vm.xml')
    os.unlink(f.name)

    # Define the VM on the host machine
    executor.run(hostname, ['virsh', 'define', '/tmp/vm.xml'])

def undefineVM(executor, hostname, guestname):
    executor.cmd(hostname, ['virsh', 'undefine', guestname])

def main(arg0, argv):
    global g_config

    executor = pce_salt.CommandExecutor()

    if len(argv) < 1:
        print_general_usage(arg0)
        exit(1)

    cmd = argv[0]

    if cmd == 'init':
        config.init()

    elif cmd == 'list':
        g_config = config.get()
        guests = None

        if len(argv) >= 2:
            hostname = argv[1]
            guests = getListOfDefinedGuestsInHost(executor, hostname)
        else:
            guests = getListOfDefinedGuestsInAllHosts(executor)

        for name,guest in guests.items():
            print('name: ' + name.ljust(8) + '\t' + 
                  'host:' + guest['host'].ljust(8) + '\t' + 
                  'status: ' + guest['status'].ljust(10) + '\t' +
                  'title: ' + guest['title'])

    elif cmd == 'define':
        if len(argv) < 2:
            print_define_usage(arg0)
            exit(1)

        g_config = config.get()
        hostname = argv[1]
        guestname = argv[2]

        defineVM(executor, hostname, guestname)

    elif cmd == 'undefine':
        if len(argv) < 2:
            print_undefine_usage(arg0)
            exit(1)

        # Undefine the VM on the host machine
        g_config = config.get()
        hostname = argv[1]
        guestname = argv[2]
        undefineVM(executor, hostname, guestname)

    elif cmd == 'reload':
        if len(argv) < 2:
            print_reload_usage(arg0)
            exit(1)

        g_config = config.get()
        guestname = argv[1]

        guests = getListOfDefinedGuestsInAllHosts(executor)
        assert guestname in guests, "Guest is not defined"
        guest = guests[guestname]

        assert guest['status'] == 'shut off', "Guest is not turned off!"

        hostname = guest['host']
        undefineVM(executor, hostname, guestname)
        defineVM(executor, hostname, guestname)

    else:
        print_general_usage(arg0)

if __name__ == "__main__":
    main(sys.argv[0], sys.argv[1::])

