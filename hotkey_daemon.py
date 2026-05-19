#!/usr/bin/env python
# -*- coding: UTF-8 -*-
import io
import sys
import time
import ctypes
import threading
import platform
import winerror
from ftplib import FTP
from pathlib import Path
from ctypes import wintypes

if 'Windows' not in platform.platform():
    raise SystemExit('hotkey_daemon.py 仅支持 Windows')

import win32api
import win32clipboard
import win32con
import win32event

IP = "10.90.4.11"
PORT = 21
USER = "admin"
PWD = "admin"
REMOTE_DIR = "/public_exchange/xxx/temp"
REMOTE_FILE = "clipboard.txt"

CLIPBOARD_WAIT_TIMEOUT = 1.5
CLIPBOARD_POLL_INTERVAL = 0.05
COPY_RETRY_COUNT = 5
COPY_RETRY_DELAY = 0.15
KEY_RELEASE_TIMEOUT = 2.0
WINDOW_SETTLE_DELAY = 0.2

HOTKEY_UPLOAD_ID = 1
HOTKEY_DOWNLOAD_ID = 2
HOTKEY_EXIT_ID = 3
HOTKEY_EXIT_MODIFIERS = win32con.MOD_CONTROL | win32con.MOD_ALT
HOTKEY_EXIT_VK = ord('Q')
MUTEX_NAME = 'Global\\ClipboardFtpHotkeyDaemon'

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32
ACTION_LOCK = threading.Lock()


class MSG(ctypes.Structure):
    _fields_ = [
        ('hwnd', wintypes.HWND),
        ('message', wintypes.UINT),
        ('wParam', wintypes.WPARAM),
        ('lParam', wintypes.LPARAM),
        ('time', wintypes.DWORD),
        ('pt', wintypes.POINT),
        ('lPrivate', wintypes.DWORD),
    ]


class FtpClient(object):
    def __init__(self, host, port, username, passwd):
        self.ftp = self.__connect(host, port, username, passwd)
        try:
            self.ftp.cwd(REMOTE_DIR)
        except Exception:
            self.ftp.mkd(REMOTE_DIR)
            self.ftp.cwd(REMOTE_DIR)
        self.bufsize = 1024

    def __connect(self, host, port, username, passwd):
        ftp = FTP()
        ftp.set_debuglevel(0)
        ftp.connect(host, port)
        ftp.login(username, passwd)
        return ftp

    def downloadfile(self, remotepath):
        chunk_io = io.BytesIO()
        self.ftp.retrbinary('RETR ' + remotepath, chunk_io.write, self.bufsize)
        self.ftp.delete(remotepath)
        payload = chunk_io.getvalue()
        try:
            return payload.decode('utf-8')
        except UnicodeDecodeError:
            try:
                return payload.decode('gb2312')
            except UnicodeDecodeError:
                return payload

    def uploadfile(self, remotepath, data):
        chunk_io = io.BytesIO(data)
        self.ftp.storbinary('STOR ' + remotepath, chunk_io, self.bufsize)

    def close(self):
        self.ftp.close()


def report_error(message):
    user32.MessageBoxW(None, message, 'Clipboard FTP', 0x10)


def send_hotkey(vk_code):
    win32api.keybd_event(win32con.VK_CONTROL, 0, 0, 0)
    win32api.keybd_event(vk_code, 0, 0, 0)
    win32api.keybd_event(vk_code, 0, win32con.KEYEVENTF_KEYUP, 0)
    win32api.keybd_event(win32con.VK_CONTROL, 0, win32con.KEYEVENTF_KEYUP, 0)
    time.sleep(0.1)


def get_clipboard_sequence_number():
    return user32.GetClipboardSequenceNumber()


def wait_for_clipboard_change(before_sequence, timeout=CLIPBOARD_WAIT_TIMEOUT):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if get_clipboard_sequence_number() != before_sequence:
            time.sleep(CLIPBOARD_POLL_INTERVAL)
            return
        time.sleep(CLIPBOARD_POLL_INTERVAL)
    raise TimeoutError('Ctrl+C 后剪贴板没有更新')


def get_foreground_window():
    return user32.GetForegroundWindow()


def wait_for_key_release(vk_code, timeout=KEY_RELEASE_TIMEOUT):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if not (user32.GetAsyncKeyState(vk_code) & 0x8000):
            time.sleep(CLIPBOARD_POLL_INTERVAL)
            return
        time.sleep(CLIPBOARD_POLL_INTERVAL)


def activate_window(hwnd):
    if hwnd:
        user32.SetForegroundWindow(hwnd)
        time.sleep(WINDOW_SETTLE_DELAY)


def open_clipboard_with_retry():
    deadline = time.time() + 1.0
    while time.time() < deadline:
        try:
            win32clipboard.OpenClipboard()
            return
        except Exception:
            time.sleep(CLIPBOARD_POLL_INTERVAL)
    raise RuntimeError('剪贴板正忙，请稍后重试')


def read_clipboard_payload():
    open_clipboard_with_retry()
    try:
        if win32clipboard.IsClipboardFormatAvailable(win32con.CF_DIB):
            return win32clipboard.GetClipboardData(win32con.CF_DIB)
        if win32clipboard.IsClipboardFormatAvailable(win32con.CF_UNICODETEXT):
            return win32clipboard.GetClipboardData(win32con.CF_UNICODETEXT)
        return None
    finally:
        win32clipboard.CloseClipboard()


def write_clipboard_payload(data):
    open_clipboard_with_retry()
    try:
        win32clipboard.EmptyClipboard()
        if isinstance(data, str):
            win32clipboard.SetClipboardData(win32con.CF_UNICODETEXT, data)
        elif isinstance(data, bytes):
            win32clipboard.SetClipboardData(win32con.CF_DIB, data)
        else:
            raise RuntimeError('复制到剪贴板出错')
    finally:
        win32clipboard.CloseClipboard()


def clipboard_payload_to_bytes(data):
    if isinstance(data, str):
        return data.encode('utf-8')
    if isinstance(data, bytes):
        return data
    raise RuntimeError('未检测到可上传的剪贴板内容')


def capture_selected_payload():
    target_window = get_foreground_window()
    wait_for_key_release(win32con.VK_F6)
    time.sleep(WINDOW_SETTLE_DELAY)
    for _ in range(COPY_RETRY_COUNT):
        before_sequence = get_clipboard_sequence_number()
        activate_window(target_window)
        send_hotkey(ord('C'))
        try:
            wait_for_clipboard_change(before_sequence)
            payload = read_clipboard_payload()
            if payload is not None:
                return payload
        except TimeoutError:
            time.sleep(COPY_RETRY_DELAY)
    raise TimeoutError('未检测到选中文本被复制到剪贴板，请保持目标窗口为前台并选中文本后再按 F6')


def upload_selected_to_ftp():
    payload = capture_selected_payload()
    ftp = FtpClient(IP, PORT, USER, PWD)
    try:
        ftp.uploadfile(REMOTE_FILE, clipboard_payload_to_bytes(payload))
    finally:
        ftp.close()


def download_and_paste():
    target_window = get_foreground_window()
    ftp = FtpClient(IP, PORT, USER, PWD)
    try:
        payload = ftp.downloadfile(REMOTE_FILE)
    finally:
        ftp.close()
    write_clipboard_payload(payload)
    wait_for_key_release(win32con.VK_F7)
    activate_window(target_window)
    send_hotkey(ord('V'))


def run_action(action):
    if not ACTION_LOCK.acquire(False):
        return

    def worker():
        try:
            action()
        except Exception as exc:
            report_error(str(exc))
        finally:
            ACTION_LOCK.release()

    threading.Thread(target=worker, daemon=True).start()


def register_hotkey(hotkey_id, modifiers, vk_code):
    if not user32.RegisterHotKey(None, hotkey_id, modifiers, vk_code):
        raise RuntimeError(f'热键注册失败: id={hotkey_id}, vk={vk_code}')


def unregister_hotkeys():
    user32.UnregisterHotKey(None, HOTKEY_UPLOAD_ID)
    user32.UnregisterHotKey(None, HOTKEY_DOWNLOAD_ID)
    user32.UnregisterHotKey(None, HOTKEY_EXIT_ID)


def ensure_single_instance():
    mutex = win32event.CreateMutex(None, False, MUTEX_NAME)
    if win32api.GetLastError() == winerror.ERROR_ALREADY_EXISTS:
        raise RuntimeError('Clipboard FTP 后台程序已在运行')
    return mutex


def message_loop():
    register_hotkey(HOTKEY_UPLOAD_ID, 0, win32con.VK_F6)
    register_hotkey(HOTKEY_DOWNLOAD_ID, 0, win32con.VK_F7)
    register_hotkey(HOTKEY_EXIT_ID, HOTKEY_EXIT_MODIFIERS, HOTKEY_EXIT_VK)
    msg = MSG()
    try:
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) != 0:
            if msg.message == win32con.WM_HOTKEY:
                hotkey_id = int(msg.wParam)
                if hotkey_id == HOTKEY_UPLOAD_ID:
                    run_action(upload_selected_to_ftp)
                elif hotkey_id == HOTKEY_DOWNLOAD_ID:
                    run_action(download_and_paste)
                elif hotkey_id == HOTKEY_EXIT_ID:
                    break
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))
    finally:
        unregister_hotkeys()


def main():
    mutex = ensure_single_instance()
    try:
        message_loop()
    finally:
        win32api.CloseHandle(int(mutex))


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        report_error(str(exc))
        sys.exit(1)
