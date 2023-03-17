# coding: utf-8
import socket
from Crypto.PublicKey import RSA
import typing


def check_tcp_service(host: str, port: int) -> bool:
    '''
    检查服务是否在线, 检查指定主机的服务
    :param host: 主机ip
    :param port: 服务端口
    :return: 是否在线
    '''
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(0.2)
    r = False
    try:
        s.connect((host, port))
        s.shutdown(socket.SHUT_RD)
        r = True
    except socket.error as e:
        pass
        # print("Error on connect: %s" % e)

    s.close()
    return r


def generate_keys(private_key_path=None, public_key_path=None, size=2048, password: str = None) -> typing.Tuple[bytes, bytes]:
    """
    生成 rsa 公钥和密码
    :param private_key_path: 生成私钥保存路径
    :param public_key_path: 生成公钥保存路径
    :param size: 密钥位宽 512/1024/2048
    :param password: 导出私钥的加密密码, 可以不提供
    :return:
    """
    key = RSA.generate(size)
    if isinstance(password, str) and password:
        private_key = key.export_key(passphrase=password, pkcs=8, protection="scryptAndAES128-CBC")
    else:
        private_key = key.export_key()

    if private_key_path:
        file_out = open(private_key_path, "wb")
        file_out.write(private_key)
        file_out.close()

    public_key = key.publickey().export_key(format='OpenSSH')  # windows 下的 ssh-server 支持的 OpenSSH， 默认的 PEM 格式不支持
    if public_key_path:
        file_out = open(public_key_path, "wb")
        file_out.write(public_key)
        file_out.close()
    return public_key, private_key


def get_client_ip(request):
    """获取客户的ip地址"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


if __name__ == '__main__':
    a, b = generate_keys()
    print(a)
    print(b)