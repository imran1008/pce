#!/bin/python

import config
import copy
import jinja2
import os
import re
import subprocess
import sys
import tempfile

uuid_re = re.compile('(.*):\n    ([a-zA-Z0-9]+) dm-\d+ LIO-ORG,(.*)$')
guest_re = re.compile('^     [^ ]+\s+([^ ]+)\s+(.*)$')

def execute_cmd(hostname, argv):
    subprocess.call(['salt', hostname, 'cmd.run', ' '.join(argv)])

def send_file(hostname, src, dest):
    subprocess.call(['salt-cp', hostname, src, dest])

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

def getDiskId(hostname, label):
    print("Looking up UUID for disk " + label)
    proc = subprocess.Popen(['salt',
                             hostname,
                             'cmd.run', 
                             'multipath -l | grep "LIO-ORG,' + label +'$"'
                            ],
                            stdout=subprocess.PIPE)

    stdout = proc.communicate()
    assert len(stdout) == 2, "Invalid response from Popen"

    output = stdout[0].decode('utf-8')
    uuidMatch = uuid_re.match(output)
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

def getAttachedDisksForGuest(hostname, guestname):
    # Add the bootable disks
    disks = {}
    for _,target in config.targets.items():
        for name,disk in target['disks'].items():
            if 'instance' in disk and disk['instance'] == guestname and 'bootOrder' in disk:
                uuid = getDiskId(hostname, name)
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
    for _,target in config.targets.items():
        for name,disk in target['disks'].items():
            if 'instance' in disk and disk['instance'] == guestname and not ('bootOrder' in disk):
                uuid = getDiskId(hostname, name)

                sortedDisks.append({
                    'uuid': uuid,
                    'type': disk['type'],
                    'bootOrder': None
                })

    return sortedDisks

def getListOfDefinedGuestsInHost(hostname):
    assert hostname in config.computeNodes, "Unknown compute node"
    proc = subprocess.Popen(['salt',
                             hostname,
                             'cmd.run', 
                             'virsh list --all'
                            ],
                            stdout=subprocess.PIPE)

    stdout = proc.communicate()
    assert len(stdout) == 2, "Invalid response from Popen"

    lines = stdout[0].decode('utf-8').split('\n')[2:]
    guests = {} 

    for line in lines:
        match = guest_re.match(line)
        if match != None:
            groups = match.groups()
            assert len(groups) == 2, "Response text does not have correct number of tokens"

            name = groups[0]
            status = groups[1]

            guests[name] = {
                'host': hostname,
                'status': status,
                'title': config.computeInstances[name]['title']
            }

    return guests

def getListOfDefinedGuestsInAllHosts():
    hosts = config.computeNodes
    mergedGuests = {}

    for host in hosts:
        guests = getListOfDefinedGuestsInHost(host)

        # Make sure the guest list isn't already in the mergedGuest list
        for name,guest in guests.items():
            assert not (name in mergedGuests), "Guest is already in another compute node!"
            mergedGuests[name] = guest

    return mergedGuests

def defineVM(hostname, guestname):
    # Make sure guest isn't already defined
    guests = getListOfDefinedGuestsInAllHosts()
    assert not guestname in guests, "Guest is already defined"

    # Load the template
    env = jinja2.Environment(loader=jinja2.FileSystemLoader('files'))
    template = env.get_template('vm.xml')

    # Render the VM guest description
    context = copy.deepcopy(config.computeInstances[guestname])
    context['name'] = guestname
    context['disks'] = getAttachedDisksForGuest(hostname, guestname)
    xml = template.render(context)

    # Send it to the VM host machine
    f = tempfile.NamedTemporaryFile(delete=False)
    f.write(str.encode(xml))
    f.close()
    send_file(hostname, f.name, '/tmp/vm.xml')
    os.unlink(f.name)

    # Define the VM on the host machine
    execute_cmd(hostname, ['virsh', 'define', '/tmp/vm.xml'])

def undefineVM(hostname, guestname):
    execute_cmd(hostname, ['virsh', 'undefine', guestname])

def main(arg0, argv):
    if len(argv) < 1:
        print_general_usage(arg0)
        exit(1)

    cmd = argv[0]

    if cmd == 'list':
        guests = None

        if len(argv) >= 2:
            hostname = argv[1]
            guests = getListOfDefinedGuestsInHost(hostname)
        else:
            guests = getListOfDefinedGuestsInAllHosts()

        for name,guest in guests.items():
            print('name: ' + name.ljust(8) + '\t' + 
                  'host:' + guest['host'].ljust(8) + '\t' + 
                  'status: ' + guest['status'].ljust(10) + '\t' +
                  'title: ' + guest['title'])

    elif cmd == 'define':
        if len(argv) < 2:
            print_define_usage(arg0)
            exit(1)

        hostname = argv[1]
        guestname = argv[2]

        defineVM(hostname, guestname)

    elif cmd == 'undefine':
        if len(argv) < 2:
            print_undefine_usage(arg0)
            exit(1)

        # Undefine the VM on the host machine
        hostname = argv[1]
        guestname = argv[2]
        undefineVM(hostname, guestname)

    elif cmd == 'reload':
        if len(argv) < 2:
            print_reload_usage(arg0)
            exit(1)

        guestname = argv[1]

        guests = getListOfDefinedGuestsInAllHosts()
        assert guestname in guests, "Guest is not defined"
        guest = guests[guestname]

        assert guest['status'] == 'shut off', "Guest is not turned off!"

        hostname = guest['host']
        undefineVM(hostname, guestname)
        defineVM(hostname, guestname)

    else:
        print_general_usage(arg0)

if __name__ == "__main__":
    main(sys.argv[0], sys.argv[1::])

