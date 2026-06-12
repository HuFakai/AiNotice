# Docker网络问题解决方案

## 问题描述

当您在1Panel服务器上部署时遇到以下错误：

```
failed to solve: DeadlineExceeded: python:3.9-slim: failed to resolve source metadata for docker.io/library/python:3.9-slim: failed to do request: Head "https://registry-1.docker.io/v2/library/python/manifests/3.9-slim": dial tcp 174.37.243.85:443: i/o timeout
```

这表明服务器无法访问Docker Hub官方镜像仓库。

## 解决方案

### 🎯 推荐方案：离线部署（最稳定）

**适用场景**：服务器网络受限，无法访问Docker Hub

```bash
cd /opt/miapi-platform
chmod +x deploy-offline.sh
./deploy-offline.sh
```

**优势**：
- ✅ 不依赖Docker，使用系统Python环境
- ✅ 自动安装配置MySQL数据库
- ✅ 创建系统服务，开机自启
- ✅ 完全离线运行，不受网络限制

### 🔧 备用方案1：配置Docker代理

如果您有可用的代理服务器：

```bash
# 创建Docker代理配置
sudo mkdir -p /etc/systemd/system/docker.service.d

# 配置代理
sudo tee /etc/systemd/system/docker.service.d/proxy.conf > /dev/null << 'EOF'
[Service]
Environment="HTTP_PROXY=http://your-proxy:port"
Environment="HTTPS_PROXY=http://your-proxy:port"
Environment="NO_PROXY=localhost,127.0.0.1"
EOF

# 重启Docker
sudo systemctl daemon-reload
sudo systemctl restart docker

# 重新部署
./deploy-simple.sh
```

### 🔧 备用方案2：使用国内镜像源

```bash
# 配置国内Docker镜像源
sudo tee /etc/docker/daemon.json > /dev/null << 'EOF'
{
  "registry-mirrors": [
    "https://docker.mirrors.ustc.edu.cn",
    "https://hub-mirror.c.163.com",
    "https://mirror.baidubce.com"
  ],
  "max-concurrent-downloads": 10,
  "log-driver": "json-file",
  "log-level": "warn",
  "log-opts": {
    "max-size": "10m",
    "max-file": "3"
  }
}
EOF

# 重启Docker
sudo systemctl restart docker

# 等待服务启动
sleep 10

# 测试镜像拉取
docker pull hello-world

# 如果成功，重新部署
./deploy-simple.sh
```

### 🔧 备用方案3：手动下载镜像

如果有其他可以访问Docker Hub的机器：

```bash
# 在可访问Docker Hub的机器上
docker pull python:3.9-slim
docker pull mysql:8.0
docker save python:3.9-slim mysql:8.0 > miapi-images.tar

# 传输到目标服务器
scp miapi-images.tar user@your-server:/opt/miapi-platform/

# 在目标服务器上加载镜像
cd /opt/miapi-platform
docker load < miapi-images.tar

# 重新部署
./deploy-simple.sh
```

## 验证部署

部署完成后，验证服务是否正常运行：

```bash
# 检查服务状态（离线部署）
sudo systemctl status miapi

# 检查Docker容器状态（Docker部署）
docker-compose ps

# 测试API接口
curl http://localhost:9000/health

# 查看日志
# 离线部署
sudo journalctl -u miapi -f

# Docker部署
docker-compose logs -f
```

## 常见问题

### Q: 离线部署时MySQL安装失败？

**A**: 手动安装MySQL：

```bash
# CentOS/RHEL
sudo yum install -y mysql-server
sudo systemctl start mysqld
sudo systemctl enable mysqld

# Ubuntu/Debian
sudo apt update
sudo apt install -y mysql-server
sudo systemctl start mysql
sudo systemctl enable mysql
```

### Q: Python依赖安装失败？

**A**: 配置pip国内源：

```bash
pip3 config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple
pip3 config set global.trusted-host pypi.tuna.tsinghua.edu.cn
```

### Q: 服务启动后无法访问？

**A**: 检查防火墙设置：

```bash
# 检查防火墙状态
sudo firewall-cmd --list-ports

# 开放9000端口
sudo firewall-cmd --permanent --add-port=9000/tcp
sudo firewall-cmd --reload
```

## 总结

对于网络受限的1Panel服务器，**强烈推荐使用离线部署方案**，这是最稳定可靠的部署方式，不受网络环境影响。