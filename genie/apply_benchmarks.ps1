param(
  [Parameter(Mandatory=$true)][string]$SpaceId,
  [string]$ProfileName = "chicagopulse",
  [string]$BenchmarkFile = ".\genie\benchmarks_30.json"
)

$ErrorActionPreference = "Stop"

$currentJson = databricks genie get-space $SpaceId `
  --include-serialized-space `
  --profile $ProfileName `
  -o json

if ($LASTEXITCODE -ne 0) { throw "Failed to read Genie Agent." }

$current = $currentJson | ConvertFrom-Json
$space = $current.serialized_space | ConvertFrom-Json
$fragment = Get-Content $BenchmarkFile -Raw | ConvertFrom-Json

if ($space.PSObject.Properties.Name -contains "benchmarks") {
  $space.benchmarks = $fragment.benchmarks
} else {
  $space | Add-Member -MemberType NoteProperty -Name benchmarks -Value $fragment.benchmarks
}

$request = @{
  serialized_space = ($space | ConvertTo-Json -Depth 100 -Compress)
}

if ($current.etag) { $request.etag = $current.etag }

$tmp = Join-Path $env:TEMP "chicagopulse-genie-update.json"
$request | ConvertTo-Json -Depth 100 | Set-Content $tmp -Encoding utf8

databricks genie update-space $SpaceId `
  --json "@$tmp" `
  --profile $ProfileName `
  -o json

if ($LASTEXITCODE -ne 0) { throw "Genie Agent update failed." }

Write-Host "Applied 30 ChicagoPulse benchmarks."