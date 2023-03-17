import os
import sys
import struct
import zipfile
from pathlib import Path
import shutil
import fire
import requests

"""

必须以 管理员身份 运行

"""

default_host = "http://127.0.0.1/8000"
host_file = Path(os.path.expanduser('~')) / '.site_address'


if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
    this_dir = Path(sys._MEIPASS)
else:
    this_dir = Path(__file__).parent

user_home_dir = os.path.expanduser('~')
user_ssh_dir = Path(user_home_dir) / '.ssh'

if not user_ssh_dir.exists():
    user_ssh_dir.mkdir()


def get_host():
    if host_file.exists():
        with open(host_file, 'r', encoding='utf-8') as f:
            h = f.read()
            if h.lower().startswith('http://') or h.lower().startswith('https://'):
                return h
            else:
                print('请重新设置正确网站的地址')
                sys.exit(-1)
    else:
        print("请先设置网站的地址")
        sys.exit(-1)


def get_system_width():
    return struct.calcsize('P') * 8


def setup_host(addr):
    """
    设置网站地址，数据举例： http://127.0.0.1/8000
    :param addr: 网站地址
    :return:
    """
    try:
        r = requests.get(addr)
        if r.status_code != 200:
            raise ValueError
    except:
        print('地址非法')
        sys.exit(-1)
    with open(host_file, 'w', encoding='utf-8') as f:
        f.write(addr)


def check_auth():
    """
    验证服务器是否能正常访问本机
    :return:
    """
    host = get_host()
    url = host.strip().strip('/') + '/install/check'
    try:
        r = requests.get(url)
        if r.json()['status']:
            print('服务器【能够】正常访问本机的SSH服务')
    except:
        print('服务器【不能够】访问本机的SSH服务')


def get_authorised_key():
    """
    从服务器获取公钥
    :return:
    """
    host = get_host()
    url = host.strip().strip('/') + f'/install/ssh/{os.getlogin()}'

    try:
        r = requests.get(url)
        pub = r.json()['pub']
    except:
        print('获取rsa公钥失败')
        print(f'请检查接口地址{url}是否正确')
        sys.exit(-1)

    # pub = '''ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQCy4yhSSYotMUP6diWw3e+L/MR1vsdXfJ1aDhujVYDmVRYUOAuLjPFjKltmBJzWp9J27DwzQKMFZtyqHecouqn1ubhuK/FrE0UpWke+ZQfSLPFMcSOPnvszsa0n6AufWgUBMhx4T/N70AcYVuw0ZGcWGQD70zgKZg93QYekjoIjhUOEzw1goOWr2er7igpAfL9SPNXnS399xoNetOsxesOF/Nq67Lrzl3EUi7G/L8EkGuuM9kY2sC82dgersoZ9cJQU4ZPKG2XmHEWfd3+V9oRxupcqVz7b1v0eWgnvp03Um4Dll4kgFsIBEGyDbaLvi3QTRMH9ECyWSZpR5SyzIkzb
    # '''

    with open(user_ssh_dir / 'authorized_keys', 'w', encoding='utf-8') as f:
        f.write(pub)


def install_third(target_dir=os.path.expandvars('%windir%\\system32')):
    """
    使用 OpenSSH 官方的方法
    :return:
    """
    os.chdir(target_dir)

    ssh_pkg = this_dir / f'apps/OpenSSH-Win{get_system_width()}.zip'
    with zipfile.ZipFile(ssh_pkg, 'r') as z:
        z.extractall(target_dir)

    cmd = f'powershell.exe -ExecutionPolicy Bypass -File .\\OpenSSH-Win{get_system_width()}\\install-sshd.ps1'

    os.system(cmd)

    return target_dir


def uninstall_third(target_dir=os.path.expandvars('%windir%\\system32')):
    """
    使用 OpenSSH 官方的方法
    :return:
    """
    # stop service
    cmd = 'powershell.exe Stop-Service sshd'
    os.system(cmd)

    cmd = 'powershell.exe Stop-Service ssh-agent'
    os.system(cmd)

    # remove firewall
    cmd= 'powershell.exe Get-NetFirewallRule -Name *ssh* || powershell.exe Remove-NetFirewallRule -Name sshd'
    os.system(cmd)

    os.chdir(target_dir)
    cmd = f'powershell.exe -ExecutionPolicy Bypass -File .\\OpenSSH-Win{get_system_width()}\\uninstall-sshd.ps1'
    os.system(cmd)

    shutil.rmtree(f'OpenSSH-Win{get_system_width()}', ignore_errors=True)

    return target_dir


def install_official():
    """
    使用微软官方的方法
    参考 https://docs.microsoft.com/zh-cn/windows-server/administration/openssh/openssh_install_firstuse
    :return:
    """
    cmd = 'powershell.exe Add-WindowsCapability -Online -Name OpenSSH.Server~~~~0.0.1.0'
    os.system(cmd)


def uninstall_official():
    """
    使用微软官方的方法
    参考 https://docs.microsoft.com/zh-cn/windows-server/administration/openssh/openssh_install_firstuse
    :return:
    """

    # stop service
    cmd = 'powershell.exe Stop-Service sshd'
    os.system(cmd)

    # remove pkg
    cmd = 'powershell.exe Remove-WindowsCapability -Online -Name OpenSSH.Server~~~~0.0.1.0'
    os.system(cmd)

    # remove firewall
    cmd = 'powershell.exe Get-NetFirewallRule -Name *ssh* || powershell.exe Remove-NetFirewallRule -Name sshd'
    os.system(cmd)
    print('OpenSSH Server related files will be deleted after reboot')


def setup_ssh_server():
    """
    配置服务器
    :return:
    """
    # setup auth pub key
    get_authorised_key()

    # config file
    sshd_config_file = os.path.expandvars('%PROGRAMDATA%\ssh\sshd_config')

    config_content = '''
    Port 22
    #AddressFamily any
    ListenAddress 0.0.0.0
    #ListenAddress ::

    # override default of no subsystems
    Subsystem	sftp	sftp-server.exe

    # Example of overriding settings on a per-user basis
    # Match User anoncvs
    #	AllowTcpForwarding no
    #	PermitTTY no
    #	ForceCommand cvs server

    # Match Group Administrators
    #       AuthorizedKeysFile __PROGRAMDATA__/ssh/administrators_authorized_keys

    AuthorizedKeysFile .ssh/authorized_keys
    PubkeyAuthentication yes
    PasswordAuthentication no
    AllowUsers {current_user}
    AuthenticationMethods publickey

    '''.format(current_user=os.environ.get('USERNAME'))

    with open(sshd_config_file, 'w', encoding='utf-8') as f:
        f.write(config_content)

    # create firewall
    cmd = 'powershell.exe Get-NetFirewallRule -Name *ssh* || powershell.exe New-NetFirewallRule -Name sshd -DisplayName \'OpenSSH Server (sshd)\' -Enabled True -Direction Inbound -Protocol TCP -Action Allow -LocalPort 22'
    os.system(cmd)

    # auto start ssh server
    cmd = 'powershell.exe Set-Service -Name sshd -StartupType \'Automatic\''
    os.system(cmd)

    # start ssh server

    cmd = 'powershell.exe Start-Service sshd'
    os.system(cmd)


def ssh_install():
    """
    安装 ssh-server
    :return:
    """
    get_host()
    r = os.system('powershell.exe Get-Service "sshd" > NUL')
    if r == 1:
        install_third()
        setup_ssh_server()
    else:
        print('Service [sshd] exists')


def ssh_uninstall():
    """
    卸载 ssh-server
    :return:
    """
    r = os.system('powershell.exe Get-Service "sshd" > NUL')
    if r == 1:
        print('Service [sshd] does not exist')
    else:
        uninstall_third()


if __name__ == '__main__':
    fire.Fire({
        'install': ssh_install,
        'uninstall': ssh_uninstall,
        'setup': setup_host,
        'check': check_auth,
        })
