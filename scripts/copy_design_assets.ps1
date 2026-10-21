$ErrorActionPreference = 'Stop'
Import-Module 'C:\dev\bin\windows-execution\WindowsTaskTools.psm1'
$projectRoot = Split-Path -Parent $PSScriptRoot
$designRoot = 'I:\atni-design-system'
$fontTarget = Join-Path $projectRoot 'site/assets/fonts'
$designTarget = Join-Path $projectRoot 'site/assets/design'
New-Item -ItemType Directory -Path $fontTarget, $designTarget -Force | Out-Null
$fonts = @('LeagueSpartan-Medium.ttf', 'LeagueSpartan-SemiBold.ttf', 'NotoSans-Regular.ttf', 'NotoSans-Bold.ttf', 'NotoSansMono-Regular.ttf')
$licenses = @('OFL-LeagueSpartan.txt', 'OFL-NotoSans.txt', 'OFL-NotoSansMono.txt')
$copies = @()
foreach ($font in $fonts) {
    $copies += @{ Source = Join-Path $designRoot "fonts/src/$font"; Target = Join-Path $fontTarget $font }
}
foreach ($license in $licenses) {
    $copies += @{ Source = Join-Path $designRoot "fonts/LICENSES/$license"; Target = Join-Path $fontTarget $license }
}
$copies += @{ Source = Join-Path $projectRoot 'work/deck/media/slide-05-pic-1-image5.png'; Target = Join-Path $designTarget 'atni-climate.png' }
$copies += @{ Source = 'I:\ATNI_design-system\ATNI design system\assets\logos\atni-climate-lockup-on-dark.png'; Target = Join-Path $designTarget 'atni-climate-on-dark.png' }
$copies += @{ Source = 'C:\Users\PatrickFreeland\OneDrive - Affiliated Tribes of Northwest Indians\Pictures\NCAI_white logo.png'; Target = Join-Path $designTarget 'ncai-white-logo.png' }
$copies += @{ Source = Join-Path $projectRoot 'work/deck/media/slide-01-pic-1-image1.png'; Target = Join-Path $designTarget 'ncai-gradient-banner.png' }
$copies += @{ Source = Join-Path $projectRoot 'work/deck/media/slide-03-pic-1-image3.png'; Target = Join-Path $designTarget 'ncai-gradient-full.png' }
foreach ($copy in $copies) {
    $expectedHash = (Get-FileHash -LiteralPath $copy.Source -Algorithm SHA256).Hash
    if (Test-Path -LiteralPath $copy.Target) {
        if ((Get-FileHash -LiteralPath $copy.Target -Algorithm SHA256).Hash -ne $expectedHash) {
            throw "Refusing to replace a different existing design asset: $($copy.Target)"
        }
    } else {
        Copy-Item -LiteralPath $copy.Source -Destination $copy.Target
    }
    if ((Get-FileHash -LiteralPath $copy.Target -Algorithm SHA256).Hash -ne $expectedHash) { throw 'Design asset copy verification failed.' }
}
Write-Output "Verified $($copies.Count) selected design assets and license notices."
exit 0
