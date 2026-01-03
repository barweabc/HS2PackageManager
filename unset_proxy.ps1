# 取消代理设置
$env:HTTP_PROXY = ""
$env:HTTPS_PROXY = ""

# 取消 Git 全局配置
git config --global --unset http.proxy
git config --global --unset https.proxy

Write-Host "已取消代理设置。" -ForegroundColor Yellow
