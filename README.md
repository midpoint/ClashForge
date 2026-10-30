## 在线演示
http://cf.252035.xyz/

## 支持WebUI操作

https://github.com/user-attachments/assets/a1a377a2-e93e-461d-9915-7f7f4dd6ff36

## 功能
- 将`hysteria2://|hy2://`、`trojan://`、`ss://`、`vless://`、`vmess://`协议链接转换为clash可用的代理节点配置
- 支持从`input`目录下的所有txt文档中按行读取代理/订阅链接(每条占一行，`#`开头为注释)；公开订阅源在 `input/subscriptions.txt`
- 付费/私密订阅不写入仓库，从系统参数读取（见 [订阅来源](#订阅来源)）
- 支持从`input`目录下的所有yaml/yml读取proxies  
- 支持指定代理类型过滤，指定参数allowed_types=['ss']
- 支持从订阅源提取代理节点，支持订阅源类型:clash、v2ray、trojan、vmess、vless、ss源(链接需以"|ss"结尾)
- 支持从某些github的README.md获取代理节点
- 链接以"|links"结尾，表示链接返回内容中直接包含代理链接，用正则匹配出来
- 支持占位符匹配，Y年m月d日H时M分 例:{Ymd} {Y_m_d} {Y-m-d}
- 支持github文件名模糊匹配，{x}.yaml表示不确定文件名的yaml文件
- 将所有获取的代理节点汇聚到一个配置文件里，自动去重，name重复自动添加随机后缀，分组`自动选择`、`故障转移`、`手动选择`，策略中排除了国内节点    
- 支持全自动批量检测节点有效性，移除失效节点，并按延迟大小排序，无需人工介入（首次执行会自动下载mihomo最新release），自动移除异常节点，修复配置文件
- 可以仅执行批量检测(配置文件名为同目录的clash_config.yaml)
- 支持设置保留节点数（`LIMIT`，默认最多保留 10000 个）
- 测速完成后额外生成精选订阅 `clash_config_featured.yaml`：只包含延迟最低的前 100 个可用节点（可用环境变量 `CLASHFORGE_FEATURED_LIMIT` 调整数量），分组和规则与主配置一致，可直接导入
- 生成临时json配置，极大的提高了修复配置异常节点的效率，使用json格式处理几十万行的数据也非常快
- 支持测试节点下载速度，按下载速度排序，默认只测试前 5 个节点(每个节点测试5秒)
- 新增`WebUI.py`，运行方式`python3 -m streamlit run WebUI.py`，打开浏览器访问 `http://localhost:8501`
- 新增生成永久订阅链接功能，订阅配置文件并不会保留在服务器本地，可以放心使用。文件存储使用的是https://catbox.moe/
- 新增容器支持，启动方式`docker run -d --rm --name clashforge -p 8501:8501 2011820123/clashforge:latest`

## 快速开始

### 本地运行
```bash
pip install -r requirements.txt
python3 ClashForge.py
```

运行完成后在仓库根目录生成：

| 文件 | 内容 |
|---|---|
| `clash_config.yaml` | 全部可用节点（按延迟排序） |
| `clash_config_featured.yaml` | 精选订阅：延迟最低的前 100 个节点 |

WebUI 方式：
```bash
python3 -m streamlit run WebUI.py
```

### Docker
```bash
docker run -d --rm --name clashforge -p 8501:8501 2011820123/clashforge:latest
```

## 订阅来源

### 公开订阅
放在 `input/*.txt`，一行一个链接，`#` 开头为注释。仓库默认提供 `input/subscriptions.txt`。
以 `_private.txt` 结尾的文件不会被当作公开源读取。

### 付费/私密订阅（不进仓库）
以下任一方式，启动时自动合并并去重：

1. 环境变量 `CLASHFORGE_PRIVATE_SUBSCRIPTIONS`，多个链接用换行、逗号或分号分隔：
   ```bash
   export CLASHFORGE_PRIVATE_SUBSCRIPTIONS='https://paid.example/sub?token=xxx'
   ```
2. 环境变量 `CLASHFORGE_PRIVATE_SUBSCRIPTIONS_FILE` 指向仓库外的 txt 文件
3. 放在 `input/*_private.txt`（`.gitignore` 已忽略，不会误提交）

GitHub Actions：在仓库 `Settings → Secrets and variables → Actions` 新建 Secret `CLASHFORGE_PRIVATE_SUBSCRIPTIONS`，内容为订阅链接（一行一个），workflow 会自动注入到运行环境。

日志中的订阅链接默认脱敏（只保留协议和域名，token/路径不输出）；需要完整链接调试时设置 `CLASHFORGE_LOG_URLS=1`。

## 环境变量

| 变量 | 默认值 | 说明 |
|---|---|---|
| `CLASHFORGE_PRIVATE_SUBSCRIPTIONS` | 空 | 私密订阅链接，换行/逗号/分号分隔 |
| `CLASHFORGE_PRIVATE_SUBSCRIPTIONS_FILE` | 空 | 私密订阅文件路径（仓库外） |
| `CLASHFORGE_LOG_URLS` | 空 | 设为 `1` 时日志输出完整订阅链接（默认脱敏） |
| `CLASHFORGE_FEATURED_LIMIT` | `100` | 精选订阅节点数 |
| `CLASHFORGE_FEATURED_FILE` | `clash_config_featured.yaml` | 精选订阅输出文件 |
| `CLASHFORGE_FETCH_BUDGET` | `1500` | 订阅抓取阶段时间预算（秒） |
| `CLASHFORGE_TEST_BUDGET` | `900` | 延迟测试阶段时间预算（秒） |
| `CLASHFORGE_FETCH_WORKERS` | `10` | 订阅抓取并发数 |
| `CLASHFORGE_MAX_JS_RENDERS` | `8` | 单次运行最多 JS 渲染的链接数 |
| `CLASHFORGE_JS_RENDER_BUDGET` | `300` | JS 渲染阶段时间预算（秒） |

## GitHub Actions
- 工作流文件：`.github/workflows/main.yml`，定时抓取、测速并自动提交生成的配置。
- 运行时长控制在 1 小时以内：抓取、JS 渲染、延迟测试各阶段都有时间预算（见上表），超时后跳过剩余链接继续产出。
- 可选配置 Secret `CLASHFORGE_PRIVATE_SUBSCRIPTIONS` 注入付费订阅；未配置时自动跳过。

## 测试
```bash
pip install -r requirements-dev.txt
pytest tests/ -q
```
纯离线单元测试，不联网。

## 相关参考：
- https://wiki.metacubex.one/config/  
- https://github.com/Loyalsoldier/geoip  
- https://github.com/MetaCubeX/mihomo/releases
- https://github.com/fish2018/ClashForge/issues/11#issuecomment-2907599228 (如果需要自己实现反代catbox可以参考这里，提供Nginx和CF worker两种方式)
