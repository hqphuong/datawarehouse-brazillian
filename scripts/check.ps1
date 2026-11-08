param(
    [switch]$Quick
)

$ErrorActionPreference = "Continue"
$root = Split-Path -Parent $PSScriptRoot
$reportsDir = Join-Path $root "reports"
$rawPath = Join-Path $reportsDir "dss_eval_raw.txt"
$outputPath = Join-Path $reportsDir "CHECK_OUTPUT.txt"
$failures = New-Object System.Collections.Generic.List[string]
$report = New-Object System.Collections.Generic.List[string]
$pytestOutput = @()
$djangoOutput = @()
$regenOutput = @()
$pytestExit = 1
$djangoExit = 1
$regenExit = 0

$python = $null
foreach ($candidate in @(
    (Join-Path $root "backend\env\Scripts\python.exe"),
    (Join-Path $root "env\Scripts\python.exe"),
    (Join-Path $root ".venv\Scripts\python.exe")
)) {
    if (Test-Path $candidate) {
        $python = $candidate
        break
    }
}
if (-not $python) {
    $pythonCommand = Get-Command python -ErrorAction SilentlyContinue
    if ($pythonCommand) {
        $python = $pythonCommand.Source
    }
}

if ($python) {
    Push-Location $root
    $pytestOutput = @(& $python -m pytest 2>&1)
    $pytestExit = $LASTEXITCODE
    Pop-Location
} else {
    $pytestOutput = @("Python executable not found.")
    $pytestExit = 127
}

$pytestText = $pytestOutput -join [Environment]::NewLine
$pytestPassed = 0
$pytestFailed = 0
if ($pytestText -match "(\d+) passed") { $pytestPassed = [int]$Matches[1] }
if ($pytestText -match "(\d+) failed") { $pytestFailed = [int]$Matches[1] }
if ($pytestText -match "(\d+) error") { $pytestFailed += [int]$Matches[1] }
if ($pytestExit -ne 0 -and $pytestFailed -eq 0) { $pytestFailed = 1 }
if ($pytestExit -ne 0) { $failures.Add("pytest") }

$djangoPython = Join-Path $root "backend\env\Scripts\python.exe"
if (Test-Path $djangoPython) {
    Push-Location (Join-Path $root "backend")
    $djangoOutput = @(& $djangoPython manage.py test dss analytics 2>&1)
    $djangoExit = $LASTEXITCODE
    Pop-Location
} else {
    $djangoOutput = @("backend\env\Scripts\python.exe not found.")
    $djangoExit = 127
}

$djangoText = $djangoOutput -join [Environment]::NewLine
$djangoRan = 0
$djangoSkipped = 0
$djangoPassed = 0
$djangoFailed = 0
if ($djangoText -match "Ran (\d+) tests?") { $djangoRan = [int]$Matches[1] }
if ($djangoText -match "FAILED \(failures=(\d+)") {
    $djangoFailed += [int]$Matches[1]
}
if ($djangoText -match "errors=(\d+)") { $djangoFailed += [int]$Matches[1] }
if ($djangoText -match "skipped=(\d+)") { $djangoSkipped = [int]$Matches[1] }
if ($djangoExit -eq 0) { $djangoFailed = 0 }
elseif ($djangoFailed -eq 0) { $djangoFailed = 1 }
$djangoPassed = [Math]::Max(0, $djangoRan - $djangoFailed - $djangoSkipped)
if ($djangoExit -ne 0) { $failures.Add("Django") }

if (-not $Quick) {
    if ($python) {
        Push-Location $root
        $regenOutput = @(& $python (Join-Path $root "scripts\regen_eval.py") 2>&1)
        $regenExit = $LASTEXITCODE
        Pop-Location
    } else {
        $regenOutput = @("Python executable not found.")
        $regenExit = 127
    }
    if ($regenExit -ne 0) { $failures.Add("regen_eval") }
}

$report.Add("PASS: $($pytestPassed + $djangoPassed)  FAIL: $($pytestFailed + $djangoFailed)")
$report.Add("pytest: pass=$pytestPassed fail=$pytestFailed")
$report.Add("Django: pass=$djangoPassed fail=$djangoFailed")
if ($Quick) {
    $report.Add("regen_eval: skipped (-Quick)")
} else {
    $report.Add("regen_eval: $(if ($regenExit -eq 0) { 'pass' } else { 'fail' })")
}

if ($pytestExit -ne 0) {
    $report.Add("")
    $report.Add("pytest failing output (last 40 lines):")
    foreach ($line in @($pytestOutput | Select-Object -Last 40)) { $report.Add([string]$line) }
}
if ($djangoExit -ne 0) {
    $report.Add("")
    $report.Add("Django failing output (last 40 lines):")
    foreach ($line in @($djangoOutput | Select-Object -Last 40)) { $report.Add([string]$line) }
}
if ($regenExit -ne 0 -and -not $Quick) {
    $report.Add("")
    $report.Add("regen_eval failing output (last 40 lines):")
    foreach ($line in @($regenOutput | Select-Object -Last 40)) { $report.Add([string]$line) }
}

if (Test-Path $rawPath) {
    $rawLines = [System.IO.File]::ReadAllLines($rawPath)
    $rawBytes = (Get-Item $rawPath).Length
    $report.Add("")
    $report.Add("raw_eval_size_bytes: $rawBytes")
    $invariant = $rawLines | Where-Object { $_ -match "l1_row_efficiency.*l2_aggregate_efficiency.*l3_validity" } | Select-Object -First 1
    if (-not $invariant) {
        $invariant = $rawLines | Where-Object { $_ -match "l1_row_efficiency" } | Select-Object -First 1
    }
    if ($invariant) { $report.Add("L1-L3 invariant: $invariant") }
    else {
        $report.Add("L1-L3 invariant: NOT FOUND")
        $failures.Add("L1-L3 invariant")
    }

    foreach ($section in @(
        "Decision Brief",
        "Sign test (V4)",
        "Bootstrap route-level (V2)"
    )) {
        $report.Add("")
        $report.Add("[$section]")
        $start = -1
        $headingPattern = "^#{1,3}\s+.*" + [regex]::Escape($section)
        for ($i = 0; $i -lt $rawLines.Length; $i++) {
            if ($rawLines[$i] -match $headingPattern) { $start = $i; break }
        }
        if ($start -lt 0) {
            $report.Add("NOT FOUND")
            $failures.Add("raw_eval:$section")
            continue
        }
        $end = [Math]::Min($start + 40, $rawLines.Length)
        for ($i = $start; $i -lt $end; $i++) {
            if ($i -gt $start -and $rawLines[$i] -match "^## ") { break }
            $report.Add($rawLines[$i])
        }
    }
} else {
    $report.Add("")
    $report.Add("raw_eval_size_bytes: missing")
    $report.Add("L1-L3 invariant: NOT FOUND")
    $failures.Add("raw_eval")
}

$utf8NoBom = New-Object System.Text.UTF8Encoding -ArgumentList @([bool]$false)
[System.IO.File]::WriteAllLines($outputPath, $report.ToArray(), $utf8NoBom)

if ($failures.Count -eq 0) {
    Write-Output "OK"
} else {
    Write-Output ($failures -join ", ")
}
