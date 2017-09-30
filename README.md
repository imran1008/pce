# What's PCE
Personal Compute Engine (PCE) is an open-source implementation of an IAAS
(Infrastructure As A Service) system. It provides the user with the ability
to manage pools of virtual storage and virtual machines.

## Storage machines
The storage machines will provide virtual block storage for virtual machines.

### Minimum hardware requirements
 - One network interface for management
 - Few network interfaces for iSCSI traffic
 - At least 4 hard drives in btrfs RAID-10 configuration

### Software requirements
 - GNU/Linux
 - Python 3
 - Saltstack
 - TargetCLI
 - btrfs

## Compute machines
The compute machines will provide a host for running virtual machines. The
hosts will connect to the storage machines via iSCSI to provide block storages
for the virtual machines.

### Minimum hardware requirements
 - One network interface with VLAN support
 - Few network interfaces for iSCSI traffic
 - Plenty of RAM
 - Plenty of CPU cores with VT-x enabled

### Software requirements
 - GNU/Linux
 - Python 3
 - Saltstack
 - Open-iSCSI
 - libvirt
 - KVM
 - MultiPath

