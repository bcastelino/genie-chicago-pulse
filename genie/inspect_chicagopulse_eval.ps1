param(
    [string]$SpaceId = "01f1a00325751a998b2eeb627266a3f2",
    [string]$EvalRunId = "01f1a0084df312ddb75a98c9d733500c",
    [string]$ProfileName = "chicagopulse",
    [string]$OutputDir = ".\genie\eval-results"
)

$ErrorActionPreference = "Stop"

New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null

Write-Host "Fetching evaluation result list..."

$listJson = databricks genie genie-list-eval-results `
    $SpaceId `
    $EvalRunId `
    --page-size 100 `
    --profile $ProfileName `
    -o json

if ($LASTEXITCODE -ne 0) {
    throw "Failed to list evaluation results."
}

$list = $listJson | ConvertFrom-Json

$details = @()

foreach ($item in $list.eval_results) {
    Write-Host "Inspecting:" $item.question

    $detailJson = databricks genie genie-get-eval-result-details `
        $SpaceId `
        $EvalRunId `
        $item.result_id `
        --profile $ProfileName `
        -o json

    if ($LASTEXITCODE -ne 0) {
        Write-Warning "Could not fetch details for result $($item.result_id)"
        continue
    }

    $detail = $detailJson | ConvertFrom-Json

    $actualSql = @(
        $detail.actual_response |
        Where-Object { $_.response_type -eq "SQL" } |
        ForEach-Object { $_.response }
    ) -join "`n---`n"

    $expectedSql = @(
        $detail.expected_response |
        Where-Object { $_.response_type -eq "SQL" } |
        ForEach-Object { $_.response }
    ) -join "`n---`n"

    $actualErrors = @(
        $detail.actual_response |
        Where-Object {
            $_.sql_execution_result -and
            $_.sql_execution_result.status -and
            $_.sql_execution_result.status.state -eq "FAILED"
        } |
        ForEach-Object {
            if ($_.sql_execution_result.status.error) {
                $_.sql_execution_result.status.error | ConvertTo-Json -Depth 20 -Compress
            }
        }
    ) -join "`n"

    $expectedErrors = @(
        $detail.expected_response |
        Where-Object {
            $_.sql_execution_result -and
            $_.sql_execution_result.status -and
            $_.sql_execution_result.status.state -eq "FAILED"
        } |
        ForEach-Object {
            if ($_.sql_execution_result.status.error) {
                $_.sql_execution_result.status.error | ConvertTo-Json -Depth 20 -Compress
            }
        }
    ) -join "`n"

    $details += [PSCustomObject]@{
        benchmark_question_id = $detail.benchmark_question_id
        result_id              = $detail.result_id
        question               = $item.question
        list_status            = $item.status
        assessment             = $detail.assessment
        manual_assessment      = $detail.manual_assessment
        assessment_reasons     = ($detail.assessment_reasons -join "; ")
        actual_sql             = $actualSql
        expected_sql           = $expectedSql
        actual_sql_error       = $actualErrors
        expected_sql_error     = $expectedErrors
    }
}

$jsonPath = Join-Path $OutputDir "$EvalRunId-details.json"
$csvPath  = Join-Path $OutputDir "$EvalRunId-summary.csv"

$details |
    ConvertTo-Json -Depth 100 |
    Set-Content $jsonPath -Encoding utf8

$details |
    Export-Csv $csvPath -NoTypeInformation -Encoding utf8

Write-Host ""
Write-Host "===== ASSESSMENT SUMMARY ====="

$details |
    Group-Object assessment |
    Sort-Object Name |
    ForEach-Object {
        Write-Host ("{0}: {1}" -f $_.Name, $_.Count)
    }

Write-Host ""
Write-Host "===== NON-GOOD RESULTS ====="

$details |
    Where-Object { $_.assessment -ne "GOOD" } |
    Select-Object `
        question, `
        list_status, `
        assessment, `
        assessment_reasons, `
        actual_sql_error, `
        expected_sql_error |
    Format-List

Write-Host ""
Write-Host "JSON:" $jsonPath
Write-Host "CSV :" $csvPath