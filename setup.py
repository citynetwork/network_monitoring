#!/usr/bin/env python
import os, sys, filecmp, imp
from shutil import copyfile

try:
    imp.find_module('easysnmp')
except ImportError:
    print "Error: You need to install python module easysnmp!"
    print "Eg. pip install easysnmp"
    sys.exit(1)

mibs_source = './mibs'
mibs_dest = '/usr/share/snmp/mibs'

for mib in os.listdir(mibs_source):
    srcmib = "{}/{}".format(mibs_source, mib)
    destmib = "{}/{}".format(mibs_dest, mib)
    if os.path.exists(destmib):
        if not os.path.isfile(destmib):
            raise('{} exists and is not a file!'.format(destmib))
            sys.exit(1)
        else:
            if filecmp.cmp(srcmib, destmib):
                continue
            else:
                copyfile(srcmib, destmib)
    else:
        copyfile(srcmib, destmib)
sys.exit(0)
