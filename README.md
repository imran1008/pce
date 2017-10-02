# What's PCE
Personal Compute Engine (PCE) is an open-source implementation of an IAAS
(Infrastructure As A Service) system. It provides the user with the ability
to manage pools of virtual storage and virtual machines.

## Master machine
The master machine is where the PCE software runs. PCE will use Saltstack
to copy and run python scripts on storage machines and compute machines.
This machine doesn't have to be dedicated entirely for running PCE. It can
run on any machine that is not part of the storage system or a host machine
dedicated to run virtual machines, as long as it has an instance of
Salt-master running on it.

### Minimum hardware requirements
 - One network interface for management

### Software requirements
 - GNU/Linux
 - Python 3
 - Saltstack

## Storage machines
The storage machines will provide virtual block storage for virtual machines.

### Minimum hardware requirements
 - One network interface for management
 - Few network interfaces for iSCSI traffic
 - At least 4 hard drives in Btrfs RAID-10 configuration

### Software requirements
 - GNU/Linux
 - Python 3
 - Saltstack
 - TargetCLI
 - BTRFS

## Compute machines
The compute machines will provide a host for running virtual machines. The
hosts will connect to the storage machines via iSCSI to provide block storages
for the virtual machines.

### Minimum hardware requirements
 - One network interface with VLAN support
 - Few network interfaces for iSCSI traffic
 - Plenty of RAM
 - Plenty of x86-64 CPU cores with virtualization enabled

### Software requirements
 - GNU/Linux
 - Python 3
 - Saltstack
 - Open-iSCSI
 - libvirt
 - KVM
 - MultiPath

## Network switch
The following is a list of requirements for the network switch
 - Support VLAN
 - Support Jumbo frames (this is not a hard requirement but jumbo frames greatly improve iSCSI performance)

