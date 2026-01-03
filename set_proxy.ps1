# 设置代理为 127.0.0.1:7890
$proxy = "http://127.0.0.1:7890"

# 设置当前会话环境变量
$env:HTTP_PROXY = $proxy
$env:HTTPS_PROXY = $proxy

# 设置 Git 全局配置
git config --global http.proxy $proxy
git config --global https.proxy $proxy

Write-Host "已成功设置代理: $proxy" -ForegroundColor Green
Write-Host "注意：环境变量仅对当前终端窗口有效，Git 配置为全局生效。" -ForegroundColor Gray
