# Roadmap
This document defines the high level goals of the project

## Long-term goal
The PCE project will provide the administrator with a single CLI interface to safely manage block storages and
virtual machines. It will also provide for a way to rebalance virtual machines across hosts to reduce the number of
running physical machines and save power.

## Short-term goals
- Convert config.py to an YAML file
- Consolidate pce-compute.py with pce-initiator.py
- Abstract away iSCSI logic into a different class
- Provide a way to create volume templates
- Provide a way to create volume from templates
- Isolate newly created volumes into its own btrfs subvolume

