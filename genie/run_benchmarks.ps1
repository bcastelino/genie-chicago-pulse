param(
  [Parameter(Mandatory=$true)][string]$SpaceId,
  [string]$ProfileName = "chicagopulse"
)

$ErrorActionPreference = "Stop"

$run = (
  databricks genie genie-create-eval-run $SpaceId `
    --json '{}' `
    --profile $ProfileName `
    -o json
) | ConvertFrom-Json

$EvalRunId = $run.eval_run_id
Write-Host "Evaluation run:" $EvalRunId

do {
  Start-Sleep -Seconds 10
  $status = (
    databricks genie genie-get-eval-run `
      $SpaceId $EvalRunId `
      --profile $ProfileName `
      -o json
  ) | ConvertFrom-Json

  Write-Host (
    "{0}/{1} done | {2} correct | {3} review | {4}" -f `
    $status.num_done,$status.num_questions,$status.num_correct,`
    $status.num_needs_review,$status.eval_run_status
  )
} while ($status.eval_run_status -in @("RUNNING","NOT_STARTED"))

databricks genie genie-list-eval-results `
  $SpaceId $EvalRunId `
  --page-size 100 `
  --profile $ProfileName `
  -o json

Write-Host "Eval Run ID:" $EvalRunId