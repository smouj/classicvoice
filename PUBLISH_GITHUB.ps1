param(
  [string]$Repo = "smouj/classicvoice"
)
$ErrorActionPreference = "Stop"

if (-not (Get-Command gh -ErrorAction SilentlyContinue)) {
  throw "GitHub CLI (gh) no está instalado. Instálalo y ejecuta 'gh auth login'."
}

gh auth status | Out-Null

if (-not (Test-Path .git)) { git init -b main }
git add .
if (-not (git rev-parse --verify HEAD 2>$null)) {
  git commit -m "chore: bootstrap project"
}

$exists = $true
try { gh repo view $Repo | Out-Null } catch { $exists = $false }
if (-not $exists) {
  gh repo create $Repo --public --source=. --remote=origin --push --description "Minimal local-first desktop utility for classic-style Spanish TTS with eSpeak NG."
} else {
  if (-not (git remote get-url origin 2>$null)) { git remote add origin "https://github.com/$Repo.git" }
  git push -u origin main
}

git push origin --tags

gh repo edit $Repo --enable-issues --disable-wiki --add-topic text-to-speech --add-topic tts --add-topic espeak-ng --add-topic spanish --add-topic python --add-topic offline --add-topic local-first --add-topic open-source

gh label create "scope:v0.1" --repo $Repo --description "Inside the frozen v0.1 product scope" --color "1D76DB" --force
gh label create "voice" --repo $Repo --description "Voice preset and synthesis behavior" --color "D4C5F9" --force
gh label create "release" --repo $Repo --description "Release and packaging work" --color "5319E7" --force

gh issue create --repo $Repo --title "test: Windows end-to-end eSpeak NG smoke test" --label "scope:v0.1,voice" --body "Validate text → preset → preview → WAV export using a current eSpeak NG Windows distribution. Document the exact executable/data layout used."
gh issue create --repo $Repo --title "voice: tune the four Spanish starter presets" --label "scope:v0.1,voice" --body "Audition Classic ES, Grave, Agudo and Narrador and adjust only voice/speed/pitch/amplitude. Do not introduce proprietary voices or new synthesis engines in v0.1."
gh issue create --repo $Repo --title "release: produce the first portable v0.1 package" --label "release,scope:v0.1" --body "Define a reproducible Windows portable package and document eSpeak NG GPL obligations before distributing a combined build."

Write-Host "Repository ready: https://github.com/$Repo"
