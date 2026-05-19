# Clipboard FTP

通过 FTP 服务实现的跨平台远程剪贴板共享工具

---

## 功能特性

- ✅ 支持文本和图片的剪贴板共享
- ✅ 热键快速操作,后台常驻
- ✅ 自动处理多种编码格式 (UTF-8/GBK)
- ✅ 跨平台支持 (Windows/Linux/Mac/Android/iOS)

---

## 使用方式

### 启动守护进程

```bash
# 安装依赖
pip install -r requirements.txt

# 启动守护进程
python hotkey_daemon.py
```

### 热键操作

- `F6` — 上传选中内容到 FTP (自动复制选中文本)
- `F7` — 从 FTP 下载并粘贴 (自动粘贴到当前位置)
- `Ctrl+Alt+Q` — 退出守护进程

### 工作流程

1. 在任意应用中选中文本
2. 按 `F6` 自动上传到 FTP
3. 切换到另一台设备
4. 按 `F7` 自动下载并粘贴

---

## 配置说明

修改 `hotkey_daemon.py` 中的 FTP 连接参数:

```python
IP = "your.ftp.server.com"     # FTP 服务器地址
PORT = 21                      # FTP 端口
USER = "your_username"         # FTP 用户名
PWD = "your_password"          # FTP 密码
REMOTE_DIR = "/path/to/remote/dir"  # 远程目录
REMOTE_FILE = "clipboard.txt"  # 剪贴板文件名
```

---

## 环境要求

### Python 依赖

```bash
pip install -r requirements.txt
```

**依赖包**:
- `pywin32` (Windows 剪贴板和热键支持)

### FTP 服务器

你需要一个可访问的 FTP 服务器:

- **局域网**: 在路由器或 NAS 上开启 FTP 服务
- **公网**: 使用云服务器搭建 FTP (需要公网 IP)
- **学生用户**: 使用学校分配的 FTP 空间

**权限要求**: FTP 用户需要有上传、下载、删除文件的权限

---

## 平台支持

| 平台 | 状态 | 说明 |
|------|------|------|
| Windows | ✅ 完整支持 | 支持热键守护进程 |
| Linux | ✅ 支持 | 使用 `clip_mac_linux.py` |
| Mac OS | ✅ 支持 | 使用 `clip_mac_linux.py` |
| Android | ✅ 支持 | 需要 QPython + androidhelper 模块 |
| iOS | ✅ 支持 | 需要 Pythonista + clipboard 模块 |

---

## 打包为可执行文件

使用 PyInstaller 打包成独立 exe:

```bash
# 打包守护进程
pyinstaller --onefile --noconsole hotkey_daemon.py

# 打包后的文件在 dist/ 目录
```

---

## 注意事项

1. **安全性**: FTP 传输未加密,不建议传输敏感信息
2. **网络要求**: 需要稳定的网络连接到 FTP 服务器
3. **防火墙**: 确保 FTP 端口 (默认 21) 未被防火墙阻止
4. **编码兼容**: 自动处理 UTF-8 和 GBK 编码,支持中文
5. **单实例运行**: 守护进程使用互斥锁,同时只能运行一个实例

---

## 常见问题

### Q: 热键不生效?
A: 确保守护进程正在运行,检查是否有其他程序占用了 F6/F7 热键

### Q: 提示"剪贴板正忙"?
A: 关闭其他占用剪贴板的程序 (如截图工具、剪贴板管理器)

### Q: FTP 连接失败?
A: 检查网络连接、FTP 服务器地址、用户名密码是否正确

### Q: 中文乱码?
A: 脚本会自动尝试 UTF-8 和 GBK 编码,如仍有问题请检查 FTP 服务器编码设置

---

## License

MIT License

---

## 致谢

创建起初是为了在内外网快速传输剪贴板内容,不需要用文件来传输 

如果觉得有用,欢迎 Star ⭐
