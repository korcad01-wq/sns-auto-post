# Trigger GitHub Actions "Daily SNS Post" (workflow_dispatch) from the local Task Scheduler at 21:00 KST.
# Why: GitHub cron is often 3-5 hours late; a local trigger posts on time, the cron stays as backup.
# Both may run; post_*.py checks "already posted today" via API so only one post goes out.
# Token file: C:\Users\USER\.sns_auto_post_github_token.txt (never printed). Log: trigger_post.log
$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$log = Join-Path $here "trigger_post.log"
try {
    $token = (Get-Content "$env:USERPROFILE\.sns_auto_post_github_token.txt" -Raw).Trim()
    $uri = "https://api.github.com/repos/korcad01-wq/sns-auto-post/actions/workflows/post.yml/dispatches"
    $headers = @{ Authorization = "Bearer $token"; Accept = "application/vnd.github+json"; "User-Agent" = "sns-trigger" }
    $body = '{"ref":"main"}'
    Invoke-RestMethod -Uri $uri -Method Post -Headers $headers -Body $body -ContentType "application/json" -UseBasicParsing | Out-Null
    Add-Content -Path $log -Value ("{0:yyyy-MM-dd HH:mm:ss} OK dispatched" -f (Get-Date))
} catch {
    Add-Content -Path $log -Value ("{0:yyyy-MM-dd HH:mm:ss} FAIL {1}" -f (Get-Date), $_.Exception.Message)
    exit 1
}
