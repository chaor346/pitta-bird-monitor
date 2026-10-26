# -*- coding: utf-8 -*-
"""
从 PYNQ-Z2 拉取视频和截图
优先用 paramiko(SFTP 自动输密码)；没装 paramiko 时自动改用 scp（终端手动输入密码）
用法:
    python pull_board.py
    python pull_board.py --ip 192.168.2.99 --out D:\bird_videos
安装 paramiko 后可免输密码（可选）:
    python -m pip install paramiko
"""
import argparse, os, sys

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ip", default="192.168.2.99")
    ap.add_argument("--user", default="xilinx")
    ap.add_argument("--pwd", default="xilinx")
    ap.add_argument("--out", default=r"D:\bird_videos")
    ap.add_argument("--remote-dirs", default="runtime/videos,runtime/annotated")
    args = ap.parse_args()

    os.makedirs(args.out, exist_ok=True)
    try:
        import paramiko  # noqa
        return pull_sftp(args)
    except ModuleNotFoundError:
        print("未检测到 paramiko，改用 scp（过程中会提示输入密码，密码 xilinx）")
        return pull_scp(args)

def pull_scp(args):
    import subprocess
    for rdir in args.remote_dirs.split(","):
        rdir = rdir.strip()
        sub = os.path.join(args.out, rdir.replace("/", "_"))
        os.makedirs(sub, exist_ok=True)
        remote = "%s@%s:~/%s/*" % (args.user, args.ip, rdir)
        print("--- 拉取 %s ---" % rdir)
        r = subprocess.run(["scp", "-r", remote, sub])
        if r.returncode != 0:
            print("  [警告] %s 拉取失败，检查板子 IP/连接" % rdir)
    print("拉取完成，本地根目录: %s" % args.out)
    return 0

def pull_sftp(args):
    import posixpath
    import paramiko
    cli = paramiko.SSHClient()
    cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        cli.connect(args.ip, username=args.user, password=args.pwd, timeout=10)
    except Exception as e:
        print("连接失败:", e)
        return 1
    print("已连接 %s" % args.ip)
    sftp = cli.open_sftp()
    home = sftp.normalize(".")
    total = 0
    for rdir in args.remote_dirs.split(","):
        rdir = rdir.strip()
        full = posixpath.join(home, rdir)
        sub = os.path.join(args.out, rdir.replace("/", "_"))
        os.makedirs(sub, exist_ok=True)
        try:
            entries = sftp.listdir(full)
        except IOError:
            print("[跳过] 远程目录不存在: %s" % full)
            continue
        print("--- %s (%d 个文件) ---" % (rdir, len(entries)))
        for name in entries:
            remote = posixpath.join(full, name)
            local = os.path.join(sub, name)
            try:
                sftp.get(remote, local)
                total += 1
                print("  %s (%d KB)" % (name, os.path.getsize(local) // 1024))
            except Exception as e:
                print("  [失败] %s: %s" % (name, e))
    sftp.close()
    cli.close()
    print("拉取完成，共 %d 个文件，本地根目录: %s" % (total, args.out))
    return 0

if __name__ == "__main__":
    sys.exit(main())
