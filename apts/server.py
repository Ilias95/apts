# Copyright (C) 2015 Ilias Stamatis <stamatis.iliass@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import os
import pwd
import grp
import sys
import socket
import logging

from . import config
from .session import TftpSessionThread
from .errors import TftpRootError


class TftpServer:
    def __init__(self, tftp_root=config.tftp_root, writable=config.writable):
        """
        Keyword arguments:
        tftp_root -- path to the tftp root directory
        writable  -- if True, the server is writable
                     else, a client can only read existing files
        """
        self.tftp_root = tftp_root
        self.writable = writable

        try:
            self.check_tftp_root(writable)
        except TftpRootError as e:
            logging.error(e)
            logging.info("Terminating the server")
            sys.exit(config.EXIT_ROOTDIR_ERROR)

    def listen(self, ip=config.host, port=config.port):
        """
        Start a server listening on the supplied interface and port.
        """
        # AF_INET for IPv4 family address, SOCK_DGRAM for UDP socket
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        server_socket.bind((ip, port))

        logging.info('Start listening on port {}'.format(port))

        # Drop no-longer-needed root privileges for security reasons.
        if TftpServer.drop_root_privileges():
            u = pwd.getpwuid(os.getuid()).pw_name
            g = grp.getgrgid(os.getgid()).gr_name
            logging.info('Dropped root privilages, running as {}:{}'.format(u, g))
        else:
            logging.error("Aborting: didn't drop root privileges")
            sys.exit(config.EXIT_PRIVILEGES)

        while True:
            data, client_address = server_socket.recvfrom(config.bufsize)

            session_thread = TftpSessionThread(ip, client_address,
                                               self.writable, data)
            session_thread.start()

    def check_tftp_root(self, writable):
        """
        Perform sanity checks on the tftp root path.

        Keyword arguments:
        writable - if True, check if the path is writable

        Returns None if the path passes all the checks.
        Otherwise, raises an TftpRootError with an appropriate message.
        """
        if not os.path.exists(self.tftp_root):
            raise TftpRootError("The TFTP root does not exist")
        if not os.path.isdir(self.tftp_root):
            raise TftpRootError("The TFTP root must be a directory")
        if not os.access(self.tftp_root, os.R_OK):
            raise TftpRootError("The TFTP root must be readable")
        if writable and not os.access(self.tftp_root, os.W_OK):
            raise TftpRootError("The TFTP root must be writable")

    @staticmethod
    def drop_root_privileges(user='nobody', group='nobody'):
        """
        Drops root privileges of the process by changing to user 'user' and
        group 'group'.

        Return True if privileges were dropped, else False.
        """
        try:
            new_uid = pwd.getpwnam(user).pw_uid
            new_gid = grp.getgrnam(group).gr_gid
        except KeyError as e:
            logging.error(e)
            return False

        try:
            os.setgroups([]) # remove group privileges
            os.setgid(new_gid)
            os.setuid(new_uid)
        except OSError as e:
            logging.error('Could not set effective group or user id: {}'.format(e))
            return False

        return True


def main():
    server = TftpServer()
    server.listen()
