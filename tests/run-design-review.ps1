param([string]$Phase = 'after')
$ErrorActionPreference = 'Stop'
node (Join-Path $PSScriptRoot 'design-review.mjs') $Phase
$code = $LASTEXITCODE
exit $code
