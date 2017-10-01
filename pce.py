#!/bin/python

import sys
pce_target = __import__('pce-target')
pce_initiator = __import__('pce-initiator')
pce_compute = __import__('pce-compute')

def print_general_usage(arg0):
    print("usage: " + arg0 + " <module>")
    print("\nmodules:")
    print("    target     iSCSI server")
    print("    initiator  iSCSI client")
    print("    compute    Compute node configuration")

def main(argv):
    arg0 = argv[0]

    if len(argv) < 2:
        print_general_usage(arg0)
        exit(1)

    module = argv[1]
    if module == 'target':
        return pce_target.main('pce-target', argv[2::])

    elif module == 'initiator':
        return pce_initiator.main('pce-initiator', argv[2::])

    elif module == 'compute':
        return pce_compute.main('pce-compute', argv[2::])

    else:
        print_general_usage(arg0)

if __name__ == "__main__":
    main(sys.argv)

