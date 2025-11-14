# Claude Code 集群配置指南

> 通过 Windows 代理服务器在无外网访问的集群上使用 Claude Code

## 📋 目录

- [架构概述](#架构概述)
- [快速开始](#快速开始)
- [Windows 端配置](#windows-端配置)
- [集群端配置](#集群端配置)
- [日常使用](#日常使用)
- [故障排查](#故障排查)
- [附录](#附录)

---

## 架构概述

```
集群服务器 (无外网) ─┐
                     ├─→ Windows 代理服务 (NSSM) ─→ LetsVPN ─→ 外网
其他服务器          ─┘      ↓ (0000端口)
                        Python 代理脚本
```

**核心思路：**
- Windows 电脑通过 LetsVPN 访问外网
- NSSM 管理 Python 代理脚本作为 Windows 服务
- 集群服务器通过 Windows 代理访问 Anthropic API

---

## 快速开始

### 前置条件

**Windows 端：**
- ✅ Python 3.9+
- ✅ LetsVPN（或其他 VPN）
- ✅ NSSM（服务管理工具）
- ✅ 管理员权限

**集群端：**
- ✅ CentOS 7 / Ubuntu 或其他 Linux 发行版
- ✅ 能访问 Windows 电脑内网 IP
- ✅ 无需 sudo 权限

### 30 秒快速安装

**Windows 端：**
```powershell
# 1. 下载代理脚本（已提供）
# 2. 安装 NSSM 服务（见下文）
# 3. 启动服务
```

**集群端：**
```bash
# 配置代理 → 安装 Node.js → 安装 Claude Code
curl -s https://[配置脚本URL] | bash
```

---

## Windows 端配置

### 1. 准备代理脚本

将 `proxy.py` 放置在固定位置：
```
C:\Users\xxx\proxy.py
```

### 2. 安装 NSSM

```powershell
# 下载 NSSM
# https://nssm.cc/download
# 解压到 C:\nssm-2.24\
```

### 3. 注册 Windows 服务

**以管理员身份运行 PowerShell：**

```powershell
# 查找 Python 路径
(Get-Command python).Path
# 记录输出，例如: C:\xxx\python.exe

# 安装服务（会弹出配置窗口）
C:\nssm-2.24\win64\nssm.exe install PythonProxy
```

**配置窗口填写：**

| 字段 | 值 |
|------|-----|
| **Path** | `C:\xxx\python.exe` |
| **Startup directory** | `C:\nssm-2.24\` |
| **Arguments** | `proxy.py` |
| **Display name** | `Python Proxy Server` |
| **Startup type** | `Automatic` |

### 4. 启动服务

```powershell
# 启动服务
C:\nssm-2.24\win64\nssm.exe start PythonProxy

# 验证服务状态
C:\nssm-2.24\win64\nssm.exe status PythonProxy
# 输出: SERVICE_RUNNING

# 测试代理
curl --proxy http://000.0.0.0:0000 https://www.google.com
```



## 集群端配置

### 环境信息

- **Windows IP**: `10.00.00.000` （根据实际情况修改）
- **代理端口**: `0000`
- **集群系统**: CentOS 7 (glibc 2.17)

### 配置步骤

#### 1. 测试代理连通性

```bash
# 测试网络
ping 10.00.00.000

# 临时设置代理测试
export http_proxy="http://10.00.00.000:0000"
export https_proxy="http://10.00.00.000:0000"

# 验证外网访问
curl -I https://www.google.com
# 应该返回: HTTP/1.0 200 Connection established
```

#### 2. 永久配置代理

```bash
# 添加到 ~/.bashrc
cat >> ~/.bashrc << 'EOF'

# ==================== 代理配置 ====================
export http_proxy="http://10.00.00.000:0000"
export https_proxy="http://10.00.00.000:0000"
export no_proxy="localhost,000.0.0.1,10.*,172.*,192.168.*"
EOF

# 使配置生效
source ~/.bashrc
```

#### 3. 安装 Node.js（glibc 2.17 兼容版本）

```bash
# 创建安装目录
mkdir -p ~/.local && cd ~/.local

# 下载 glibc 2.17 兼容版本
curl -o node.tar.gz \
  https://unofficial-builds.nodejs.org/download/release/v20.18.0/node-v20.18.0-linux-x64-glibc-217.tar.gz

# 解压并重命名
tar -xzf node.tar.gz
mv node-v20.18.0-linux-x64-glibc-217 node
rm node.tar.gz

# 添加到 PATH
echo 'export PATH="$HOME/.local/node/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc

# 验证安装
node --version  # v20.18.0
npm --version   # 10.8.2
```

#### 4. 安装 Claude Code

```bash
# 全局安装
npm install -g @anthropic-ai/claude-code

# 验证安装
claude --version  # 2.0.37 (Claude Code)
```

#### 5. 配置 API 认证

```bash
# 添加 API 配置到 ~/.bashrc
cat >> ~/.bashrc << 'EOF'

# ==================== Claude Code 配置 ====================
export ANTHROPIC_AUTH_TOKEN="******key******"
export ANTHROPIC_BASE_URL="https://www.********.org/api"
export CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC="1"
EOF

# 使配置生效
source ~/.bashrc
```

**注意：** 将 `你的_API_TOKEN` 替换为实际的 API Token

#### 6. 测试 Claude Code

```bash
# 测试翻译
echo "Hello, how are you?" | claude -p "Translate to Chinese"

# 交互式使用
claude

# 帮助信息
claude --help
```

---

## 日常使用

### Windows 端

**完全自动化，无需操作！**

服务已配置为开机自动启动，后台运行。

**查看服务状态：**
```powershell
# 方法 1: 使用 NSSM
C:\nssm-2.24\win64\nssm.exe status PythonProxy

# 方法 2: Windows 服务管理器
services.msc
# 找到 "Python Proxy Server"
```

**管理服务：**
```powershell
# 启动
C:\nssm-2.24\win64\nssm.exe start PythonProxy

# 停止
C:\nssm-2.24\win64\nssm.exe stop PythonProxy

# 重启
C:\nssm-2.24\win64\nssm.exe restart PythonProxy
```

### 集群端

**直接使用 Claude Code：**

```bash
# 交互模式
claude

# 命令模式
claude -p "你的提示词" < input.txt

# 管道模式
cat file.py | claude -p "解释这段代码"
```

**VSCode 集成：**

如果使用 VSCode 远程连接集群，可以安装 Claude Code 扩展，自动使用命令行的 `claude`。

---

## 故障排查

### Windows 端

#### 问题：服务无法启动

```powershell
# 1. 检查服务状态
C:\nssm-2.24\win64\nssm.exe status PythonProxy

# 2. 查看错误日志
notepad C:\Users\THINK\proxy_server.log

# 3. 手动测试脚本
python C:\Users\THINK\proxy.py

# 4. 重新安装服务
C:\nssm-2.24\win64\nssm.exe remove PythonProxy confirm
C:\nssm-2.24\win64\nssm.exe install PythonProxy
```

#### 问题：端口被占用

```powershell
# 查看 0000 端口占用情况
netstat -ano | findstr "0000"

# 结束占用进程（记下 PID 后）
taskkill /PID <PID> /F
```

#### 问题：代理不工作

```powershell
# 确认 LetsVPN 已连接

# 测试本地代理
curl --proxy http://000.0.0.1:0000 https://www.google.com

# 检查防火墙
# Windows 防火墙 → 入站规则 → 允许 0000 端口
```

### 集群端

#### 问题：无法访问外网

```bash
# 1. 检查代理配置
echo $http_proxy
echo $https_proxy

# 2. 测试 Windows 连通性
ping 10.00.00.000

# 3. 测试代理
curl -v --proxy http://10.00.00.000:0000 https://www.google.com

# 4. 重新加载配置
source ~/.bashrc
```

#### 问题：claude 命令找不到

```bash
# 1. 检查 PATH
echo $PATH | grep node

# 2. 查看安装位置
ls -la ~/.local/node/bin/ | grep claude

# 3. 手动添加 PATH
export PATH="$HOME/.local/node/bin:$PATH"

# 4. 验证 npm 配置
npm config get prefix
```

#### 问题：API 调用失败

```bash
# 1. 检查环境变量
echo $ANTHROPIC_AUTH_TOKEN
echo $ANTHROPIC_BASE_URL

# 2. 测试 API 可达性
curl -I https://www.*********.org/api

# 3. 重新加载配置
source ~/.bashrc

# 4. 查看 Claude Code 日志
claude --version
```

---

## 附录

### A. 完整配置文件

#### Windows: `proxy.py`

见项目文件 `proxy.py`

#### 集群: `~/.bashrc` (追加内容)

```bash
# ==================== 代理配置 ====================
export http_proxy="http://10.00.00.000:0000"
export https_proxy="http://10.00.00.000:0000"
export no_proxy="localhost,000.0.0.1,10.*,172.*,192.168.*"

# ==================== Node.js 配置 ====================
export PATH="$HOME/.local/node/bin:$PATH"

# ==================== Claude Code 配置 ====================
export ANTHROPIC_AUTH_TOKEN="你的_API_TOKEN"
export ANTHROPIC_BASE_URL="https://www.*********.org/api"
export CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC="1"
```

### B. NSSM 服务配置

| 配置项 | 值 |
|--------|-----|
| 服务名称 | PythonProxy |
| 显示名称 | Python Proxy Server |
| 可执行文件 | `C:\xxx\python.exe` |
| 工作目录 | `C:\nssm-2.24` |
| 参数 | `proxy.py` |
| 启动类型 | 自动 |

### C. 网络架构图

```
┌───────────────────────────────────────────────────────────── ┐
│                        外网 (Internet)                       │
│                 ↑                           ↑                │
│                 │                           │                │
│           LetsVPN                    Anthropic API           │
└─────────────────┼───────────────────────────┼────────────────┘
                  │                           │
┌─────────────────┼───────────────────────────┼────────────────┐
│  Windows 电脑   │                           │                │
│  (10.00.00.000) │                           │                │
│                 │                           │                │
│  ┌──────────────▼────────────┐              │                │
│  │  NSSM 服务管理            │              │                │
│  │  └─ Python 代理脚本       │              │                │
│  │     监听: 0.0.0.0:0000    │              │                │
│  └───────────────┬───────────┘              │                │
│                  │                           │                │
└──────────────────┼───────────────────────────┼────────────────┘
                   │                           │
                   │ HTTP Proxy                │ API Calls
                   │                           │
┌──────────────────┼───────────────────────────┼────────────────┐
│  集群内网        │                           │                │
│                  │                           │                │
│  ┌───────────────▼─────────┐  ┌─────────────▼──────────────┐ │
│  │ 集群服务器 (hpc000)      │  │ Ubuntu 电脑 (localhost-jhl)│ │
│  │                         │  │                            │ │
│  │ • 配置代理环境变量       │  │ • 配置代理环境变量           │ │
│  │ • 安装 Node.js          │  │ • 安装 Node.js              │ │
│  │ • 安装 Claude Code      │  │ • 安装 Claude Code          │ │
│  │ • 配置 API Key          │  │ • 配置 API Key              │ │
│  └─────────────────────────┘  └────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

### D. 常用命令速查

#### Windows PowerShell

```powershell
# 服务管理
C:\nssm-2.24\win64\nssm.exe status PythonProxy    # 查看状态
C:\nssm-2.24\win64\nssm.exe start PythonProxy     # 启动
C:\nssm-2.24\win64\nssm.exe stop PythonProxy      # 停止
C:\nssm-2.24\win64\nssm.exe restart PythonProxy   # 重启
C:\nssm-2.24\win64\nssm.exe edit PythonProxy      # 编辑配置

# 日志查看
Get-Content C:\Users\THINK\proxy_server.log -Wait -Tail 50

# 测试代理
curl --proxy http://000.0.0.1:0000 https://www.google.com

# 查看端口
netstat -ano | findstr "0000"
```

#### 集群 Bash

```bash
# 环境管理
source ~/.bashrc                    # 重新加载配置
echo $http_proxy                    # 查看代理配置
echo $ANTHROPIC_AUTH_TOKEN          # 查看 API Token

# 网络测试
ping 10.00.00.000                   # 测试 Windows 连通性
curl -I https://www.google.com      # 测试外网访问

# Node.js & npm
node --version                      # 查看 Node.js 版本
npm --version                       # 查看 npm 版本
npm list -g --depth=0               # 查看全局包

# Claude Code
claude --version                    # 查看版本
claude --help                       # 查看帮助
claude                              # 启动交互模式
```

### E. 资源与链接

**工具下载：**
- NSSM: https://nssm.cc/download
- Node.js (unofficial builds): https://unofficial-builds.nodejs.org/
- Claude Code: https://www.npmjs.com/package/@anthropic-ai/claude-code

**文档参考：**
- Anthropic API: https://docs.anthropic.com/
- Claude Code 文档: https://docs.claude.com/en/docs/claude-code

**第三方服务：**
- *********.org: https://www.*********.org/

### F. 性能参考

**Windows 代理服务：**
- 内存占用: ~8-15 MB
- CPU 占用: <1% (空闲时)
- 响应延迟: <10ms (内网)

**集群 Claude Code：**
- 安装大小: ~50 MB
- 内存占用: ~30-50 MB (运行时)

### G. 安全建议

1. **API Key 保护**
   - 不要提交到代码仓库
   - 定期更换 Token
   - 使用 `chmod 600 ~/.bashrc` 保护配置文件

2. **代理访问控制**
   - 配置 Windows 防火墙限制访问 IP
   - 考虑使用内网专用网段
   - 定期检查代理日志

3. **服务监控**
   - 定期查看 `proxy_server.log`
   - 监控异常请求
   - 关注统计报告中的错误次数

---

## 📞 联系与支持

**问题反馈：**
- 查看日志文件排查问题
- 参考故障排查章节
- 记录详细错误信息

**版本信息：**
- 文档版本: 1.0
- 更新日期: 2025-11-14
- 适用环境: Windows + CentOS 7

---

## 📄 许可证

本配置方案基于实际部署经验整理，供内部使用和参考。

---

**🎉 配置完成后，享受 Claude Code 在集群上的便利吧！**
