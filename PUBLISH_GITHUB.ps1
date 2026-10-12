param(
    [string]$Repo = 'smouj/classicvoice'
)

$ErrorActionPreference = 'Stop'

if (-not (Get-Command gh -ErrorAction SilentlyContinue)) {
    throw "GitHub CLI (gh) is not installed. Install it, run 'gh auth login', then retry."
}

gh auth status | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'GitHub CLI is not authenticated.' }
if (-not (Test-Path -LiteralPath '.git')) { throw 'Run this script from the ClassicVoice repository.' }

$remote = git remote get-url origin 2>$null
if ($LASTEXITCODE -ne 0 -or $remote -notmatch 'github\.com[:/]smouj/classicvoice(?:\.git)?$') {
    throw "The origin remote does not point to smouj/classicvoice: $remote"
}

git push origin main
if ($LASTEXITCODE -ne 0) { throw 'Could not push main to GitHub.' }
git push origin --tags
if ($LASTEXITCODE -ne 0) { throw 'Could not push tags to GitHub.' }

gh repo edit $Repo `
    --description 'Offline multilingual text-to-speech for Windows. Classic eSpeak NG voices, language-specific pronunciation, and WAV export.' `
    --enable-issues `
    --disable-wiki `
    --add-topic text-to-speech `
    --add-topic tts `
    --add-topic espeak-ng `
    --remove-topic spanish `
    --add-topic multilingual `
    --add-topic windows `
    --add-topic offline `
    --add-topic local-first `
    --add-topic open-source `
    --add-topic desktop-app `
    --add-topic python
if ($LASTEXITCODE -ne 0) { throw 'GitHub repository metadata could not be updated.' }

Write-Host "Repository source and metadata synchronized: https://github.com/$Repo"
Write-Host 'A pushed vMAJOR.MINOR.PATCH tag starts the Windows Release workflow.'
