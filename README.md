## 在线演示
http://cf.252035.xyz/

## 支持WebUI操作

https://github.com/user-attachments/assets/a1a377a2-e93e-461d-9915-7f7f4dd6ff36

## 功能
- 将`hysteria2://|hy2://`、`trojan://`、`ss://`、`vless://`、`vmess://`协议链接转换为clash可用的代理节点配置
- 支持从`input`目录下的所有txt文档中按行读取代理链接(每条代理链接占一行)
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
- 支持设置保留节点数，默认保留100个延迟最小的节点
- 生成临时json配置，极大的提高了修复配置异常节点的效率，使用json格式处理几十万行的数据也非常快
- 支持测试节点下载速度，按下载速度排序，默认只测试前30个节点(每个节点测试5秒)
- 新增`WebUI.py`，运行方式`python3 -m streamlit run WebUI.py`，打开浏览器访问 `http://localhost:8501`
- 新增生成永久订阅链接功能，订阅配置文件并不会保留在服务器本地，可以放心使用。文件存储使用的是https://catbox.moe/
- 新增容器支持，启动方式`docker run -d --rm --name clashforge -p 8501:8501 2011820123/clashforge:latest`

## 相关参考：
- https://wiki.metacubex.one/config/  
- https://github.com/Loyalsoldier/geoip  
- https://github.com/MetaCubeX/mihomo/releases
- https://github.com/fish2018/ClashForge/issues/11#issuecomment-2907599228 (如果需要自己实现反代catbox可以参考这里，提供Nginx和CF worker两种方式)

