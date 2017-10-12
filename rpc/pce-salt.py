#!/bin/python

import subprocess

class CommandExecutor:
    def run(self, hostname, argv, show_output=False):
        proc = None

        if type(argv) is list:
            if hostname == 'localhost':
                proc = subprocess.run(argv,
                                        stdout=subprocess.PIPE)

            else:
                #print("running: " + ' '.join(argv))
                proc = subprocess.run(['salt',
                                         hostname,
                                         'cmd.run',
                                         ' '.join(argv)
                                        ],
                                        stdout=subprocess.PIPE)

        else:
            if hostname == 'localhost':
                proc = subprocess.run(argv.split(' '),
                                        stdout=subprocess.PIPE)

            else:
                #print("running: " + ' '.join(argv))
                proc = subprocess.run(['salt',
                                         hostname,
                                         'cmd.run',
                                         argv
                                        ],
                                        stdout=subprocess.PIPE)

        output = proc.stdout.decode('utf-8')
        if show_output:
            print(output)

        return output

    def send_file(hostname, src, dest):
        subprocess.run(['salt-cp', hostname, src, dest])

