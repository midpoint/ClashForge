FROM python:3.10.10-slim-bullseye

# 设置工作目录
WORKDIR /app

# 复制文件到工作目录
ADD ClashForge.py .
ADD clash-linux .
ADD requirements.txt .
ADD WebUI.py .
ADD input/subscriptions.txt ./input/subscriptions.txt

# 安装依赖
RUN pip3 install -r requirements.txt && \
    apt-get update && \
    apt-get -f install -y --no-install-recommends \
    chromium \
    libpq-dev \
    gcc \
    libc6-dev \
    libxcursor1 \
    libxss1 \
    libpangocairo-1.0-0 \
    libgtk-3-0 && \
    rm -rf /var/lib/apt/lists/* && \
    rm -rf /usr/local/lib/python3.10/site-packages/distutils-precedence.pth && \
    export PYPPETEER_CHROMIUM_REVISION=1181205 && \
    pyppeteer-install

# 暴露端口
EXPOSE 8501

# 运行 Streamlit
CMD ["python3", "-m", "streamlit", "run", "WebUI.py"]
