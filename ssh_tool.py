# coding: utf-8

import os
import socket
import ssh2
import ssh2.exceptions
import ssh2.sftp_handle
from ssh2.sftp import LIBSSH2_FXF_READ, LIBSSH2_SFTP_S_IRUSR
from ssh2.session import Session
from datetime import datetime
from pathlib import Path
import os
import stat
import typing

class SSH2(object):
    """SSH2 客户端"""
    def __init__(self, host: str, port: int, user: str, path: str, prefix: str, key: typing.AnyStr):
        if not isinstance(key, bytes):
            key = key.encode('utf-8')
        self.host = host
        self.port = port
        self.user = user
        self.key = key
        self.path = path
        self.prefix = prefix
        self.__sock: socket.socket = None
        self.__session: Session = None
        self.is_authenticated = False

    def init_connect(self):
        """初始化连接"""
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((self.host, self.port))
        session = Session()
        session.handshake(sock)
        self.__sock = sock
        self.__session = session

    def authenticate(self):
        """认证"""
        if self.__sock is None or self.__session is None:
            raise ValueError('Please init connect')
        if self.is_authenticated:
            return True
        self.__session.userauth_publickey_frommemory(self.user, self.key)
        self.is_authenticated = self.__session.userauth_authenticated()
        return self.is_authenticated

    def check_remote_path_exist(self):
        if not self.is_authenticated:
            raise ValueError('Please be authenticated')
        sftp = self.__session.sftp_init()
        try:
            r: ssh2.sftp_handle.SFTPHandle = sftp.opendir(self.path)
        except ssh2.exceptions.SFTPProtocolError:
            return False
        return True

    def get_files(self, timestamp: int = None):
        """
        获取远程的文件，如果提供时间戳，只获取比指定时间晚的文件
        """
        if not self.is_authenticated:
            raise ValueError('Please be authenticated')
        files = []
        sftp = self.__session.sftp_init()
        try:
            r: ssh2.sftp_handle.SFTPHandle = sftp.opendir(self.path)
        except ssh2.exceptions.SFTPProtocolError:
            raise
        for i in r.readdir():
            l, n, a = i
            if self.check_if_file(info=a):

                a: ssh2.sftp_handle.SFTPAttributes = a
                files.append((n.decode('utf-8'), a.mtime, a.filesize))
        if timestamp:
            files = [(file_name, file_timestamp, file_size) for file_name, file_timestamp, file_size in files if file_timestamp > timestamp]

        return files

    def download_files(self, files: typing.List, target_dir: (str, Path)):
        """批量下载文件"""
        if not self.is_authenticated:
            raise ValueError('Please be authenticated')
        source_dir = Path(self.path)
        target_dir = Path(target_dir)

        if not target_dir.exists():
            os.system(f'md {target_dir}')

        sftp = self.__session.sftp_init()

        for file_name, file_timestamp, file_size in files:
            fp = target_dir / file_name
            sp = source_dir / file_name
            with sftp.open(str(sp), LIBSSH2_FXF_READ, LIBSSH2_SFTP_S_IRUSR) as fh:
                with open(fp, 'wb') as f:
                    for size, data in fh:
                        f.write(data)

    @classmethod
    def check_tcp_service(cls, host, port):
        """"""
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(0.2)
        r = False
        try:
            s.connect((host, port))
            s.shutdown(socket.SHUT_RD)
            r = True
        except socket.error as e:
            pass  # print("Error on connect: %s" % e)

        s.close()
        return r

    @classmethod
    def check_if_dir(cls, info: ssh2.sftp_handle.SFTPAttributes):
        return stat.S_ISDIR(info.permissions)

    @classmethod
    def check_if_file(cls, info: ssh2.sftp_handle.SFTPAttributes):
        return stat.S_ISREG(info.permissions)

