#!/usr/bin/env python
import os
import sys
import imp
from tempfile import mkstemp
import tarfile
from shutil import copyfile, rmtree
from urlparse import urlparse

external_deps = ['ftputil', 'easysnmp', 'dateutil']
cisco_miburl = urlparse("ftp://ftp.cisco.com/pub/mibs/v2/v2.tar.gz")
mibs_dest = '/usr/share/snmp/mibs'


try:
    for dep in external_deps:
        imp.find_module(dep)
except ImportError:
    deplist = ", ".join(external_deps)
    print "Unmet dependencies, the following external dependencies are required: {}".format(deplist)


from ftputil import FTPHost


print "Downloading required mibs..."
with FTPHost(cisco_miburl.netloc, 'anonymous', 'anonymous') as host:
    if host.path.isfile(cisco_miburl.path):
        tempfile = mkstemp(suffix='.tar.gz')[1]
        host.download(cisco_miburl.path, tempfile)
        print "Unpacking tarball..."
        tar = tarfile.open(tempfile)
        tar.extractall()
        tar.close()
        os.unlink(tempfile)
        print "Installing MIBs..."
        for mib in os.listdir("./auto/mibs/v2"):
            if not mib.endswith(".my"):
                continue
            srcmib = "auto/mibs/v2/{}".format(mib)
            destmib = "{}/{}".format(mibs_dest, mib)
            if os.path.exists(destmib):
                continue
            else:
                try:
                    copyfile(srcmib, destmib)
                except IOError:
                    print "Failed to copy mibs, not running as root?"
                    rmtree('./auto')
                    sys.exit(1)
        rmtree('./auto')
    else:
        raise('Failed to download {} from {}'.format(cisco_miburl.path, cisco_miburl.netloc))
        sys.exit(1)


print "Done."
sys.exit(0)
