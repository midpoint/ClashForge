import streamlit as st
import os
import io
from contextlib import redirect_stdout
import time
import asyncio
import pandas as pd
import yaml
import requests
import json
import streamlit.components.v1 as components

# 导入ClashForge模块
from ClashForge import (
    generate_clash_config, merge_lists, switch_proxy,
    filter_by_types_alt, read_txt_files, read_yaml_files, read_private_links,
    start_clash, proxy_clean, kill_clash,
    ClashConfig, download_and_extract_latest_release,
    upload_and_generate_urls, TIMEOUT
)

def capture_output(func, *args, **kwargs):
    """捕获函数的标准输出并返回函数结果"""
    f = io.StringIO()
    with redirect_stdout(f):
        result = func(*args, **kwargs)
    return result

# 设置页面配置
st.set_page_config(
    page_title="ClashForge Web",
    page_icon="🌐",
    layout="wide",
    initial_sidebar_state="expanded",
)

# 添加一些基本样式
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        color: #1E88E5;
        text-align: center;
        margin-bottom: 1rem;
    }
    .footer {
        text-align: center;
        margin-top: 2rem;
        padding: 1rem;
        font-size: 0.9rem;
        color: #666;
    }
    .scrolling-text-container {
        background-color: #f0f8ff;
        border-left: 4px solid #1E88E5;
        padding: 10px 15px;
        margin-bottom: 20px;
        border-radius: 4px;
        box-shadow: 0 2px 5px rgba(0,0,0,0.1);
        overflow: hidden;
        position: relative;
        width: 100%;
    }
    .marquee {
        width: 100%;
        overflow: hidden;
        position: relative;
    }
    .marquee-content {
        display: flex;
        animation: marquee 20s linear infinite;
        white-space: nowrap;
    }
    .marquee-item {
        flex-shrink: 0;
        padding: 0 20px;
    }
    @keyframes marquee {
        0% { transform: translateX(0); }
        100% { transform: translateX(-100%); }
    }
</style>
""", unsafe_allow_html=True)

# 滚动提示信息函数
def show_scrolling_tips():
    # 计算距离下一次重置的剩余时间
    current_time = time.time()
    # 假设重置发生在每10分钟，即每小时的0, 10, 20, 30, 40, 50分钟
    current_minute = int(time.strftime("%M", time.localtime(current_time)))
    current_second = int(time.strftime("%S", time.localtime(current_time)))
    
    # 计算下一个10分钟整点
    next_reset_minute = (current_minute // 10 + 1) * 10
    if next_reset_minute == 60:
        next_reset_minute = 0  # 下一个小时
    
    # 计算剩余分钟和秒数
    if next_reset_minute == 0:
        # 如果下一个重置点是下一个小时的0分，则剩余分钟是60-current_minute-1
        remaining_minutes = 60 - current_minute - 1
    else:
        remaining_minutes = next_reset_minute - current_minute - 1
    
    remaining_seconds = 60 - current_second
    
    # 正确处理边界情况
    if remaining_seconds == 60:
        remaining_seconds = 0
        remaining_minutes += 1
    
    # 确保时间不会出现负数
    if remaining_minutes < 0:
        remaining_minutes = 0
        
    if remaining_seconds < 0:
        remaining_seconds = 0
    
    # 格式化剩余时间
    remaining_time = f"{remaining_minutes:01d}分{remaining_seconds:02d}秒"
    
    tips = [
        f"⏱️ 提示：本站仅供演示，每10分钟重置一次，下次重置将在 {remaining_time} 后，建议本地部署",
        "🔍 提示：延迟低不一定速度快，建议同时测试延迟和速，本站部署在香港VPS，带宽20Mbps，测试结果仅供参考 "
    ]

    # 使用新的轮播结构实现真正无缝的滚动
    tip_html = ""
    for tip in tips:
        tip_html += f'<div class="marquee-item">{tip}</div>'
    
    st.markdown(f"""
    <div class="scrolling-text-container">
        <div class="marquee">
            <div class="marquee-content">
                {tip_html}
                {tip_html}
                {tip_html}
                {tip_html}
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

# 设置文件路径
SETTINGS_FILE = "settings.json"

# 默认链接列表
DEFAULT_LINKS = [
	"https://proxypool.link/vmess/sub"
]

# 加载设置
def load_settings():
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"加载设置文件出错: {e}")
    return {"proxy_links": DEFAULT_LINKS, "delays": [], "subscription_links": {}}

# 保存设置
def save_settings(settings):
    try:
        with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
            json.dump(settings, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"保存设置文件出错: {e}")

# 局部更新设置：先读最新内容再写回，避免用旧字典覆盖其他键
def update_settings(**kwargs):
    settings = load_settings()
    settings.update(kwargs)
    save_settings(settings)
    return settings

# 保存测速结果
def save_speed_test_results(results, group_name, node_count):
    try:
        settings = load_settings()
        speed = {
            "results": results,
            "group_name": group_name,
            "node_count": node_count
        }
        settings["speed"] = speed
        save_settings(settings)
    except Exception as e:
        print(f"保存测速结果出错: {e}")

# 加载测速结果
def load_speed_test_results():
    speed = {"results": [], "group_name": "", "node_count": 0}
    if os.path.exists(SETTINGS_FILE):
        try:
            settings = load_settings()
            speed = settings.get("speed") if settings.get("speed") else speed
        except Exception as e:
            print(f"加载测速结果出错: {e}")
    return speed

# 自定义配置生成函数
def custom_generate_clash_config(links, nodes=None):
    """生成新配置；失败时恢复旧配置，避免一次拉取失败把可用配置删掉"""
    config_files = ("clash_config.yaml", "clash_config.yaml.json")
    backups = {}
    for name in config_files:
        if os.path.exists(name):
            with open(name, 'rb') as f:
                backups[name] = f.read()

    try:
        result = capture_output(generate_clash_config, links, nodes or [])
    except Exception:
        for name, data in backups.items():
            with open(name, 'wb') as f:
                f.write(data)
        raise

    # 生成失败时 generate_clash_config 不会写文件，恢复旧配置
    if not os.path.exists("clash_config.yaml") and backups:
        for name, data in backups.items():
            with open(name, 'wb') as f:
                f.write(data)
        print("新配置未生成，已恢复上一次的配置文件")
    elif os.path.exists("clash_config.yaml"):
        # 配置已更新，之前的订阅链接失效
        update_settings(subscription_links={})

    return result


# 本地 mihomo 的 HTTP 代理，测速必须走它才能测到节点本身
LOCAL_PROXIES = {
    "http": "http://127.0.0.1:7890",
    "https": "http://127.0.0.1:7890",
}


def test_proxy_speed(proxy_name, test_url="https://speed.cloudflare.com/__down?bytes=100000000", timeout=5):
    """测试代理下载速度（走本地 mihomo 代理）"""
    try:
        print(f"开始测试节点: {proxy_name}")

        # 测试延迟
        start_time = time.time()
        delay_url = "https://www.gstatic.com/generate_204"
        requests.get(delay_url, timeout=TIMEOUT, proxies=LOCAL_PROXIES)  # 延迟测试固定用3秒超时
        delay = int((time.time() - start_time) * 1000)  # 毫秒

        # 测试下载速度 (使用指定的时间段)
        start_time = time.time()
        total_length = 0
        download_time = 0

        # 使用流式请求，这样我们可以控制下载时间
        with requests.get(test_url, stream=True, timeout=10, proxies=LOCAL_PROXIES) as resp:
            if resp.status_code != 200:
                print(f"测速请求失败: {resp.status_code}")
                return {"speed": 0, "delay": delay}
                
            # 下载直到达到指定的时间
            for chunk in resp.iter_content(chunk_size=1024*1024):  # 1MB的块
                if chunk:
                    total_length += len(chunk)
                    current_time = time.time()
                    download_time = current_time - start_time
                    
                    # 如果已经下载了指定的时间，就停止
                    if download_time >= timeout:
                        break
                        
        # 计算速度：Bps -> MB/s
        if download_time > 0:
            speed_mbps = total_length / download_time / (1024 * 1024)
        else:
            speed_mbps = 0
            
        print(f"节点 {proxy_name} 下载速度: {speed_mbps:.2f} MB/s, 延迟: {delay}ms")
        return {"speed": speed_mbps, "delay": delay}
    
    except requests.exceptions.Timeout:
        print(f"节点 {proxy_name} 测试超时")
        return {"speed": 0, "delay": 0}
    except Exception as e:
        print(f"节点 {proxy_name} 测试出错: {str(e)}")
        return {"speed": 0, "delay": 0}

# 标题
st.markdown('<h1 class="main-header">ClashForge WebUI</h1>', unsafe_allow_html=True)

# 显示滚动提示
show_scrolling_tips()

# 主要功能标签页
tab1, tab2, tab3 = st.tabs(["获取节点", "测速", "配置编辑"])

# 初始化会话状态
if "clash_process" not in st.session_state:
    st.session_state.clash_process = None
if "clash_running" not in st.session_state:
    st.session_state.clash_running = False
if "delays" not in st.session_state:
    settings = load_settings()
    st.session_state.delays = settings.get("delays", [])

# 自动启动Clash
def is_clash_running():
    """检查Clash是否正在运行"""
    try:
        # 尝试访问Clash API来检查服务是否运行
        response = requests.get(f"http://127.0.0.1:9090/proxies", timeout=2)
        return response.status_code == 200
    except:
        return False

def _start_clash(rerun=True):
    # 尝试自动启动Clash（如果未运行）
    if os.path.exists("clash_config.yaml.json") and not st.session_state.clash_running and not is_clash_running():
        with st.spinner("正在启动Clash..."):
            st.session_state.clash_process = capture_output(start_clash)
            if st.session_state.clash_process:
                st.session_state.clash_running = True
                if rerun:
                    st.rerun()  # 重新运行应用以更新UI
            else:
                st.error("启动Clash失败，请检查Clash程序是否存在")

def _stop_clash(rerun=True):
    """停止 Clash，首先尝试使用进程对象，如果失败则使用 PID"""
    if st.session_state.clash_process:
        try:
            st.session_state.clash_process.kill()
            st.session_state.clash_process = None
            st.session_state.clash_running = False
            # print("Clash 已成功停止")
            if rerun:
                st.rerun()
        except Exception as e:
            print(f"停止 Clash 失败: {str(e)}")

    # 如果进程对象不可用，尝试使用 PID
    kill_clash()
    st.session_state.clash_process = None
    st.session_state.clash_running = False
    if rerun:
        st.rerun()

def _reconcile_clash_state():
    """mihomo 可能自行崩溃；发现进程已退出时同步刷新界面状态"""
    if not st.session_state.clash_running:
        return
    proc = st.session_state.clash_process
    if proc is not None and proc.poll() is not None:
        st.session_state.clash_process = None
        st.session_state.clash_running = False
    elif proc is None and not is_clash_running():
        st.session_state.clash_running = False

_reconcile_clash_state()

# 合并数据
def merge_node_data(data, delays):
    if not delays:
        return data
    # 创建 DataFrame
    df_data = pd.DataFrame(data)
    df_delays = pd.DataFrame(delays)
    
    # 合并
    df_merged = df_data.merge(
        df_delays,
        how="left",  # 保留所有 data 中的记录
        left_on="代理名称",
        right_on="name"
    )
    
    # 选择需要的列
    df_final = df_merged[["序号", "代理名称", "Delay_ms"]]
    
    # 按 Delay_ms 排序，NaN 排最后
    df_final = df_final.sort_values(by="Delay_ms", ascending=True, na_position="last")
    
    # 重新生成序号
    df_final["序号"] = range(1, len(df_final) + 1)
    
    return df_final

# 侧边栏
with st.sidebar:
    st.header("配置")
    
    # 代理类型过滤
    st.subheader("代理类型")
    proxy_types = st.multiselect(
        "选择允许的代理类型",
        ["ss", "ssr", "vmess", "vless", "trojan", "hysteria2", "hy2"],
        default=["ss", "ssr", "vmess", "vless", "trojan", "hysteria2", "hy2"]
    )
    
    # 确保input文件夹存在
    if not os.path.exists("input"):
        os.makedirs("input")
    
    # Clash 控制
    st.subheader("Clash 控制")
    
    # 显示当前状态
    status_col1, status_col2 = st.columns([1, 3])
    with status_col1:
        st.markdown("**状态:**")
    with status_col2:
        # 再次检查Clash状态以确保显示准确
        if st.session_state.clash_running or is_clash_running():
            # 如果检测到已运行但状态未更新，则更新状态
            if not st.session_state.clash_running and is_clash_running():
                st.session_state.clash_running = True
            st.markdown("🟢 **运行中**")
        else:
            st.markdown("🔴 **已停止**")
    
    # 控制按钮
    if not st.session_state.clash_running:
        if st.button("▶️ 启动 Clash"):
            _start_clash()
    else:
        if st.button("⏹️ 停止 Clash"):
            _stop_clash()
    
    # 工具
    st.subheader("工具")
    if st.button("下载最新版Clash"):
        with st.spinner("正在下载..."):
            capture_output(download_and_extract_latest_release)
            st.success("下载并解压完成")

# 获取节点标签页
with tab1:
    st.header("获取与管理节点")
    
    # 新增：文件上传功能
    st.subheader("上传配置文件")

    # 确保input文件夹存在
    if not os.path.exists("input"):
        os.makedirs("input")
    
    # 单列布局，文件上传后自动保存
    uploaded_files = st.file_uploader(
        "上传配置文件到input文件夹（自动保存）",
        accept_multiple_files=True,
        type=["yaml", "yml", "json", "txt"],
        help="支持YAML, JSON和TXT(每条代理节点占一行)格式的配置文件，上传后自动保存"
    )
    
    # 如果有文件被上传，自动保存
    if uploaded_files:
        saved_files = []
        for uploaded_file in uploaded_files:
            file_path = os.path.join("input", uploaded_file.name)
            
            # 检查文件是否已经保存过（通过会话状态跟踪）
            file_key = f"saved_{uploaded_file.name}_{uploaded_file.size}"
            if file_key not in st.session_state:
                # 读取上传的文件内容并保存
                with open(file_path, "wb") as f:
                    f.write(uploaded_file.getbuffer())
                saved_files.append(uploaded_file.name)
                
                # 标记为已保存
                st.session_state[file_key] = True
        
        # 如果有新保存的文件，显示成功消息
        if saved_files:
            st.success(f"已自动保存 {len(saved_files)} 个文件到 input 文件夹: {', '.join(saved_files)}")
    
    # 显示当前input文件夹中的文件
    if os.path.exists("input") and os.listdir("input"):
        with st.expander("已有配置文件", expanded=False):
            files = os.listdir("input")
            files = [f for f in files if f.endswith(('.yaml', '.yml', '.json', '.txt'))]
            
            if files:
                # 创建文件列表表格
                file_data = [{"文件名": file, "大小": f"{os.path.getsize(os.path.join('input', file)) / 1024:.1f} KB", 
                             "修改时间": time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(os.path.getmtime(os.path.join('input', file))))} 
                             for file in files]
                
                file_df = pd.DataFrame(file_data)
                st.dataframe(
                    file_df,
                    use_container_width=True,
                    column_config={
                        "文件名": st.column_config.TextColumn("文件名", width="large"),
                        "大小": st.column_config.TextColumn("大小", width="small"),
                        "修改时间": st.column_config.TextColumn("修改时间", width="medium")
                    },
                    hide_index=True
                )
                
                # 添加删除文件功能
                if st.button("清空input文件夹", key="clear_input_folder"):
                    kept = {"subscriptions.txt"}  # 公开订阅源是仓库文件，不随清空删除
                    for file in files:
                        if file in kept:
                            continue
                        try:
                            os.remove(os.path.join("input", file))
                        except Exception as e:
                            st.error(f"删除文件 {file} 失败: {str(e)}")

                    # 清除保存状态
                    for key in list(st.session_state.keys()):
                        if key.startswith("saved_"):
                            del st.session_state[key]

                    st.success("成功清空input文件夹（保留 subscriptions.txt）")
                    st.rerun()
            else:
                st.info("input文件夹中没有配置文件")
    
    # 移到此处：代理链接配置
    st.subheader("代理链接")
    # 加载设置
    settings = load_settings()
    # 创建回调函数来处理输入变化
    def on_text_change():
        # 当文本区域值发生变化时被调用
        links_list = [link.strip() for link in st.session_state.proxy_links_input.split("\n") if link.strip()]
        # 只更新 proxy_links，避免用旧字典覆盖其他设置
        update_settings(proxy_links=links_list)
    
    # 创建文本输入并绑定到会话状态和回调函数
    proxy_links = st.text_area(
        "输入代理链接 (每行一个)", 
        value="\n".join(settings["proxy_links"]), 
        height=150,
        key="proxy_links_input",
        on_change=on_text_change
    )

    # 添加更详细的格式说明
    with st.expander("📌  链接格式说明", expanded=False):
        st.markdown("""
        ### 支持的链接格式
        
        #### 基本订阅链接
        直接输入代理订阅链接，支持的订阅类型:
        - Clash 配置链接
        - V2ray 订阅链接
        - Trojan 订阅链接
        - Vmess 订阅链接
        - Vless 订阅链接
        - SS 订阅链接 (需添加 `|ss` 后缀)
        
        #### 特殊参数
        - **特殊格式转换**：
          - `链接|ss` - 将链接内容作为SS源处理
          - `链接|links` - 从链接内容中按行正则匹配节点
        
        #### 动态时间占位符
        支持在链接中使用时间占位符，会自动替换成当前日期/时间:
        - `{Y}` - 四位年份 (2023)
        - `{m}` - 两位月份 (01-12)
        - `{d}` - 两位日期 (01-31)
        - `{Ymd}` - 组合日期 (20230131)
        - `{Y_m_d}` - 下划线分隔 (2023_01_31)
        - `{Y-m-d}` - 横线分隔 (2023-01-31)
        
        #### GitHub 模糊匹配
        - `https://raw.githubusercontent.com/user/repo/main/{x}.yaml` - 匹配任意yaml文件

        #### 私密/付费订阅
        不要把付费订阅写进仓库，改用以下任一方式，启动时会自动合并：
        - 环境变量 `CLASHFORGE_PRIVATE_SUBSCRIPTIONS`（多个用换行/逗号分隔）
        - 环境变量 `CLASHFORGE_PRIVATE_SUBSCRIPTIONS_FILE` 指向仓库外的 txt
        - `input/` 目录下以 `_private.txt` 结尾的文件（已被 .gitignore 忽略）
        日志里订阅链接默认脱敏（只保留域名），需要完整链接调试时设置 `CLASHFORGE_LOG_URLS=1`

        #### 示例
        ```
        https://cdn.jsdelivr.net/gh/xiaoji235/airport-free/clash/naidounode.txt
        https://cdn.jsdelivr.net/gh/yangxiaoge/tvbox_cust@master/clash/Clash2.yml
        https://gy.xiaozi.us.kg/sub?token=lzj666
        https://igdux.top/5Hna
        https://mxlsub.me/newfull
        https://proxypool.link/ss/sub|ss
        https://proxypool.link/trojan/sub
        https://proxypool.link/vmess/sub
        https://raw.githubusercontent.com/Q3dlaXpoaQ/V2rayN_Clash_Node_Getter/refs/heads/main/APIs/sc0.yaml
        https://raw.githubusercontent.com/Q3dlaXpoaQ/V2rayN_Clash_Node_Getter/refs/heads/main/APIs/sc1.yaml
        https://raw.githubusercontent.com/Q3dlaXpoaQ/V2rayN_Clash_Node_Getter/refs/heads/main/APIs/sc2.yaml
        https://raw.githubusercontent.com/Q3dlaXpoaQ/V2rayN_Clash_Node_Getter/refs/heads/main/APIs/sc3.yaml
        https://raw.githubusercontent.com/Q3dlaXpoaQ/V2rayN_Clash_Node_Getter/refs/heads/main/APIs/sc4.yaml
        https://raw.githubusercontent.com/Roywaller/clash_subscription/refs/heads/main/clash_subscription.txt
        https://raw.githubusercontent.com/Ruk1ng001/freeSub/main/clash.yaml
        https://raw.githubusercontent.com/SoliSpirit/v2ray-configs/main/all_configs.txt
        https://raw.githubusercontent.com/a2470982985/getNode/main/clash.yaml
        https://raw.githubusercontent.com/aiboboxx/clashfree/refs/heads/main/clash.yml
        https://raw.githubusercontent.com/aiboboxx/v2rayfree/refs/heads/main/README.md
        https://raw.githubusercontent.com/anaer/Sub/refs/heads/main/clash.yaml
        https://raw.githubusercontent.com/chengaopan/AutoMergePublicNodes/master/list.yml
        https://raw.githubusercontent.com/ermaozi/get_subscribe/main/subscribe/clash.yml
        https://raw.githubusercontent.com/firefoxmmx2/v2rayshare_subcription/refs/heads/main/subscription/clash_sub.yaml
        https://raw.githubusercontent.com/free18/v2ray/refs/heads/main/c.yaml
        https://raw.githubusercontent.com/go4sharing/sub/main/sub.yaml
        https://raw.githubusercontent.com/leetomlee123/freenode/refs/heads/main/README.md
        https://raw.githubusercontent.com/ljlfct01/ljlfct01.github.io/refs/heads/main/节点
        https://raw.githubusercontent.com/mahdibland/SSAggregator/master/sub/sub_merge_yaml.yml
        https://raw.githubusercontent.com/mahdibland/ShadowsocksAggregator/master/Eternity.yml
        https://raw.githubusercontent.com/mahdibland/ShadowsocksAggregator/master/LogInfo.txt
        https://raw.githubusercontent.com/mai19950/clashgithub_com/refs/heads/main/site
        https://raw.githubusercontent.com/mfbpn/tg_mfbpn_sub/main/trial.yaml
        https://raw.githubusercontent.com/mfuu/v2ray/master/clash.yaml
        https://raw.githubusercontent.com/mgit0001/test_clash/refs/heads/main/heima.txt
        https://raw.githubusercontent.com/peasoft/NoMoreWalls/master/list.meta.yml
        https://raw.githubusercontent.com/peasoft/NoMoreWalls/master/list.yml
        https://raw.githubusercontent.com/Pawdroid/Free-servers/refs/heads/main/sub
        https://raw.githubusercontent.com/ripaojiedian/freenode/main/clash
        https://raw.githubusercontent.com/shahidbhutta/Clash/refs/heads/main/Router
        https://raw.githubusercontent.com/skka3134/Free-servers/refs/heads/main/README.md|linnks
        https://raw.githubusercontent.com/snakem982/proxypool/main/source/clash-meta.yaml
        https://raw.githubusercontent.com/vxiaov/free_proxies/main/clash/clash.provider.yaml
        https://raw.githubusercontent.com/wangyingbo/yb_clashgithub_sub/main/clash_sub.yml
        https://raw.githubusercontent.com/xiaoer8867785/jddy5/refs/heads/main/data/{Y_m_d}/{x}.yaml
        https://raw.githubusercontent.com/xiaoji235/airport-free/refs/heads/main/clash/naidounode.txt
        https://raw.githubusercontent.com/zhangkaiitugithub/passcro/main/speednodes.yaml
        https://raw.githubusercontent.com/aiboboxx/clashfree/refs/heads/main/clash.yml
        https://raw.githubusercontent.com/ljlfct01/ljlfct01.github.io/refs/heads/main/节点
        https://raw.githubusercontent.com/mahdibland/ShadowsocksAggregator/master/LogInfo.txt
        https://raw.githubusercontent.com/wangyingbo/yb_clashgithub_sub/main/clash_sub.yml
        https://SOS.CMLiussss.net/auto
        https://sub.fqzsnai.ggff.net/auto
        https://sub.mikeone.ggff.net/sub?token=6e300fe82f12874e439b76693aa179fb
        https://sub.reajason.eu.org/clash.yaml
        https://v1.mk/HuaplNe
        https://www.freeclashnode.com/uploads/{Y}/{m}/0-{Ymd}.yaml
        https://www.freeclashnode.com/uploads/{Y}/{m}/1-{Ymd}.yaml
        https://zrf.zrf.me/zrf
        ```
        """)
    
    # 处理链接 - 直接从设置中读取最新的链接
    links = [link.strip() for link in settings["proxy_links"] if link.strip()]
    
    # 显示当前保存的链接数量
    st.caption(f"当前保存了 {len(links)} 个链接，链接已自动保存")
    
    st.divider()
    
    if 'show_greeting' not in st.session_state:
        st.session_state.show_greeting = False

    # 获取节点按钮
    if st.button("批量获取节点", key="get_nodes_btn"):
        # 停止clash
        st.cache_data.clear() # 显式清理缓存
        st.cache_resource.clear()
        st.session_state.show_greeting = True  # 设置提示标志
        _stop_clash()
    if st.session_state.show_greeting:
        st.session_state.show_greeting = False
        # 重新加载设置，确保使用最新保存的链接
        settings = load_settings()
        links = [link.strip() for link in settings["proxy_links"] if link.strip()]
        if not links and not (os.path.exists("input") and any(f.endswith(('.yaml', '.yml', '.json', '.txt')) for f in os.listdir("input"))):
            st.warning("请先添加至少一个代理链接或上传配置文件")
        else:
            # 清空测速结果（因为将要生成新配置）
            st.session_state.speed_test_results = []
            st.session_state.speed_test_group = ""
            st.session_state.test_node_count = 0
            save_speed_test_results([], "", 0)
            
            with st.spinner("正在获取代理并生成配置..."):
                # 显示进度条
                progress_bar = st.progress(0)
                progress_text = st.empty()
                
                # 阶段1：读取并合并节点
                progress_text.text("读取节点中...")
                progress_bar.progress(0.1)
                
                # 从input文件夹读取节点
                nodes = capture_output(read_yaml_files, folder_path="input") or []
                
                # 过滤节点类型
                if proxy_types and nodes:
                    nodes = capture_output(filter_by_types_alt, proxy_types, nodes=nodes) or []
                
                # 读取链接
                progress_bar.progress(0.3)
                txt_links = capture_output(read_txt_files, folder_path="input") or []
                # 付费订阅走环境变量 / 私有文件，不进仓库
                private_links = capture_output(read_private_links, "input") or []
                all_links = capture_output(merge_lists, txt_links, private_links, links) or links
                
                # 阶段2：生成配置
                progress_text.text("生成配置文件中...")
                progress_bar.progress(0.5)

                if all_links or nodes:
                    # 使用自定义函数替代原函数，添加去重功能
                    custom_generate_clash_config(all_links, nodes)
                    all_links = []
                    nodes = []
                    # 阶段3：测试节点（如果Clash正在运行）
                    _start_clash(rerun=False)
                    clash_actually_running = st.session_state.clash_running or is_clash_running()
                    if clash_actually_running:
                        # 更新会话状态，确保一致性
                        if not st.session_state.clash_running and is_clash_running():
                            st.session_state.clash_running = True
                        progress_text.text("测试节点延迟中...")
                        progress_bar.progress(0.7)
                        try:
                            switch_proxy('DIRECT')
                            st.session_state.delays = capture_output(asyncio.run, proxy_clean()) or []
                            update_settings(delays=st.session_state.delays)
                        except Exception as e:
                            print(f"proxy_clean 失败: {str(e)}")
                            st.session_state.delays = []
                            update_settings(delays=[])
                        finally:
                            switch_proxy('DIRECT')
                    # 完成
                    progress_bar.progress(1.0)
                    progress_text.text("完成！")
                    st.success("成功获取代理并生成配置文件")
                    st.rerun()
                else:
                    st.warning("没有找到可用的代理链接或节点")

    
    # 显示节点列表
    st.subheader("节点列表")
    if os.path.exists("clash_config.yaml"):
        config = ClashConfig("clash_config.yaml")
        group_names = config.get_group_names()
        group_names = [x for x in group_names if x != '节点选择']
        # 选择代理组
        selected_group = st.selectbox(
            "选择代理组", 
            options=group_names,
            key="node_group_select"
        )
        
        # 显示节点
        if selected_group:
            proxies = config.get_group_proxies(selected_group)
            st.write(f"**{selected_group}** 包含 **{len(proxies)}** 个有效节点")
            
            # 过滤特殊节点
            proxies = [p for p in proxies if p not in ["DIRECT", "REJECT"]]
            
            # 创建数据表格
            data = [{"序号": i+1, "代理名称": proxy} for i, proxy in enumerate(proxies)]
            
            # 显示表格
            if data:
                df = merge_node_data(data, st.session_state.delays)
                st.dataframe(
                    df,
                    use_container_width=True,
                    height=400,
                    column_config={
                        "序号": st.column_config.NumberColumn("序号", width=60),
                        "代理名称": st.column_config.TextColumn("代理名称", width="large"),
                        "Delay_ms": st.column_config.NumberColumn("延迟(ms)", format="%.2f ms")
                    },
                    hide_index=True
                )
            else:
                st.info(f"{selected_group} 组中没有节点")
    else:
        st.info("尚未生成配置文件，请先获取节点")

# 测速标签页
with tab2:
    st.header("节点测速")
    
    # 初始化会话状态中的测速结果
    if "speed_test_results" not in st.session_state:
        # 从文件加载测速结果
        saved_results = load_speed_test_results()
        st.session_state.speed_test_results = saved_results["results"]
        st.session_state.speed_test_group = saved_results["group_name"]
        st.session_state.test_node_count = saved_results["node_count"]
    
    # 使用函数检查Clash是否真的在运行
    clash_actually_running = st.session_state.clash_running or is_clash_running()
    if not clash_actually_running:
        st.warning("Clash 服务未运行，请稍等片刻或检查服务状态")
    else:
        # 确保会话状态与实际状态一致
        if not st.session_state.clash_running and is_clash_running():
            st.session_state.clash_running = True
        
        # 测速设置
        st.subheader("测速设置")
        col1, col2 = st.columns(2)
        with col1:
            test_node_count = st.number_input("测试节点数量", 
                min_value=1, 
                max_value=100, 
                value=10, 
                step=1,
                help="设置要测试的节点数量（按列表顺序）")
            
        with col2:
            test_timeout = st.number_input("下载测试时间 (秒)", 
                min_value=1, 
                max_value=30, 
                value=3, 
                step=1,
                help="每个节点将下载指定秒数后停止，时间越长测试越准确，但总耗时也更长")
        
        # 选择要测速的代理组
        if os.path.exists("clash_config.yaml"):
            config = ClashConfig("clash_config.yaml")
            group_names = config.get_group_names()
            group_names = [x for x in group_names if x != '节点选择']
            
            selected_group = st.selectbox(
                "选择代理组进行测速", 
                options=group_names,
                key="speed_test_group_select"
            )
            
            # 显示节点和开始测速按钮
            if selected_group:
                all_proxies = config.get_group_proxies(selected_group)
                all_proxies = [p for p in all_proxies if p not in ["DIRECT", "REJECT"]]
                
                if not all_proxies:
                    st.info(f"{selected_group} 组中没有节点")
                else:
                    # 限制测试节点数量
                    test_node_count = min(test_node_count, len(all_proxies))
                    proxies = all_proxies[:test_node_count]
                    
                    st.write(f"**{selected_group}** 包含 **{len(all_proxies)}** 个节点，将测试前 **{test_node_count}** 个")
                    
                    # 开始测速按钮
                    if st.button("开始测速", key="start_speed_test"):
                        if not proxies:
                            st.warning("没有可测试的节点")
                        else:
                            with st.spinner("正在测速中..."):
                                # 创建进度条
                                progress_bar = st.progress(0)
                                progress_text = st.empty()
                                
                                # 创建结果列表
                                results = []
                                total = len(proxies)
                                
                                # 测试每个节点
                                for i, proxy in enumerate(proxies):
                                    progress_text.text(f"测试节点 {i+1}/{total}: {proxy} (下载测试 {test_timeout}秒)")
                                    progress_bar.progress((i) / total)
                                    
                                    # 调用测速函数
                                    try:
                                        capture_output(switch_proxy, proxy_name=proxy)
                                        speed_result = capture_output(test_proxy_speed, proxy_name=proxy, timeout=test_timeout)
                                        
                                        # 将结果添加到列表
                                        if speed_result and isinstance(speed_result, dict):
                                            speed_result["name"] = proxy
                                            results.append(speed_result)
                                        else:
                                            print(f"节点 {proxy} 测速失败")
                                    except Exception as e:
                                        print(f"节点 {proxy} 测速出错: {str(e)}")
                                
                                # 完成测速
                                progress_bar.progress(1.0)
                                progress_text.text("测速完成！")
                                
                                # 按速度排序结果（不再过滤）
                                if results:
                                    # 按速度排序
                                    results.sort(key=lambda x: x.get("speed", 0), reverse=True)
                                    # 格式化数据
                                    table_data = []
                                    sorted_proxy_names = []
                                    for i, result in enumerate(results):
                                        table_data.append({
                                            "序号": i+1,
                                            "节点名称": result.get("name", "未知"),
                                            "下载速度 (MB/s)": round(result.get("speed", 0), 2),
                                            "延迟 (ms)": result.get("delay", 0)
                                        })
                                        sorted_proxy_names.append(result["name"])
                                    # 只重排当前测速组的节点，其他组保持原样
                                    group = next((g for g in config.proxy_groups
                                                  if g["name"] == selected_group), None)
                                    if group is not None:
                                        original = group.get("proxies", [])
                                        ordered = [n for n in sorted_proxy_names if n in original]
                                        rest = [n for n in original if n not in ordered]
                                        group["proxies"] = ordered + rest
                                    config.save()

                                    # 将结果存储到会话状态
                                    st.session_state.speed_test_results = table_data
                                    st.session_state.speed_test_group = selected_group
                                    st.session_state.test_node_count = test_node_count
                                    
                                    # 保存测速结果到文件
                                    save_speed_test_results(table_data, selected_group, test_node_count)
                                else:
                                    # 如果没有结果，清空会话状态的测速结果
                                    st.session_state.speed_test_results = []
                                    st.session_state.speed_test_group = ""
                                    st.session_state.test_node_count = 0
                                    # 清空保存的测速结果
                                    save_speed_test_results([], "", 0)
                                    st.warning("测速失败，未获取到任何有效结果")
                                
                                # 切换回DIRECT
                                capture_output(switch_proxy, proxy_name="DIRECT")
                    
                    # 显示保存在会话状态中的测速结果
                    if st.session_state.speed_test_results:
                        # 显示测试信息
                        st.subheader(f"测速结果 - {st.session_state.speed_test_group}")
                        st.info(f"已测试 {len(st.session_state.speed_test_results)} 个节点，按下载速度排序")
                        
                        # 显示结果表格
                        df = pd.DataFrame(st.session_state.speed_test_results)
                        st.dataframe(
                            df,
                            use_container_width=True,
                            column_config={
                                "序号": st.column_config.NumberColumn("序号", width=60),
                                "节点名称": st.column_config.TextColumn("节点名称", width="large"),
                                "下载速度 (MB/s)": st.column_config.NumberColumn("下载速度 (MB/s)", format="%.2f MB/s"),
                                "延迟 (ms)": st.column_config.NumberColumn("延迟 (ms)", format="%d ms")
                            },
                            hide_index=True
                        )
                        
                        # 添加清除结果按钮
                        if st.button("清除测速结果", key="clear_speed_results"):
                            st.session_state.speed_test_results = []
                            st.session_state.speed_test_group = ""
                            st.session_state.test_node_count = 0
                            # 清空保存的测速结果
                            save_speed_test_results([], "", 0)
                            st.rerun()
        else:
            st.info("尚未生成配置文件，请先在'获取节点'标签页获取节点")

# 配置编辑标签页
with tab3:
    st.header("配置编辑")
    
    # 获取订阅地址功能
    st.subheader("生成订阅链接")
    st.info("此功能将生成永久订阅链接，即使重置也不会失效")
    
    # 添加文件存储安全性提示
    with st.expander("📌  关于订阅文件存储与安全性的说明", expanded=True):
        st.markdown("""
            **文件存储说明**:
            - 默认同时生成`clash`和`singbox`订阅链接
            - 您的订阅配置文件**不会**保存在服务器上，可以放心使用
            - 文件实际托管在 [catbox.moe](https://catbox.moe) (需翻)的文件服务上
        """)
    # 加载保存的订阅链接（如果有）
    settings = load_settings()
    subscription_links = settings.get("subscription_links", {})
    
    if not os.path.exists("clash_config.yaml"):
        st.warning("未找到配置文件，请先在'获取节点'标签页生成配置文件")
    else:
        # 根据是否已有链接显示不同的按钮文本
        button_text = "重新生成链接" if subscription_links and ("clash_url" in subscription_links or "singbox_url" in subscription_links) else "生成订阅链接"
        
        # 显示生成/重新生成按钮
        if st.button(button_text, key="gen_subscription_links"):
            _stop_clash(rerun=False)
            with st.spinner("正在上传配置并生成链接..."):
                try:
                    # 调用upload_and_generate_urls方法获取订阅链接
                    links = upload_and_generate_urls("clash_config.yaml")
                    
                    # 显示链接结果
                    if links and isinstance(links, dict):
                        # 保存链接到设置文件
                        settings["subscription_links"] = links
                        save_settings(settings)
                        
                        st.success("订阅链接生成成功")
                        st.rerun()  # 重新加载页面以显示保存的链接
                    else:
                        st.error("未获取到有效的订阅链接，返回数据类型：" + str(type(links)))
                        st.write("返回数据内容：", links)
                except Exception as e:
                    st.error(f"生成订阅链接失败: {str(e)}")
                    import traceback
                    st.code(traceback.format_exc())
        
        # 如果已经有保存的订阅链接，显示链接和复制功能
        if subscription_links and ("clash_url" in subscription_links or "singbox_url" in subscription_links):
            # 显示Clash链接
            if "clash_url" in subscription_links and subscription_links["clash_url"]:
                st.subheader("Clash 订阅")
                clash_link = subscription_links["clash_url"]
                
                # 创建一行用于显示链接和复制按钮
                col1, col2 = st.columns([4, 1])
                with col1:
                    st.code(clash_link)
                with col2:
                    # 使用HTML组件实现可靠的复制功能，优化样式适应手机
                    components.html(
                        f"""
                        <style>
                            @media (max-width: 768px) {{
                                .copy-button-container {{
                                    width: 100% !important;
                                }}
                                .copy-button {{
                                    width: 100% !important;
                                }}
                            }}
                        </style>
                        <div style="display:flex; justify-content:center; align-items:center; height:100%;" class="copy-button-container">
                            <button 
                                onclick="
                                    navigator.clipboard.writeText('{clash_link}');
                                    this.textContent = '已复制!';
                                    setTimeout(() => this.textContent = '复制链接', 2000);
                                    parent.postMessage({{type: 'streamlit:toast', data: {{icon: '✅', body: 'Clash链接已复制到剪贴板！'}} }}, '*');
                                "
                                style="background-color: #4CAF50; color: white; border: none; border-radius: 4px; padding: 6px 12px; cursor: pointer; font-size: 14px; white-space: nowrap; display: block;"
                                class="copy-button"
                            >
                                复制链接
                            </button>
                        </div>
                        """,
                        height=73,  # 匹配code块高度
                    )
            
            # 显示SingBox链接
            if "singbox_url" in subscription_links and subscription_links["singbox_url"]:
                st.subheader("SingBox 订阅")
                singbox_link = subscription_links["singbox_url"]
                
                # 创建一行用于显示链接和复制按钮
                col1, col2 = st.columns([4, 1])
                with col1:
                    st.code(singbox_link)
                with col2:
                    # 使用HTML组件实现可靠的复制功能，优化样式适应手机
                    components.html(
                        f"""
                        <style>
                            @media (max-width: 768px) {{
                                .copy-button-container {{
                                    width: 100% !important;
                                }}
                                .copy-button {{
                                    width: 100% !important;
                                }}
                            }}
                        </style>
                        <div style="display:flex; justify-content:center; align-items:center; height:100%;" class="copy-button-container">
                            <button 
                                onclick="
                                    navigator.clipboard.writeText('{singbox_link}');
                                    this.textContent = '已复制!';
                                    setTimeout(() => this.textContent = '复制链接', 2000);
                                    parent.postMessage({{type: 'streamlit:toast', data: {{icon: '✅', body: 'SingBox链接已复制到剪贴板！'}} }}, '*');
                                "
                                style="background-color: #4CAF50; color: white; border: none; border-radius: 4px; padding: 6px 12px; cursor: pointer; font-size: 14px; white-space: nowrap; display: block;"
                                class="copy-button"
                            >
                                复制链接
                            </button>
                        </div>
                        """,
                        height=73,  # 匹配code块高度
                    )

    st.divider()
    
    # 配置文件管理
    st.subheader("配置文件管理")
    st.info("此功能可以删除当前生成的所有配置文件")
    
    # 检查是否存在配置文件
    config_files = []
    if os.path.exists("clash_config.yaml"):
        config_files.append("clash_config.yaml")
    if os.path.exists("clash_config.yaml.json"):
        config_files.append("clash_config.yaml.json")
        
    if not config_files:
        st.warning("未找到配置文件，请先在'获取节点'标签页生成配置文件")
    else:
        # 创建确认状态（如果不存在）
        if "confirm_clean" not in st.session_state:
            st.session_state.confirm_clean = False
        
        # 仅当未处于确认状态时显示清理按钮
        if not st.session_state.confirm_clean:
            if st.button("清理配置文件", key="clean_config_files"):
                # 设置确认状态
                st.session_state.confirm_clean = True
                # 立即重新运行以隐藏按钮
                st.rerun()
        
        # 显示确认窗口
        if st.session_state.confirm_clean:
            st.warning("您确定要删除所有配置文件吗？此操作不可恢复。")
            confirm_col1, confirm_col2 = st.columns(2)
            with confirm_col1:
                if st.button("确认删除", key="confirm_clean_btn"):
                    deleted_files = []
                    # 删除配置文件
                    for config_file in config_files:
                        try:
                            os.remove(config_file)
                            deleted_files.append(config_file)
                        except Exception as e:
                            st.error(f"删除文件 {config_file} 失败: {str(e)}")
                    
                    # 清空测速结果
                    if "speed_test_results" in st.session_state:
                        st.session_state.speed_test_results = []
                        st.session_state.speed_test_group = ""
                        st.session_state.test_node_count = 0
                        save_speed_test_results([], "", 0)
                    
                    # 显示成功消息
                    if deleted_files:
                        st.success(f"已成功删除以下配置文件: {', '.join(deleted_files)}")
                        st.session_state.confirm_clean = False
                        # 延迟一秒后刷新页面
                        time.sleep(1)
                        st.rerun()
            
            with confirm_col2:
                if st.button("取消", key="cancel_clean_btn"):
                    st.session_state.confirm_clean = False
                    st.rerun()
    
    st.divider()
    
    # 配置内容编辑
    st.subheader("配置内容编辑")
    st.info("此功能可以直接编辑配置文件的内容")
    
    if not config_files:
        st.warning("未找到配置文件，请先在'获取节点'标签页生成配置文件")
    else:
        # 选择要编辑的配置文件
        selected_config = st.selectbox(
            "选择配置文件", 
            options=config_files,
            key="edit_config_select"
        )
        
        # 读取选中的配置文件内容
        try:
            with open(selected_config, 'r', encoding='utf-8') as f:
                config_content = f.read()
            
            # 根据文件类型提供更好的编辑体验
            file_type = "yaml" if selected_config.endswith(".yaml") else "json"
            
            edited_content = st.text_area(
                "配置内容（直接编辑）",
                value=config_content,
                height=500,
                # 用文件名做 key：切换文件时自动加载对应内容，而不是沿用上一个文件
                key=f"config_editor_{selected_config}"
            )
            
            # 尝试验证YAML/JSON格式
            is_valid = True
            validation_error = ""
            
            try:
                if file_type == "yaml":
                    yaml.safe_load(edited_content)
                else:  # JSON
                    json.loads(edited_content)
            except Exception as e:
                is_valid = False
                validation_error = str(e)
            
            # 显示验证结果
            if not is_valid:
                st.error(f"配置格式错误: {validation_error}")
                st.warning("请修复格式错误后再保存")
            
            # 使用HTML组件创建并排按钮，确保在移动设备上也保持一行
            save_disabled = "disabled" if not is_valid else ""
            
            # 格式化后下载
            download_data = edited_content
            if is_valid:
                try:
                    if file_type == "yaml":
                        yaml_data = yaml.safe_load(edited_content)
                        download_data = yaml.dump(yaml_data, default_flow_style=False, sort_keys=False, allow_unicode=True)
                    elif file_type == "json":
                        json_data = json.loads(edited_content)
                        download_data = json.dumps(json_data, ensure_ascii=False, indent=2)
                except:
                    # 如果格式化失败，使用原始内容
                    pass
            
            # 使用固定容器创建按钮布局，确保始终保持一行显示
            button_container = st.container()
            with button_container:
                # 使用CSS设置按钮容器为flex布局
                st.markdown("""
                <style>
                    div[data-testid="column"]:nth-of-type(1) .stButton,
                    div[data-testid="column"]:nth-of-type(2) .stButton {
                        width: 100%;
                        min-width: 0;
                    }
                    div[data-testid="column"]:nth-of-type(1) .stButton > button,
                    div[data-testid="column"]:nth-of-type(2) .stButton > button {
                        width: 100%;
                        white-space: nowrap;
                    }
                    .button-flex-container div.row-widget.stHorizontal {
                        flex-wrap: nowrap !important;
                    }
                </style>
                <div class="button-flex-container">
                """, unsafe_allow_html=True)
                
                col1, col2 = st.columns(2)
                with col1:
                    save_clicked = st.button(
                        "保存修改",
                        key="save_config_btn",
                        disabled=not is_valid,
                        help="保存修改到配置文件",
                        type="primary",
                        use_container_width=True
                    )
                    
                    # 处理保存按钮点击
                    if save_clicked:
                        try:
                            # 解析后同时写 yaml 与 json，避免两份配置分叉
                            if file_type == "yaml":
                                data = yaml.safe_load(edited_content)
                                with open(selected_config, 'w', encoding='utf-8') as f:
                                    yaml.dump(data, f, default_flow_style=False, sort_keys=False, allow_unicode=True)
                                with open(f'{selected_config}.json', 'w', encoding='utf-8') as f:
                                    json.dump(data, f, ensure_ascii=False, indent=2)
                            else:
                                data = json.loads(edited_content)
                                with open(selected_config, 'w', encoding='utf-8') as f:
                                    json.dump(data, f, ensure_ascii=False, indent=2)
                                yaml_path = selected_config[:-5] if selected_config.endswith('.json') else f'{selected_config}.yaml'
                                with open(yaml_path, 'w', encoding='utf-8') as f:
                                    yaml.dump(data, f, default_flow_style=False, sort_keys=False, allow_unicode=True)

                            # 清空订阅链接，因为配置已经修改
                            update_settings(subscription_links={})

                            st.success("配置已保存并且订阅链接已重置")
                            st.rerun()  # 重新加载页面以反映变化
                        except Exception as e:
                            st.error(f"保存配置失败: {str(e)}")
                
                with col2:
                    # 下载按钮
                    st.download_button(
                        label="下载配置文件",
                        data=download_data,
                        file_name=selected_config,
                        mime="text/plain" if file_type == "yaml" else "application/json",
                        key="download_config_btn",
                        help="下载当前配置文件",
                        type="secondary",
                        use_container_width=True
                    )
                
                st.markdown("</div>", unsafe_allow_html=True)
        
        except Exception as e:
            st.error(f"读取配置文件失败: {str(e)}")


# 页脚
st.markdown("---")
st.markdown(
    """
    <div class="footer">
        <a href="https://github.com/fish2018/ClashForge">ClashForge</a> | 
        <a href="https://t.me/s/tgsearchers">TG频道资源宇宙</a> | 
        <a href="https://proxy.252035.xyz/">订阅转换</a>  
    </div>
    """,
    unsafe_allow_html=True
)

# 不蒜子访问统计
busuanzi_html = """
<script async src="//busuanzi.ibruce.info/busuanzi/2.3/busuanzi.pure.mini.js"></script>
<div class="footer" style="text-align: center;">
    <span id="busuanzi_container_site_pv">
        本站总访问量 <span id="busuanzi_value_site_pv"></span> 次
    </span>
     | 
    <span id="busuanzi_container_site_uv">
        本站访客数 <span id="busuanzi_value_site_uv"></span> 人
    </span>
</div>
"""
components.html(busuanzi_html, height=100)

